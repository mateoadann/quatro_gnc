from typing import List

import cv2
import numpy as np


def order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = int(max(height_a, height_b))

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def find_document_contour(edged: np.ndarray, min_area: float = 5000) -> np.ndarray | None:
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            return approx.reshape(4, 2)

    return None


def auto_crop_background(
    img_bgr: np.ndarray,
    diff_thresh: int = 12,
    content_fraction: float = 0.08,
    max_crop_frac: float = 0.35,
) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    if h < 20 or w < 20:
        return img_bgr.copy()

    border = np.concatenate(
        [gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]]
    )
    bg_val = np.median(border)

    def find_cut_from_top(g):
        max_top = int(h * max_crop_frac)
        for y in range(max_top):
            row = g[y, :]
            diff = np.abs(row.astype(np.int16) - int(bg_val))
            if (diff > diff_thresh).mean() > content_fraction:
                return y
        return 0

    def find_cut_from_bottom(g):
        max_bottom = int(h * max_crop_frac)
        for i in range(max_bottom):
            y = h - 1 - i
            row = g[y, :]
            diff = np.abs(row.astype(np.int16) - int(bg_val))
            if (diff > diff_thresh).mean() > content_fraction:
                return y + 1
        return h

    def find_cut_from_left(g):
        max_left = int(w * max_crop_frac)
        for x in range(max_left):
            col = g[:, x]
            diff = np.abs(col.astype(np.int16) - int(bg_val))
            if (diff > diff_thresh).mean() > content_fraction:
                return x
        return 0

    def find_cut_from_right(g):
        max_right = int(w * max_crop_frac)
        for i in range(max_right):
            x = w - 1 - i
            col = g[:, x]
            diff = np.abs(col.astype(np.int16) - int(bg_val))
            if (diff > diff_thresh).mean() > content_fraction:
                return x + 1
        return w

    top = find_cut_from_top(gray)
    bottom = find_cut_from_bottom(gray)
    left = find_cut_from_left(gray)
    right = find_cut_from_right(gray)

    if bottom - top < 10 or right - left < 10:
        return img_bgr.copy()

    return img_bgr[top:bottom, left:right].copy()


def shrink_quad(quad: np.ndarray, factor: float = 0.92) -> np.ndarray:
    quad = quad.astype(np.float32)
    center = quad.mean(axis=0, keepdims=True)
    return center + (quad - center) * factor


def process_image_to_documents(
    image_bgr: np.ndarray,
    debug: bool = False,
    debug_prefix: str = "",
    margin_ratio: float = 0.06,
    rotate_portrait: bool = True,
    max_docs: int = 6,
    enhance_mode: str = "soft",
) -> List[np.ndarray]:
    processed_images: List[np.ndarray] = []

    orig = image_bgr.copy()
    orig_h, orig_w = orig.shape[:2]
    max_dim = 1000

    scale = 1.0
    if max(orig_h, orig_w) > max_dim:
        scale = max_dim / float(max(orig_h, orig_w))
        image_bgr = cv2.resize(
            image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
        )

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(gray, 50, 150)

    if debug:
        cv2.imwrite(f"{debug_prefix}debug_edges_multi.jpg", edged)

    contours, _ = cv2.findContours(
        edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    h, w = edged.shape[:2]
    min_area = 0.05 * h * w

    internal_candidates: list[tuple[float, np.ndarray]] = []
    border_candidates: list[tuple[float, np.ndarray]] = []
    border_eps = 5

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        x, y, cw, ch = cv2.boundingRect(contour)
        touches_border = (
            x <= border_eps
            or y <= border_eps
            or x + cw >= w - border_eps
            or y + ch >= h - border_eps
        )

        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect).astype("float32")
        box_area = cv2.contourArea(box)
        if box_area < min_area:
            continue

        w_box, h_box = rect[1]
        if w_box == 0 or h_box == 0:
            continue

        ratio = max(w_box, h_box) / max(1.0, min(w_box, h_box))
        if not (1.2 <= ratio <= 2.2):
            continue

        if touches_border:
            border_candidates.append((box_area, box))
        else:
            internal_candidates.append((box_area, box))

    if internal_candidates:
        candidates = sorted(internal_candidates, key=lambda x: x[0], reverse=True)
    elif border_candidates:
        candidates = sorted(border_candidates, key=lambda x: x[0], reverse=True)
    else:
        candidates = []

    candidates = candidates[:max_docs]
    if not candidates:
        full_rect = np.array(
            [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
            dtype="float32",
        )
        candidates = [(h * w, full_rect)]

    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:max_docs]

    for idx, (_, cnt) in enumerate(candidates):
        if idx >= max_docs:
            break

        doc_contour = cnt / scale
        doc_contour = shrink_quad(doc_contour, factor=0.92)

        if debug:
            dbg = orig.copy()
            cv2.drawContours(dbg, [doc_contour.astype(int)], -1, (0, 255, 0), 3)
            cv2.imwrite(f"{debug_prefix}debug_contour_doc_{idx+1}.jpg", dbg)

        warped = four_point_transform(orig, doc_contour.astype("float32"))
        warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

        if enhance_mode == "hard":
            blurred = cv2.GaussianBlur(warped_gray, (5, 5), 0)
            bin_doc = cv2.adaptiveThreshold(
                blurred,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                35,
                10,
            )
            warped_final = cv2.cvtColor(bin_doc, cv2.COLOR_GRAY2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(warped_gray)
            cl = cv2.medianBlur(cl, 3)
            warped_final = cv2.cvtColor(cl, cv2.COLOR_GRAY2BGR)

        warped_final = auto_crop_background(
            warped_final,
            diff_thresh=12,
            content_fraction=0.08,
            max_crop_frac=0.35,
        )

        hh, ww = warped_final.shape[:2]
        base = min(hh, ww)
        pad = int(base * margin_ratio)

        warped_padded = cv2.copyMakeBorder(
            warped_final,
            pad,
            pad,
            pad,
            pad,
            borderType=cv2.BORDER_CONSTANT,
            value=(255, 255, 255),
        )

        if rotate_portrait:
            h2, w2 = warped_padded.shape[:2]
            if h2 > w2:
                warped_padded = cv2.rotate(warped_padded, cv2.ROTATE_90_COUNTERCLOCKWISE)

        processed_images.append(warped_padded)

    return processed_images
