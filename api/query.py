"""POST /api/query — ochiq veb-interfeys uchun JSON endpoint.

Alohida fayl: Vercel rewrite'lariga bog'liq bo'lmasin (avval "/" rewrite'i
?info=1 ni ham yutib yuborgan edi). Mantiq api/index.py da.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from api.index import app  # noqa: E402,F401  (WSGI entrypoint)
