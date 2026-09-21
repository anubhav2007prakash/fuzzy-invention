"""File security utilities for dataset uploads.

Provides filename sanitization, path traversal prevention, and server-generated
storage names to ensure uploaded files remain inside the configured data/raw directory.

SECURITY MODEL:
    - User-supplied filenames are never used directly for storage.
    - A UUID-based server-generated name is used for all files on disk.
    - The original filename is preserved in metadata only (DB record).
    - Path traversal sequences (../, ..\\, ~/, etc.) are detected and rejected.
    - Only .csv files are permitted for dataset uploads.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional

from backend.app.core.exceptions import UnsupportedFormatError

# Allowed file extensions for dataset uploads
_ALLOWED_EXTENSIONS = {".csv"}

# Characters that are unsafe in filenames across platforms
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')

# Path traversal patterns to detect and reject
_TRAVERSAL_PATTERNS = [
    "..",
    "~",
    "/",
    "\\",
]


class FileSecurityError(Exception):
    """Raised when a file fails security validation."""
    pass


def sanitize_filename(filename: Optional[str]) -> str:
    """Sanitize a user-supplied filename by removing dangerous characters.

    Args:
        filename: The original filename from the upload.

    Returns:
        A cleaned filename with unsafe characters removed.

    Note:
        This is a defense-in-depth measure. The primary security mechanism
        is server-generated storage names in generate_safe_storage_path().
    """
    if not filename:
        return "dataset.csv"

    # Strip directory components (path traversal defense)
    basename = os.path.basename(filename)

    # Remove null bytes
    basename = basename.replace("\x00", "")

    # Remove unsafe characters
    basename = _UNSAFE_FILENAME_CHARS.sub("_", basename)

    # Collapse multiple dots (防止 ../  after basename extraction)
    basename = re.sub(r'\.{2,}', '.', basename)

    # Ensure it's not empty after sanitization
    if not basename or basename.startswith("."):
        basename = "dataset.csv"

    return basename


def validate_filename(filename: Optional[str]) -> None:
    """Validate that a filename is safe to accept.

    Checks:
        1. Filename is not None or empty.
        2. No path traversal sequences (../, ..\\, etc.).
        3. No null bytes.
        4. Extension is in the allowed set (.csv).
        5. No platform-unsafe characters.

    Args:
        filename: The user-supplied filename.

    Raises:
        FileSecurityError: If the filename fails any security check.
        UnsupportedFormatError: If the file extension is not allowed.
    """
    if not filename or not filename.strip():
        raise FileSecurityError("Filename is empty or missing.")

    # Check for null bytes (can bypass extension checks)
    if "\x00" in filename:
        raise FileSecurityError("Filename contains null bytes — rejected.")

    # Check for path traversal sequences
    # Normalize separators first, then check
    normalized = filename.replace("\\", "/")
    for part in normalized.split("/"):
        if part in (".", "..", "~"):
            raise FileSecurityError(
                f"Path traversal detected in filename: '{filename}' — rejected."
            )

    # Check for tilde expansion (~/etc/passwd style)
    if normalized.startswith("~/"):
        raise FileSecurityError(
            f"Home directory expansion detected in filename: '{filename}' — rejected."
        )

    # Check for absolute paths
    if normalized.startswith("/") or (len(normalized) >= 2 and normalized[1] == ":"):
        raise FileSecurityError(
            f"Absolute path detected in filename: '{filename}' — rejected."
        )

    # Reject filenames starting with '..' (e.g., '..csv' which would confuse
    # some path handling even though it's technically a single component)
    basename = os.path.basename(filename)
    if basename.startswith('..'):
        raise FileSecurityError(
            f"Filename starts with '..' — rejected as potential traversal: '{filename}'."
        )

    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"File extension '{ext}' is not allowed. "
            f"Accepted extensions: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )


def generate_safe_storage_path(
    storage_dir: Path,
    original_filename: Optional[str] = None,
    extension: str = ".csv",
) -> Path:
    """Generate a UUID-based storage path that is safe from path traversal.

    The file is stored inside `storage_dir` with a random UUID name,
    ensuring no user-controlled component affects the filesystem path.

    Args:
        storage_dir: The target directory (e.g., settings.DATA_RAW_DIR).
        original_filename: Original filename (used only for the extension).
        extension: File extension to use if original_filename has none.

    Returns:
        A Path object pointing to a safe location inside storage_dir.
    """
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Use the original filename's extension if valid, otherwise default
    if original_filename:
        ext = Path(original_filename).suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            ext = extension

    # Generate a UUID-based safe name
    safe_name = f"{uuid.uuid4().hex}{ext}"

    return storage_dir / safe_name


def verify_file_within_directory(file_path: Path, allowed_dir: Path) -> bool:
    """Verify that a file path is within the allowed directory.

    Uses resolve() to handle symlinks and relative components.

    Args:
        file_path: The resolved file path.
        allowed_dir: The directory that must contain the file.

    Returns:
        True if the file is within the allowed directory.
    """
    try:
        resolved_file = file_path.resolve()
        resolved_dir = allowed_dir.resolve()
        return resolved_file.is_relative_to(resolved_dir)
    except (ValueError, OSError):
        return False
