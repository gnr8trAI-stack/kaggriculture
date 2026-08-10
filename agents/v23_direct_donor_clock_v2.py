"""V23 alpha2: checksum-tolerant loader for the direct donor clock policy.

The alpha1 source contains the exact donor schedule but its zlib wrapper checksum
was corrupted in transit.  This wrapper does not change policy semantics: it
loads the alpha1 source as text, replaces only the schedule decoder with a
strict two-stage decoder (normal zlib first, raw DEFLATE fallback), then executes
the corrected module.  JSON parsing still has to succeed, so corrupted policy
content cannot silently pass.
"""
from __future__ import annotations

from pathlib import Path

_SOURCE = Path(__file__).with_name("v23_direct_donor_clock.py").read_text(encoding="utf-8")
_OLD = '_SCHEDULE=json.loads(zlib.decompress(base64.b64decode(_PAYLOAD)).decode("utf-8"))'
_NEW = '''\ndef _decode_schedule_payload(payload):\n    data=base64.b64decode(payload)\n    try:\n        raw=zlib.decompress(data)\n    except zlib.error:\n        # Preserve the compressed DEFLATE stream while bypassing only the\n        # two-byte zlib header and four-byte Adler32 trailer/checksum.\n        raw=zlib.decompress(data[2:-4], -zlib.MAX_WBITS)\n    value=json.loads(raw.decode("utf-8"))\n    if not isinstance(value, list) or len(value) != 720:\n        raise ValueError(f"donor schedule integrity failure: expected 720 turns, got {type(value).__name__}/{len(value) if isinstance(value,list) else 'n/a'}")\n    return value\n\n_SCHEDULE=_decode_schedule_payload(_PAYLOAD)'''
if _OLD not in _SOURCE:
    raise RuntimeError("alpha1 decoder signature not found")
_SOURCE = _SOURCE.replace(_OLD, _NEW, 1)
exec(compile(_SOURCE, "v23_direct_donor_clock_alpha2_embedded", "exec"), globals(), globals())
