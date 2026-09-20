"""SHA-256 Hashing Utilities."""
import hashlib

def sha256_hash(data: str | bytes) -> str:
    """Compute 64-character lowercase hexadecimal SHA-256 digest."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def hash_file(file_path: str) -> str:
    """Compute SHA-256 digest for an entire file in chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()
