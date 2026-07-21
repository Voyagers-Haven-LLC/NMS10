"""Shared image intake for base photos.

Both the admin panel and the public submission flow upload base images through
this module, so processing is identical everywhere: validate the type, cap the
raw size, auto-orient from EXIF, strip metadata, downscale, and re-encode to a
web-friendly progressive JPEG under MEDIA_DIR/<base_id>/<uuid>.jpg.

Keeping this in one place means a 12 MB phone photo can't blow up the Pi's disk
no matter which entry point it comes in through."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

# What browsers/phones actually send for screenshots. We re-encode everything
# to JPEG on the way out regardless, so this is just the accept gate.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

MAX_UPLOAD_BYTES = 12 * 1024 * 1024   # reject the raw upload above this
MAX_EDGE = 2560                       # downscale so the long edge <= this
JPEG_QUALITY = 85
# Flatten transparency onto the NMS-dark background instead of white.
FLATTEN_BG = (11, 15, 20)


def _read_capped(file: UploadFile) -> bytes:
    # Read one byte past the cap so we can tell "exactly at limit" from "over".
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"image too large ({MAX_UPLOAD_BYTES // (1024 * 1024)}MB max)")
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    return data


def _has_alpha(img) -> bool:
    """True if the image carries real transparency."""
    if img.mode in ("RGBA", "LA", "PA"):
        return True
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False


def _process_and_save(
    dest_dir: Path,
    file: UploadFile,
    max_edge: int = MAX_EDGE,
    keep_alpha: bool = False,
) -> Path:
    """Validate, normalize, and store one image under dest_dir. Returns the
    on-disk path; the caller builds the public URL from it.

    keep_alpha=True (logos/icons) preserves transparency and saves PNG, so a
    transparent emblem stays transparent. keep_alpha=False (base screenshots)
    flattens onto the dark UI background and saves a smaller JPEG."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported image type: {file.content_type}")

    raw = _read_capped(file)
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="could not read image file")

    # Respect the camera's EXIF orientation, then re-encoding drops all metadata.
    img = ImageOps.exif_transpose(img)

    transparent = keep_alpha and _has_alpha(img)
    if transparent:
        # Keep the alpha channel intact — no background painted behind it.
        img = img.convert("RGBA")
    elif img.mode in ("RGBA", "LA", "P"):
        # Opaque target: flatten any alpha onto the dark UI background.
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, FLATTEN_BG)
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    img.thumbnail((max_edge, max_edge), Image.LANCZOS)

    dest_dir.mkdir(parents=True, exist_ok=True)
    if transparent:
        dest = dest_dir / f"{uuid.uuid4().hex}.png"
        img.save(dest, "PNG", optimize=True)
    else:
        dest = dest_dir / f"{uuid.uuid4().hex}.jpg"
        img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return dest


def save_processed_image(base_id: str, file: UploadFile) -> Path:
    """Store a base photo. Public URL: /media/<base_id>/<name>."""
    return _process_and_save(config.MEDIA_DIR / base_id, file)


# Community logos live under an `_civ/` subfolder of the same media root, served
# by the same /media mount. slugify() only ever emits [a-z0-9-], so `_civ` can
# never collide with a base id — no extra static mount or proxy rule needed.
COMMUNITY_MEDIA_SUBDIR = "_civ"
LOGO_MAX_EDGE = 640  # logos are emblems, not screenshots — keep them small


def save_community_logo(community_id: str, file: UploadFile) -> Path:
    """Store a community logo. Public URL: /media/_civ/<community_id>/<name>.
    Transparency is preserved (icons stay cut-out, no background box)."""
    dest_dir = config.MEDIA_DIR / COMMUNITY_MEDIA_SUBDIR / community_id
    return _process_and_save(dest_dir, file, max_edge=LOGO_MAX_EDGE, keep_alpha=True)


def community_logo_rel(community_id: str, dest: Path) -> str:
    return f"/media/{COMMUNITY_MEDIA_SUBDIR}/{community_id}/{dest.name}"
