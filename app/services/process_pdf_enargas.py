from __future__ import annotations

from dataclasses import dataclass
import io
from datetime import datetime
from pathlib import Path
from typing import Iterable

import re
import unicodedata

import pdfplumber


@dataclass(frozen=True)
class PdfTextProbe:
    path: str
    char_count: int
    pages_with_text: int
    total_pages: int
    use_ocr: bool
    reason: str
    sample: str
    fields: dict[str, str | list[str] | bool | int | None] | None = None


VEHICLE_LABELS = ["Marca", "Ano", "Modelo", "Uso", "Dominio"]
PATENTE_RE = re.compile(r"\b([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})\b")
DATE_RE = re.compile(r"\b\d{2}[-/]\d{2}[-/]\d{4}\b")
FECHA_CRPC_RE = re.compile(r"\b(0?[1-9]|1[0-2])\s*/\s*[0-9]{2,4}\b")
STOP_LABEL_RE = re.compile(
    r"\b(?:Oblea|Codigo|Cuit|Fecha|Operacion|Domicilio|Razon|Datos)\b",
    re.IGNORECASE,
)
LABEL_RE = re.compile(
    r"(?P<label>Marca|Modelo|Uso|Dominio|Ano|Año|Fecha\s*CRPC|F\.?\s*CRPC|CRPC)\s*:",
    re.IGNORECASE,
)
LABEL_ALIASES = {
    "marca": "marca",
    "modelo": "modelo",
    "uso": "uso",
    "dominio": "dominio",
    "ano": "ano",
    "año": "ano",
    "fecha crpc": "fecha_crpc",
    "f. crpc": "fecha_crpc",
    "crpc": "fecha_crpc",
}


def extract_text(path: str) -> tuple[str, int, int]:
    with pdfplumber.open(path) as pdf:
        return extract_text_from_pdf(pdf)


def extract_text_from_pdf(pdf) -> tuple[str, int, int]:
    text_chunks: list[str] = []
    pages_with_text = 0
    total_pages = len(pdf.pages)
    for page in pdf.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages_with_text += 1
        text_chunks.append(page_text)
    return "".join(text_chunks), pages_with_text, total_pages


def extract_text_bytes(pdf_bytes: bytes) -> tuple[str, int, int]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return extract_text_from_pdf(pdf)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", normalized).strip()


def should_use_ocr(
    text: str,
    pages_with_text: int,
    total_pages: int,
    min_chars: int = 80,
    min_pages_with_text: int = 1,
) -> tuple[bool, str]:
    char_count = len(text.strip())
    if total_pages == 0:
        return True, "PDF sin paginas"
    if pages_with_text < min_pages_with_text:
        return True, "no se detecto texto en paginas"
    if char_count < min_chars:
        return True, f"texto muy corto ({char_count} chars)"
    return False, "texto detectado"


def extract_labeled_value(text: str, label: str, next_labels: list[str]) -> str | None:
    if next_labels:
        next_pattern = "|".join(re.escape(item) for item in next_labels)
        pattern = (
            rf"{re.escape(label)}\s*:?\s*(.{1,200}?)"
            rf"(?=\s+(?:{next_pattern})\s*:|$)"
        )
    else:
        pattern = rf"{re.escape(label)}\s*:?\s*(.{1,200})$"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def extract_section(text: str, start_label: str, end_labels: list[str]) -> str:
    lower = text.lower()
    start_idx = lower.find(start_label.lower())
    if start_idx == -1:
        return text
    section = text[start_idx + len(start_label) :]
    end_idx = None
    for marker in end_labels:
        marker_idx = section.lower().find(marker.lower())
        if marker_idx != -1:
            end_idx = marker_idx if end_idx is None else min(end_idx, marker_idx)
    if end_idx is not None:
        section = section[:end_idx]
    return section


def clean_value(value: str) -> str:
    if not value:
        return value
    cleaned = STOP_LABEL_RE.split(value)[0].strip(" :;-")
    return cleaned


def normalize_crpc_value(value: str) -> str | None:
    match = re.search(r"(0?[1-9]|1[0-2])\s*/\s*([0-9]{2,4})", value)
    if not match:
        return None
    month = int(match.group(1))
    year = match.group(2)
    if len(year) == 4:
        year = year[-2:]
    return f"{month}/{year}"


def unique_in_order(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def parse_fecha_consulta(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def parse_fecha_vencimiento(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def parse_crpc_month(value: str) -> tuple[int, int] | None:
    match = re.search(r"(0?[1-9]|1[0-2])\s*/\s*([0-9]{2,4})", value)
    if not match:
        return None
    month = int(match.group(1))
    year = match.group(2)
    if len(year) == 2:
        year_value = 2000 + int(year)
    else:
        year_value = int(year)
    return year_value, month


def compute_resultado(
    fecha_consulta: str | None,
    fechas_crpc: list[str],
    fecha_vencimiento: str | None,
) -> str | None:
    consulta_dt = parse_fecha_consulta(fecha_consulta)
    if not consulta_dt or not fechas_crpc:
        return None
    venc_dt = parse_fecha_vencimiento(fecha_vencimiento)
    consulta_months = consulta_dt.year * 12 + consulta_dt.month
    min_months_until_ph = None
    for value in fechas_crpc:
        parsed = parse_crpc_month(value)
        if not parsed:
            continue
        year_value, month_value = parsed
        crpc_months = year_value * 12 + month_value
        ph_due_months = crpc_months + 60
        months_until_ph = ph_due_months - consulta_months
        if min_months_until_ph is None or months_until_ph < min_months_until_ph:
            min_months_until_ph = months_until_ph
        if months_until_ph <= 6:
            return "Prueba Hidraulica"
    if venc_dt is None:
        return "Renovación de Oblea"
    if consulta_dt > venc_dt:
        return "Renovación de Oblea"
    if min_months_until_ph is None:
        return None
    return "Equipo Habilitado"


def extract_label_values(lines: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    for line in lines:
        normalized = normalize_text(line)
        matches = list(LABEL_RE.finditer(normalized))
        if not matches:
            continue
        for idx, match in enumerate(matches):
            raw_label = normalize_text(match.group("label")).lower()
            key = LABEL_ALIASES.get(raw_label, raw_label)
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized)
            value = normalized[start:end].strip(" :;-")
            value = clean_value(value)
            if value:
                results[key] = value
    return results


def extract_fecha_crpc(lines: list[str]) -> list[str] | None:
    normalized_lines = [normalize_text(line) for line in lines if line.strip()]
    start_idx = 0
    for idx, line in enumerate(normalized_lines):
        lower = line.lower()
        if "datos cilindro" in lower or "datos del cilindro" in lower:
            start_idx = idx + 1
            break

    section = normalized_lines[start_idx:]
    header_idx = None
    for idx, line in enumerate(section[:10]):
        lower = line.lower()
        if "fecha crpc" in lower or "crpc" in lower:
            header_idx = idx
            break

    values: list[str] = []
    if header_idx is None:
        return None

    search_from = header_idx + 1
    for line in section[search_from : search_from + 20]:
        for match in FECHA_CRPC_RE.finditer(line):
            normalized = normalize_crpc_value(match.group(0))
            if normalized:
                values.append(normalized)

    if not values:
        return None
    return values


def extract_fecha_crpc_from_pdf(pdf) -> list[str]:
    values: list[str] = []
    for page in pdf.pages:
        tables = page.extract_tables() or []
        for table in tables:
            if not table:
                continue
            header_idx = None
            fecha_crpc_idx = None
            for idx, row in enumerate(table):
                cells = [normalize_text(cell or "") for cell in row]
                if not any(cells):
                    continue
                if any("crpc" in cell.lower() for cell in cells):
                    header_idx = idx
                    crpc_indices = [i for i, cell in enumerate(cells) if "crpc" in cell.lower()]
                    for i in crpc_indices:
                        if "fecha" in cells[i].lower():
                            fecha_crpc_idx = i
                            break
                    if fecha_crpc_idx is None and crpc_indices:
                        fecha_crpc_idx = crpc_indices[-1]
                    break
            if header_idx is None or fecha_crpc_idx is None:
                continue
            for row in table[header_idx + 1 :]:
                if fecha_crpc_idx >= len(row):
                    continue
                cell = normalize_text(row[fecha_crpc_idx] or "")
                for match in FECHA_CRPC_RE.finditer(cell):
                    normalized = normalize_crpc_value(match.group(0))
                    if normalized:
                        values.append(normalized)
    return values


def extract_fecha_crpc_from_tables(path: str) -> list[str]:
    try:
        with pdfplumber.open(path) as pdf:
            return extract_fecha_crpc_from_pdf(pdf)
    except Exception:
        return []


def extract_vehicle_from_table(lines: list[str]) -> dict[str, str | None]:
    header_idx = None
    for idx, line in enumerate(lines):
        lower = line.lower()
        if "marca" in lower and "modelo" in lower and "uso" in lower and "dominio" in lower:
            header_idx = idx
            break
    if header_idx is None or header_idx + 1 >= len(lines):
        return {}

    value_line = lines[header_idx + 1]
    if header_idx + 2 < len(lines) and len(value_line.split()) < 5:
        value_line = f"{value_line} {lines[header_idx + 2]}".strip()

    columns = [col.strip() for col in re.split(r"\s{2,}", value_line) if col.strip()]
    if len(columns) >= 5:
        return {
            "marca": columns[0],
            "ano": columns[1],
            "modelo": columns[2],
            "uso": columns[3],
            "dominio": columns[4],
        }

    dominio = None
    ano = None
    dominio_match = PATENTE_RE.search(value_line)
    if dominio_match:
        dominio = dominio_match.group(1)
    ano_match = re.search(r"\b(19|20)\d{2}\b", value_line)
    if ano_match:
        ano = ano_match.group(0)

    return {
        "marca": None,
        "ano": ano,
        "modelo": None,
        "uso": None,
        "dominio": dominio,
    }


def parse_fields(text: str) -> dict[str, str | list[str] | bool | int | None]:
    normalized = normalize_text(text)
    lines = [line for line in text.splitlines() if line.strip()]
    label_values = extract_label_values(lines)

    fecha_consulta = None
    fecha_match = re.search(
        r"Fecha(?:\s+de)?\s+consulta\s*:?(\s*\d{2}[-/]\d{2}[-/]\d{4})",
        normalized,
        re.IGNORECASE,
    )
    if fecha_match:
        fecha_consulta = fecha_match.group(1).strip()

    fecha_vencimiento = None
    venc_match = re.search(
        r"Fecha\s+de\s+vencimiento\s*:?(\s*\d{2}[-/]\d{2}[-/]\d{4})",
        normalized,
        re.IGNORECASE,
    )
    if venc_match:
        fecha_vencimiento = venc_match.group(1).strip()

    consulta_dominio = None
    consulta_match = re.search(
        r"Consulta\s+por\s+Dominio\s*:?([A-Z0-9\-\s]+)",
        normalized,
        re.IGNORECASE,
    )
    if consulta_match:
        raw_value = consulta_match.group(1).strip().upper()
        match = PATENTE_RE.search(raw_value)
        consulta_dominio = match.group(1) if match else raw_value.replace(" ", "")

    vehiculo_section = extract_section(normalized, "Datos del vehiculo", ["Datos del cilindro"])
    vehicle_fields: dict[str, str | None] = {}
    for idx, label in enumerate(VEHICLE_LABELS):
        value = extract_labeled_value(vehiculo_section, label, VEHICLE_LABELS[idx + 1 :])
        vehicle_fields[label.lower()] = value

    if not any(vehicle_fields.values()):
        for idx, label in enumerate(VEHICLE_LABELS):
            value = extract_labeled_value(normalized, label, VEHICLE_LABELS[idx + 1 :])
            if value:
                vehicle_fields[label.lower()] = value

    if not any(vehicle_fields.values()):
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        fallback = extract_vehicle_from_table(lines)
        if fallback:
            vehicle_fields.update({key: fallback.get(key) for key in vehicle_fields.keys()})

    for key in ["marca", "ano", "modelo", "uso", "dominio"]:
        if not vehicle_fields.get(key) and label_values.get(key):
            vehicle_fields[key] = label_values.get(key)

    if not vehicle_fields.get("dominio"):
        dominio_match = PATENTE_RE.search(normalized)
        if dominio_match:
            vehicle_fields["dominio"] = dominio_match.group(1)

    if vehicle_fields.get("ano") and len(vehicle_fields["ano"]) > 4:
        year_match = re.search(r"\b(19|20)\d{2}\b", vehicle_fields["ano"])
        if year_match:
            vehicle_fields["ano"] = year_match.group(0)

    cilindro_section = extract_section(normalized, "Datos del cilindro", [])
    if cilindro_section == normalized:
        cilindro_section = extract_section(normalized, "Datos cilindro", [])

    fecha_crpc_values: list[str] = []
    crpc_match = re.search(
        r"(Fecha\s*CRPC|F\.?\s*CRPC)\s*:?\s*(\d{1,2}\s*/\s*\d{2,4})",
        cilindro_section,
        re.IGNORECASE,
    )
    if crpc_match:
        normalized_value = normalize_crpc_value(crpc_match.group(2).strip())
        if normalized_value:
            fecha_crpc_values.append(normalized_value)
    elif label_values.get("fecha_crpc"):
        normalized_value = normalize_crpc_value(label_values["fecha_crpc"])
        if normalized_value:
            fecha_crpc_values.append(normalized_value)
    else:
        extracted = extract_fecha_crpc(lines)
        if extracted:
            fecha_crpc_values.extend(extracted)

    fecha_crpc_values = [value for value in fecha_crpc_values if value]
    cant_cilindros = len(fecha_crpc_values)
    fecha_crpc = ", ".join(fecha_crpc_values) if fecha_crpc_values else None
    resultado = compute_resultado(fecha_consulta, fecha_crpc_values, fecha_vencimiento)

    coincide = None
    if vehicle_fields.get("dominio") and consulta_dominio:
        coincide = (
            vehicle_fields["dominio"].upper().strip() == consulta_dominio.upper().strip()
        )

    return {
        "fecha_consulta": fecha_consulta,
        "marca": vehicle_fields.get("marca"),
        "ano": vehicle_fields.get("ano"),
        "modelo": vehicle_fields.get("modelo"),
        "uso": vehicle_fields.get("uso"),
        "dominio": vehicle_fields.get("dominio"),
        "fecha_crpc": fecha_crpc,
        "fecha_vencimiento": fecha_vencimiento,
        "consulta_dominio": consulta_dominio,
        "coincide": coincide,
        "resultado": resultado,
        "cant_cilindros": cant_cilindros,
    }


def probe_pdf(path: str) -> PdfTextProbe:
    text, pages_with_text, total_pages = extract_text(path)
    use_ocr, reason = should_use_ocr(text, pages_with_text, total_pages)
    fields = None
    if not use_ocr:
        fields = parse_fields(text)
        table_dates = extract_fecha_crpc_from_tables(path)
        if table_dates:
            fields["fecha_crpc"] = ", ".join(table_dates)
            fields["cant_cilindros"] = len(table_dates)
            fields["resultado"] = compute_resultado(
                fields.get("fecha_consulta"),
                table_dates,
                fields.get("fecha_vencimiento"),
            )
    sample = text[:120].replace("\n", " ").strip()
    return PdfTextProbe(
        path=path,
        char_count=len(text.strip()),
        pages_with_text=pages_with_text,
        total_pages=total_pages,
        use_ocr=use_ocr,
        reason=reason,
        sample=sample,
        fields=fields,
    )


def analyze_pdf_bytes(pdf_bytes: bytes) -> dict[str, str | list[str] | bool | int | None]:
    text, _pages_with_text, _total_pages = extract_text_bytes(pdf_bytes)
    fields = parse_fields(text)
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        table_dates = extract_fecha_crpc_from_pdf(pdf)
    if table_dates:
        fields["fecha_crpc"] = ", ".join(table_dates)
        fields["cant_cilindros"] = len(table_dates)
        fields["resultado"] = compute_resultado(
            fields.get("fecha_consulta"),
            table_dates,
            fields.get("fecha_vencimiento"),
        )
    return fields


def probe_folder(folder: str) -> list[PdfTextProbe]:
    base = Path(folder)
    results: list[PdfTextProbe] = []
    for path in sorted(base.glob("*.pdf")):
        results.append(probe_pdf(str(path)))
    return results


def summarize_probes(probes: Iterable[PdfTextProbe]) -> str:
    probes = list(probes)
    if not probes:
        return "No se encontraron PDFs."

    headers = [
        "Archivo",
        "Fecha consulta",
        "Marca",
        "Ano",
        "Modelo",
        "Uso",
        "Dominio",
        "Fecha CRPC",
        "Coincide",
        "Resultado",
        "Cant Cilindros",
    ]

    rows: list[list[str]] = []
    for probe in probes:
        fields = probe.fields or {}
        coincide_value = ""
        if fields.get("coincide") is True:
            coincide_value = "true"
        elif fields.get("coincide") is False:
            coincide_value = "false"
        rows.append(
            [
                Path(probe.path).name,
                fields.get("fecha_consulta") or "",
                fields.get("marca") or "",
                fields.get("ano") or "",
                fields.get("modelo") or "",
                fields.get("uso") or "",
                fields.get("dominio") or "",
                fields.get("fecha_crpc") or "",
                coincide_value,
                fields.get("resultado") or "",
                str(fields.get("cant_cilindros") or 0),
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))

    def format_row(items: list[str]) -> str:
        return "| " + " | ".join(
            str(item).ljust(widths[idx]) for idx, item in enumerate(items)
        ) + " |"

    sep = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    output = [sep, format_row(headers), sep]
    for row in rows:
        output.append(format_row(row))
    output.append(sep)
    return "\n".join(output)


if __name__ == "__main__":
    probes = probe_folder("debug/pdfs")
    print(summarize_probes(probes))
