import base64
import os
import re
import time
from datetime import datetime

from playwright.sync_api import Playwright, sync_playwright

ENARGAS_WEB = os.getenv(
    "ENARGAS_WEB","https://www.enargas.gob.ar/secciones/gas-natural-comprimido/sic.php"
)
RPA_HEADLESS = os.getenv("RPA_HEADLESS", "true").lower() == "true"

DATE_CELL_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


class NoOperacionesError(Exception):
    pass


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")


def wait_login_result(page, timeout_ms: int = 8000) -> None:
    """
    Luego de click en Ingresar:
    - Si aparece 'Consultas' => login OK
    - Si aparece 'Ya se encuetra logueado' y NO aparece 'Consultas' => aborta
    """
    already = page.get_by_text("Ya se encuetra logueado", exact=False)
    ok = page.get_by_role("link", name="Consultas")

    end = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < end:
        try:
            if ok.is_visible():
                return
        except Exception:
            pass

        try:
            if already.is_visible():
                try:
                    if ok.is_visible():
                        return
                except Exception:
                    pass
                raise RuntimeError(
                    "ENARGAS: detecto 'Ya se encuetra logueado' (bloqueo)."
                )
        except Exception:
            pass

        page.wait_for_timeout(200)

    raise RuntimeError("No se pudo confirmar el login (timeout).")


def login_if_needed(page, enargas_user: str, enargas_password: str) -> None:
    ok = page.get_by_role("link", name="Consultas")
    try:
        if ok.is_visible():
            return
    except Exception:
        pass

    user = page.get_by_role("textbox", name="Usuario *")
    pwd = page.get_by_role("textbox", name="Contraseña *")

    user.wait_for(state="visible", timeout=5000)

    user.fill(enargas_user)
    pwd.fill(enargas_password)
    page.get_by_role("button", name="Ingresar").click()

    wait_login_result(page, timeout_ms=10000)


def abort_if_no_operaciones(scope, timeout_ms: int = 4000) -> None:
    """
    scope puede ser Page o Frame.
    Si aparece el alert 'No se registran operaciones' => levanta NoOperacionesError.
    """
    alert = scope.get_by_role("alert").filter(
        has_text=re.compile(r"No se registran operaciones", re.IGNORECASE)
    )

    page = getattr(scope, "page", scope)

    end = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < end:
        try:
            if alert.first.is_visible():
                raise NoOperacionesError(
                    "ENARGAS: No se registran operaciones para la patente."
                )
        except NoOperacionesError:
            raise
        except Exception:
            pass

        page.wait_for_timeout(200)


def open_latest_movement_popup(page):
    container = page.locator("#div-detalle-previo")
    container.wait_for(state="visible", timeout=15000)

    rows = container.get_by_role("row")
    count = rows.count()

    best_i = None
    best_dt = None

    for i in range(count):
        row = rows.nth(i)
        cells = row.get_by_role("cell")
        if cells.count() == 0:
            continue

        first_cell_text = cells.nth(0).inner_text().strip()
        match = DATE_CELL_RE.match(first_cell_text)
        if not match:
            continue

        day, month, year = map(int, match.groups())
        dt = datetime(year, month, day)

        if best_dt is None or dt > best_dt:
            best_dt = dt
            best_i = i

    if best_i is None:
        raise RuntimeError(
            "No se encontro ninguna fila con fecha dd/mm/yyyy en #div-detalle-previo."
        )

    target_row = rows.nth(best_i)
    btn = target_row.get_by_role("button").first
    btn.scroll_into_view_if_needed()

    with page.expect_popup() as p1_info:
        btn.click()

    return p1_info.value


def run_rpa(
    patente: str,
    enargas_user: str,
    enargas_password: str,
    headless: bool | None = None,
):
    if headless is None:
        headless = RPA_HEADLESS

    with sync_playwright() as playwright:
        return _run_with_playwright(
            playwright, patente, enargas_user, enargas_password, headless
        )


def _run_with_playwright(
    playwright: Playwright,
    patente: str,
    enargas_user: str,
    enargas_password: str,
    headless: bool,
):
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()

    context.add_init_script(
        """
        window.print = () => {};
        window.close = () => {};
        """
    )

    try:
        page = context.new_page()
        page.goto(ENARGAS_WEB)

        login_if_needed(page, enargas_user, enargas_password)

        page.get_by_role("link", name="Consultas").click()
        page.get_by_role("link", name="Operaciones PEC").click()
        page.get_by_label("Consulta por *").select_option("Dominio")
        page.get_by_role("textbox", name="Dominio *").fill(patente)
        page.get_by_role("button", name="Consultar").click()

        abort_if_no_operaciones(page, timeout_ms=5000)

        page1 = open_latest_movement_popup(page)

        with page1.expect_popup() as p2_info:
            page1.locator("#imprimir").click()
        page2 = p2_info.value

        page2.wait_for_load_state("domcontentloaded")
        page2.wait_for_timeout(1500)

        cdp = context.new_cdp_session(page2)
        result = cdp.send(
            "Page.printToPDF",
            {
                "printBackground": True,
                "preferCSSPageSize": True,
            },
        )
        pdf_bytes = base64.b64decode(result["data"])

        page2.close()
        page1.get_by_role("link", name="Salir").click()
        page1.close()

        return {
            "pdf_data": pdf_bytes,
            "pdf_filename": safe_name(f"{patente}_ENARGAS.pdf"),
            "resultado": None,
        }
    finally:
        context.close()
        browser.close()
