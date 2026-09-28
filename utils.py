import gzip
import zlib

def safe_decode_bytes(val):
    if not isinstance(val, bytes):
        return val

    if val.startswith(b"\x1f\x8b"):
        try:
            val = gzip.decompress(val)
        except Exception:
            pass

    elif val.startswith(b"\x78"):
        try:
            val = zlib.decompress(val)
        except Exception:
            pass

    for encoding in ("utf-8", "cp1250", "latin-1"):
        try:
            return val.decode(encoding)
        except UnicodeDecodeError:
            continue

    return val.decode("utf-8", errors="replace")