"""Shared hardening helpers for image-generation providers."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Callable, Dict, List, Optional, Tuple

import requests
from PIL import Image


class ImageEchoError(ValueError):
    """Raised when generated output appears to echo an input image."""


ECHO_AHASH_MAX_DISTANCE = 6
ECHO_DHASH_MAX_DISTANCE = 8


def build_tryon_prompt(product_title: str, category: str, strict: bool = False) -> str:
    category_hint = {
        "tops": "upper body garment",
        "bottoms": "lower body garment (pants/jeans)",
        "dresses": "full-body dress",
        "outerwear": "outer layer jacket/coat",
    }.get(category, "garment")

    base_prompt = (
        "You are creating a virtual try-on result from two inputs: "
        "image 1 is the person photo, image 2 is the product photo. "
        f"Generate one high-detail photorealistic image of the person wearing the {product_title} ({category_hint}). "
        "Identity lock: preserve the person's face identity, skin tone, body shape, hairstyle, and body proportions. "
        "Scene lock: preserve the camera framing, pose, and background from the person photo. "
        "Garment lock: preserve the product's color, pattern, logos, texture, silhouette, seams, and details exactly from the product photo. "
        "Apply natural drape and realistic garment fit on the person. "
        "Output must be a clean, realistic photo with sharp detail and no collage artifacts."
    )
    if strict:
        base_prompt += _strict_tryon_retry_suffix()
    return base_prompt


def build_studio_prompt(strict: bool = False) -> str:
    prompt = (
        "You are given two images. "
        "Image 1 is the final try-on person image (identity and clothing source). "
        "Image 2 is the studio reference image (pose, background, and style source). "
        "Generate one photorealistic studio result where the output follows the pose, camera style, lighting mood, and background composition of image 2, "
        "while preserving the face identity, body shape, and clothing details from image 1. "
        "Do not change the garment design from image 1. "
        "Do not keep the original background from image 1. "
        "Output must look like a professional studio photo with natural edges and consistent lighting."
    )
    if strict:
        prompt += (
            " CRITICAL RETRY: if the result is too similar to image 1, "
            "strongly transfer pose/background/style from image 2 while keeping identity and clothing from image 1."
        )
    return prompt


def download_and_validate_product_image(
    url: str,
    *,
    timeout_seconds: int,
    logger,
    min_width: int = 120,
    min_height: int = 120,
) -> bytes:
    resp = requests.get(url, timeout=timeout_seconds)
    resp.raise_for_status()
    image_bytes = resp.content

    content_type = (resp.headers.get("Content-Type", "") or "").lower()
    content_length = resp.headers.get("Content-Length")
    if content_type and not content_type.startswith("image/"):
        raise ValueError(
            f"TRYON_PRODUCT_IMAGE_INVALID: expected image content-type, got '{content_type}'"
        )

    width = None
    height = None
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
    except Exception as exc:
        raise ValueError("TRYON_PRODUCT_IMAGE_INVALID: downloaded payload is not a decodable image") from exc

    if not width or not height or width < min_width or height < min_height:
        raise ValueError(
            f"TRYON_PRODUCT_IMAGE_INVALID: product image too small ({width}x{height}), minimum is {min_width}x{min_height}"
        )

    logger.info(
        "Product image downloaded: request_url=%s final_url=%s status=%s content_type=%s content_length=%s bytes=%s width=%s height=%s",
        url,
        resp.url,
        resp.status_code,
        content_type,
        content_length,
        len(image_bytes),
        width,
        height,
    )
    return image_bytes


def compute_reference_hashes(
    person_image: bytes,
    product_image: bytes,
    normalize_fn: Callable[[bytes], bytes],
) -> Dict[str, object]:
    person_norm = normalize_fn(person_image)
    product_norm = normalize_fn(product_image)
    return {
        "person_sha": hashlib.sha256(person_norm).hexdigest(),
        "person_ahash": _average_hash(person_norm),
        "person_dhash": _difference_hash(person_norm),
        "product_sha": hashlib.sha256(product_norm).hexdigest(),
        "product_ahash": _average_hash(product_norm),
        "product_dhash": _difference_hash(product_norm),
    }


def select_best_non_echo_candidate(
    candidates: List[Tuple[bytes, str]],
    *,
    reference_hashes: Dict[str, object],
    normalize_fn: Callable[[bytes], bytes],
    logger,
) -> Tuple[bytes, str]:
    person_sha = reference_hashes.get("person_sha")
    person_ahash = reference_hashes.get("person_ahash")
    person_dhash = reference_hashes.get("person_dhash")
    product_sha = reference_hashes.get("product_sha")
    product_ahash = reference_hashes.get("product_ahash")
    product_dhash = reference_hashes.get("product_dhash")

    scored: List[Tuple[int, bytes, str]] = []
    echo_count = 0
    for raw_bytes, source in candidates:
        normalized = normalize_fn(raw_bytes)
        cand_sha = hashlib.sha256(normalized).hexdigest()
        cand_ahash = _average_hash(normalized)
        cand_dhash = _difference_hash(normalized)

        person_a_distance = _hamming_distance(cand_ahash, person_ahash)
        person_d_distance = _hamming_distance(cand_dhash, person_dhash)
        same_as_person = cand_sha == person_sha or (
            person_a_distance <= ECHO_AHASH_MAX_DISTANCE and person_d_distance <= ECHO_DHASH_MAX_DISTANCE
        )

        product_a_distance = _hamming_distance(cand_ahash, product_ahash)
        product_d_distance = _hamming_distance(cand_dhash, product_dhash)
        same_as_product = cand_sha == product_sha or (
            product_a_distance <= ECHO_AHASH_MAX_DISTANCE and product_d_distance <= ECHO_DHASH_MAX_DISTANCE
        )

        if same_as_person or same_as_product:
            echo_count += 1
            logger.info(
                "echo_rejected event=tryon_candidate_rejected source=%s same_as_person=%s same_as_product=%s person_a=%s person_d=%s product_a=%s product_d=%s",
                source,
                same_as_person,
                same_as_product,
                person_a_distance,
                person_d_distance,
                product_a_distance,
                product_d_distance,
            )
            continue

        score = len(normalized)
        scored.append((score, normalized, source))

    if not scored:
        raise ImageEchoError(
            f"TRYON_OUTPUT_INVALID_OR_ECHO: all {len(candidates)} candidates matched input media (echo_count={echo_count})"
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    _, selected_bytes, selected_source = scored[0]
    return selected_bytes, selected_source


def _average_hash(image_bytes: bytes) -> Optional[int]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            gray = img.convert("L").resize((8, 8), resample)
            pixels = list(gray.getdata())
        avg = sum(pixels) / len(pixels)
        bits = 0
        for idx, px in enumerate(pixels):
            if px >= avg:
                bits |= 1 << idx
        return bits
    except Exception:
        return None


def _difference_hash(image_bytes: bytes) -> Optional[int]:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            gray = img.convert("L").resize((9, 8), resample)
            pixels = list(gray.getdata())
        bits = 0
        bit_index = 0
        for row in range(8):
            row_start = row * 9
            for col in range(8):
                left = pixels[row_start + col]
                right = pixels[row_start + col + 1]
                if left > right:
                    bits |= 1 << bit_index
                bit_index += 1
        return bits
    except Exception:
        return None


def _hamming_distance(left: Optional[int], right: Optional[int]) -> int:
    if left is None or right is None:
        return 64
    return (left ^ right).bit_count()


def _strict_tryon_retry_suffix() -> str:
    return (
        " CRITICAL RETRY: previous output looked like an echo. "
        "Do not return the unchanged person image. "
        "The output must clearly show the provided product worn on the person with natural fit, "
        "while preserving identity and background."
    )
