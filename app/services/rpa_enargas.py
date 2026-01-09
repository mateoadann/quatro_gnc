import asyncio
import base64
import logging
import os
import re
import threading
import time
from datetime import datetime

from playwright.async_api import async_playwright

from .rpa_session import mark_active, mark_cooldown, mark_running

ENARGAS_LOGIN_URL = os.getenv(
    "ENARGAS_LOGIN_URL",
    "https://www.enargas.gob.ar/secciones/gas-natural-comprimido/sic.php",
)
RPA_HEADLESS = os.getenv("RPA_HEADLESS", "true").lower() == "true"
RPA_DEBUG_DIR = os.getenv("RPA_DEBUG_DIR", "/app/debug")
RPA_SESSION_IDLE_SECONDS = int(os.getenv("RPA_SESSION_IDLE_SECONDS", "120"))
RPA_SESSION_COOLDOWN_SECONDS = int(os.getenv("RPA_SESSION_COOLDOWN_SECONDS", "240"))

logger = logging.getLogger(__name__)

DATE_CELL_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_ready = threading.Event()
_session_lock: asyncio.Lock | None = None


class NoOperacionesError(Exception):
    pass


class SessionActivaError(Exception):
    pass


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread, _session_lock
    if _loop and _loop.is_running():
        return _loop

    _loop = asyncio.new_event_loop()

    def _run_loop() -> None:
        asyncio.set_event_loop(_loop)
        global _session_lock
        _session_lock = asyncio.Lock()
        _loop_ready.set()
        _loop.run_forever()

    _loop_thread = threading.Thread(target=_run_loop, daemon=True)
    _loop_thread.start()
    _loop_ready.wait()
    return _loop


def _run_on_loop(coro):
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def _get_session_lock() -> asyncio.Lock:
    if _session_lock is None:
        raise RuntimeError("RPA loop no inicializado")
    return _session_lock


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")


async def _capture_debug(page, patente: str) -> None:
    if os.getenv("RPA_DEBUG", "false").lower() != "true":
        return
    try:
        os.makedirs(RPA_DEBUG_DIR, exist_ok=True)
        filename = f"enargas_{safe_name(patente)}.png"
        screenshot_path = os.path.join(RPA_DEBUG_DIR, filename)
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.error("Screenshot guardado en %s", screenshot_path)
    except Exception:
        logger.exception("RPA: no se pudo guardar screenshot")

    try:
        container = page.locator("#div-detalle-previo")
        if await container.count() == 0:
            logger.error("HTML #div-detalle-previo: no encontrado")
            return
        html = await container.first.inner_html(timeout=2000)
        logger.error("HTML #div-detalle-previo:\n%s", html)
    except Exception:
        logger.exception("RPA: no se pudo leer HTML de #div-detalle-previo")


async def _is_visible(locator) -> bool:
    try:
        return await locator.first.is_visible()
    except Exception:
        return False


async def wait_login_result(page, timeout_ms: int = 10000) -> None:
    consultas_link = page.get_by_role("link", name=re.compile(r"Consultas", re.I))
    active_session_text = page.get_by_text(
        re.compile(r"ya\s+se\s+encu?entra\s+logueado", re.I)
    )
    invalid_alert = page.locator(".alert, [role='alert']").filter(
        has_text=re.compile(
            r"incorrect|invalida|no\s+coincide|no\s+fue\s+dado\s+de\s+alta",
            re.I,
        )
    )

    end = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < end:
        if await _is_visible(consultas_link):
            return
        if await _is_visible(active_session_text):
            raise SessionActivaError("ENARGAS: detecto 'Ya se encuentra logueado'.")
        if await _is_visible(invalid_alert):
            raise RuntimeError("ENARGAS: credenciales invalidas.")
        await page.wait_for_timeout(200)

    raise SessionActivaError("ENARGAS: no se pudo confirmar el login (timeout).")


async def login_if_needed(page, enargas_user: str, enargas_password: str) -> None:
    try:
        user_input = page.get_by_label("Usuario *")
    except Exception:
        return

    if await user_input.count() == 0 or not await _is_visible(user_input):
        return

    await user_input.fill(enargas_user)
    await page.get_by_placeholder("Contraseña").fill(enargas_password)
    await page.get_by_role("button", name=re.compile(r"Ingresar", re.I)).click()
    await wait_login_result(page, timeout_ms=10000)


async def _is_logged_in(page) -> bool:
    consultas_link = page.get_by_role("link", name=re.compile(r"Consultas", re.I))
    return await _is_visible(consultas_link)


async def ensure_consulta_flow(page, enargas_user: str, enargas_password: str) -> None:
    """
    Deja la pagina lista para consultar por Dominio.
    """
    logger.info("RPA: navegando a Consultas/Operaciones PEC")
    if not await _is_logged_in(page):
        await page.goto(ENARGAS_LOGIN_URL)
        await login_if_needed(page, enargas_user, enargas_password)

    await page.get_by_role("link", name=re.compile(r"Consultas", re.I)).click()
    await page.get_by_role("link", name=re.compile(r"Operaciones PEC", re.I)).click()

    try:
        selector = page.get_by_label("Consulta por *")
        if await selector.is_visible():
            await selector.select_option("Dominio")
    except Exception:
        pass


async def abort_if_no_operaciones(scope, timeout_ms: int = 15000) -> None:
    """
    Espera resultado dentro de #div-detalle-previo.
    - Si detecta 'No se registran operaciones' => NoOperacionesError
    - Si detecta filas con fecha/botones => OK
    """
    page = getattr(scope, "page", scope)
    container = page.locator("#div-detalle-previo")

    error_re = re.compile(
        r"la\s+solicitud\s+no\s+pudo\s+ser\s+procesada", re.IGNORECASE
    )
    no_ops_re = re.compile(r"no\s+se\s+registran\s+operaciones", re.IGNORECASE)

    end = time.monotonic() + (timeout_ms / 1000)
    detail = ""
    while time.monotonic() < end:
        try:
            detail = await container.inner_text()
        except Exception:
            try:
                detail = await page.inner_text("body")
            except Exception:
                detail = ""

        try:
            if no_ops_re.search(detail):
                raise NoOperacionesError("ENARGAS: No se registran operaciones para la patente.")
        except NoOperacionesError:
            raise
        except Exception:
            pass

        try:
            if DATE_CELL_RE.search(detail):
                return
        except Exception:
            pass

        try:
            if error_re.search(detail):
                raise RuntimeError(
                    f"ENARGAS: respuesta de error/intermedia detectada: {detail}"
                )
        except RuntimeError:
            raise
        except Exception:
            pass

        await page.wait_for_timeout(200)

    if not detail:
        detail = "<no se pudo leer inner_text del container>"

    raise RuntimeError(
        f"ENARGAS: no se pudo determinar el resultado de la consulta. Detalle: {detail}"
    )


async def open_latest_movement_popup(page):
    container = page.locator("#div-detalle-previo")
    try:
        await container.wait_for(state="visible", timeout=15000)
    except Exception:
        pass
    try:
        await container.click()
    except Exception:
        pass

    rows = container.locator("tbody tr")
    end = time.monotonic() + 12
    while time.monotonic() < end:
        if await rows.count() > 0:
            break
        await page.wait_for_timeout(200)

    if await rows.count() == 0:
        rows = container.locator("tr")

    count = await rows.count()
    logger.info("RPA: movimientos encontrados=%s", count)

    best_i = None
    best_dt = None

    for i in range(count):
        row = rows.nth(i)
        if await row.locator("button, [role='button']").count() == 0:
            continue

        row_text = (await row.inner_text()).strip()
        match = DATE_CELL_RE.search(row_text)
        if not match:
            continue

        day, month, year = map(int, match.groups())
        dt = datetime(year, month, day)

        if best_dt is None or dt > best_dt:
            best_dt = dt
            best_i = i

    if best_i is None:
        raise RuntimeError(
            "ENARGAS: no se pudo determinar la fecha mas reciente del detalle previo."
        )

    target_row = rows.nth(best_i)
    btn = target_row.locator("button, [role='button']").first
    await btn.scroll_into_view_if_needed()

    async with page.expect_popup() as p1_info:
        await btn.click()

    return await p1_info.value


class EnargasSession:
    def __init__(self, playwright, browser, context, page, headless: bool):
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page
        self.headless = headless
        self.last_used = time.monotonic()

    async def begin_job(self) -> None:
        self.last_used = time.monotonic()
        await _cancel_idle_timer()
        mark_running()

    async def end_job(self) -> None:
        self.last_used = time.monotonic()
        mark_active(RPA_SESSION_IDLE_SECONDS)
        await _schedule_idle_close(self)

    def is_idle(self) -> bool:
        return (time.monotonic() - self.last_used) > RPA_SESSION_IDLE_SECONDS

    async def logout(self) -> None:
        try:
            await self.page.get_by_role("link", name=re.compile(r"Salir", re.I)).click()
            await self.page.wait_for_timeout(1000)
        except Exception:
            pass

    async def close(self) -> None:
        try:
            await self.context.close()
        except Exception:
            pass
        try:
            await self.browser.close()
        except Exception:
            pass
        try:
            await self.playwright.stop()
        except Exception:
            pass


_session: EnargasSession | None = None
_cooldown_until = 0.0
_idle_task: asyncio.Task | None = None


async def _cancel_idle_timer() -> None:
    global _idle_task
    if _idle_task is None:
        return
    _idle_task.cancel()
    try:
        await _idle_task
    except asyncio.CancelledError:
        pass
    _idle_task = None


async def _schedule_idle_close(session: EnargasSession) -> None:
    if RPA_SESSION_IDLE_SECONDS <= 0:
        return

    async def _close_if_current() -> None:
        await asyncio.sleep(RPA_SESSION_IDLE_SECONDS)
        async with _get_session_lock():
            if _session is not session:
                return
        await _close_session(session, "inactividad")

    global _idle_task
    await _cancel_idle_timer()
    _idle_task = asyncio.create_task(_close_if_current())


def _set_cooldown() -> None:
    global _cooldown_until
    if RPA_SESSION_COOLDOWN_SECONDS <= 0:
        _cooldown_until = 0.0
        mark_cooldown(0)
        return
    _cooldown_until = time.monotonic() + RPA_SESSION_COOLDOWN_SECONDS
    mark_cooldown(RPA_SESSION_COOLDOWN_SECONDS)


async def _wait_for_cooldown() -> None:
    remaining = _cooldown_until - time.monotonic()
    if remaining <= 0:
        return
    logger.info("RPA: cooldown activo, esperando %.1fs", remaining)
    await asyncio.sleep(remaining)


def _set_session(value: EnargasSession | None) -> None:
    global _session
    _session = value


async def _close_session(session: EnargasSession, reason: str) -> None:
    logger.info("RPA: cerrando sesion (%s)", reason)
    try:
        await session.logout()
    except Exception:
        pass
    await session.close()
    _set_session(None)
    _set_cooldown()
    await _cancel_idle_timer()


async def _get_or_create_session(headless: bool) -> EnargasSession:
    async with _get_session_lock():
        session = _session

        if session and session.page and not session.page.is_closed():
            if session.headless != headless:
                await _close_session(session, "cambio de headless")
            elif session.is_idle():
                await _close_session(session, "inactividad")
            else:
                logger.info("RPA: reutilizando sesion existente")
                return session

        await _wait_for_cooldown()

        logger.info("RPA: creando nueva sesion (headless=%s)", headless)
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context()
        await context.add_init_script(
            """
            window.print = () => {};
            window.close = () => {};
            """
        )
        page = await context.new_page()
        session = EnargasSession(playwright, browser, context, page, headless)
        _set_session(session)
        mark_active(RPA_SESSION_IDLE_SECONDS)
        return session


async def _run_rpa_async(
    patente: str,
    enargas_user: str,
    enargas_password: str,
    headless: bool,
):
    session = await _get_or_create_session(headless)
    await session.begin_job()

    page = session.page
    try:
        logger.info("RPA: inicio consulta patente=%s", patente)
        await ensure_consulta_flow(page, enargas_user, enargas_password)
        await page.get_by_role("textbox", name="Dominio *").fill(patente)
        await page.get_by_role("button", name="Consultar").click()
        logger.info("RPA: consulta enviada patente=%s", patente)

        await abort_if_no_operaciones(page, timeout_ms=15000)
        await _capture_debug(page, patente)

        page1 = await open_latest_movement_popup(page)

        async with page1.expect_popup() as p2_info:
            await page1.locator("#imprimir").click()
        page2 = await p2_info.value

        await page2.wait_for_load_state("domcontentloaded")
        await page2.wait_for_timeout(1500)

        cdp = await session.context.new_cdp_session(page2)
        result = await cdp.send(
            "Page.printToPDF",
            {
                "printBackground": True,
                "preferCSSPageSize": True,
            },
        )
        pdf_bytes = base64.b64decode(result["data"])
        logger.info("RPA: PDF generado patente=%s bytes=%s", patente, len(pdf_bytes))

        await page2.close()
        await page1.close()

        return {
            "pdf_data": pdf_bytes,
            "pdf_filename": safe_name(f"{patente}_ENARGAS.pdf"),
            "resultado": None,
        }
    except SessionActivaError:
        await _capture_debug(page, patente)
        await _close_session(session, "sesion activa detectada")
        logger.info("RPA: sesion activa detectada")
        raise
    except NoOperacionesError:
        await _capture_debug(page, patente)
        logger.info("RPA: patente sin operaciones registradas")
        raise
    except Exception:
        await _capture_debug(page, patente)
        await _close_session(session, "error en ejecucion")
        logger.exception("RPA: error en consulta patente=%s", patente)
        raise
    finally:
        try:
            async with _get_session_lock():
                if _session is session:
                    await session.end_job()
        except Exception:
            pass


def run_rpa(
    patente: str,
    enargas_user: str,
    enargas_password: str,
    headless: bool | None = None,
):
    if headless is None:
        headless = RPA_HEADLESS
    return _run_on_loop(_run_rpa_async(patente, enargas_user, enargas_password, headless))
