"""POST /api/query — ochiq veb-interfeys uchun JSON endpoint.

Nega alohida fayl: Vercel har bir Python faylini o'z funksiyasi deb biladi va
o'z ichidagi `app` ni qidiradi. Rewrite'larga tayanmaymiz — "/" rewrite'i
avval "?info=1" debug manzilini ham yutib yuborgan edi.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from api.index import app  # noqa: F401  (WSGI entrypoint sifatida qayta eksport)


def _app_alias(environ, start_response):
    return app(environ, start_response)


# Vercel `app` yoki `handler` ni qidiradi — ikkalasini ham beramiz.
def handler(environ, start_response):  # noqa: D401
    return app(environ, start_response)
