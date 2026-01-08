import base64
import io
import os
from typing import Iterable, List

import cv2
import numpy as np
from PIL import Image, ImageOps

from .img_pdf.image_processor import process_image_to_documents
from .img_pdf.pdf_maker import create_single_page_pdf_bytes


MAX_FILES = 6
MAX_DOCS = 6
MAX_FILE_MB = 10
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg"}


def _decode_image_bytes(data: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _encode_image_png(image_bgr: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image_bgr)
    if not ok:
        raise ValueError("No se pudo codificar la imagen.")
    return buffer.tobytes()


def data_url_from_png(data: bytes) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _enhance_full_image(image_bgr: np.ndarray, enhance_mode: str) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    mode = (enhance_mode or "soft").lower()
    if mode == "hard":
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        bin_doc = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            35,
            10,
        )
        return cv2.cvtColor(bin_doc, cv2.COLOR_GRAY2BGR)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(gray)
    cl = cv2.medianBlur(cl, 3)
    return cv2.cvtColor(cl, cv2.COLOR_GRAY2BGR)


def decode_data_url(data_url: str) -> np.ndarray:
    header, _, encoded = data_url.partition(",")
    if not header.startswith("data:image"):
        raise ValueError("Formato de imagen invalido.")
    raw = base64.b64decode(encoded)
    return _decode_image_bytes(raw)


def validate_upload(file_storage) -> None:
    if file_storage.mimetype not in ALLOWED_TYPES:
        raise ValueError(f"Tipo de archivo no soportado: {file_storage.mimetype}")
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"Archivo excede {MAX_FILE_MB}MB.")


def build_previews(files, enhance_mode: str = "soft") -> list[dict]:
    previews: list[dict] = []
    processed_images: list[np.ndarray] = []

    for file_storage in files:
        validate_upload(file_storage)
        data = file_storage.read()
        image = _decode_image_bytes(data)
        full_processed = _enhance_full_image(image, enhance_mode)
        full_data_url = data_url_from_png(_encode_image_png(full_processed))

        docs_left = MAX_DOCS - len(processed_images)
        if docs_left <= 0:
            break

        docs = process_image_to_documents(
            image,
            debug=False,
            debug_prefix="",
            margin_ratio=0.06,
            rotate_portrait=True,
            max_docs=docs_left,
            enhance_mode=enhance_mode,
        )
        for doc in docs:
            processed_images.append(doc)
            if len(processed_images) >= MAX_DOCS:
                break
            previews.append(
                {
                    "id": len(previews),
                    "data_url": data_url_from_png(_encode_image_png(doc)),
                    "full_data_url": full_data_url,
                    "width": doc.shape[1],
                    "height": doc.shape[0],
                }
            )

        if len(processed_images) >= MAX_DOCS:
            break

    if not processed_images:
        raise ValueError("No se pudo extraer ningún documento.")

    return previews


def create_pdf_from_data_urls(data_urls: Iterable[str]) -> tuple[bytes, int]:
    images: list[np.ndarray] = []
    for data_url in data_urls:
        images.append(decode_data_url(data_url))

    if not images:
        raise ValueError("No se recibieron imágenes para generar el PDF.")

    pdf_bytes = create_single_page_pdf_bytes(
        images_bgr=images,
        dpi=300,
        outer_margin_mm=8.0,
        inner_margin_mm_x=8.0,
        inner_margin_mm_y=2.0,
        grid_rows=3,
        grid_cols=2,
    )
    return pdf_bytes, len(images)


def save_previews_to_folder(data_urls: Iterable[str], folder: str) -> List[str]:
    os.makedirs(folder, exist_ok=True)
    paths: list[str] = []
    for idx, data_url in enumerate(data_urls):
        image = decode_data_url(data_url)
        filename = f"img_{idx + 1}.png"
        path = os.path.join(folder, filename)
        cv2.imwrite(path, image)
        paths.append(path)
    return paths


def create_pdf_from_files(image_paths: Iterable[str]) -> tuple[bytes, int]:
    images: list[np.ndarray] = []
    for path in image_paths:
        image = cv2.imread(path)
        if image is None:
            raise ValueError(f"No se pudo leer la imagen {path}")
        images.append(image)

    if not images:
        raise ValueError("No se recibieron imágenes para generar el PDF.")

    pdf_bytes = create_single_page_pdf_bytes(
        images_bgr=images,
        dpi=300,
        outer_margin_mm=8.0,
        inner_margin_mm_x=8.0,
        inner_margin_mm_y=2.0,
        grid_rows=3,
        grid_cols=2,
    )
    return pdf_bytes, len(images)
