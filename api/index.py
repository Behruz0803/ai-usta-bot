"""Ochiq veb-interfeys: https://<loyiha>.vercel.app/

Hakamlar brauzerdan ochib, ro'yxatdan o'tmasdan savol berishi uchun.
Telegram webhookiga tegmaydi — /api/webhook va /api/usta o'z ishida qoladi.

Vercel Python runtime'da `app` (WSGI) entrypoint ishlatiladi,
shuning uchun FastAPI o'rniga yengil WSGI ilova yozilgan — sovuq start tez.
"""
import html
import json
import os
import sys
import time
import traceback
from urllib.parse import parse_qs, urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

TEMPLATE = os.path.join(_ROOT, "web", "templates", "index.html")


def _json(status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _run_question(question, timeout=85):
    """uzex.agent.answer ni sinxron chaqirish (WSGI ichida event loop yo'q)."""
    import asyncio
    from uzex.agent import answer
    t0 = time.time()
    try:
        loop = asyncio.new_event_loop()
        try:
            ans = loop.run_until_complete(asyncio.wait_for(answer(question), timeout=timeout))
        finally:
            loop.close()
        return ans, int((time.time() - t0) * 1000)
    except Exception as e:
        traceback.print_exc()
        msg = (
            "⚠️ Javob berishda texnik xatolik yuz berdi.\n"
            "Savolni biroz boshqacha yozib ko'ring.\n\n"
            "⚠️ Техническая ошибка. Попробуйте переформулировать вопрос."
        )
        return msg, int((time.time() - t0) * 1000)


def _handle(method, path, query, body):
    path = (path or "/").rstrip("/") or "/"

    if path in ("/", "/index", "/chat"):
        if method != "GET":
            return 405, "text/plain; charset=utf-8", b"method not allowed"
        try:
            with open(TEMPLATE, "rb") as f:
                data = f.read()
            return 200, "text/html; charset=utf-8", data
        except FileNotFoundError:
            return 500, "text/plain; charset=utf-8", b"template not found"

    if path == "/api/health":
        info = {"status": "ok", "mode": "web", "db": None}
        try:
            from uzex.db import db_is_ready, ensure_db
            info["db_ready"] = db_is_ready()
            p = ensure_db()
            info["db"] = str(p)
            info["db_mb"] = round(p.stat().st_size / 1024 / 1024, 1)
        except Exception as e:
            info["db_error"] = str(e)[:300]
        info["gemini_key"] = bool(os.getenv("UZEX_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY"))
        return _json(200, info)

    if path == "/api/stats":
        try:
            import sqlite3
            from uzex.db import ensure_db
            conn = sqlite3.connect(str(ensure_db()))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM deals")
            deals = cur.fetchone()[0]
            cur.execute("SELECT MIN(deal_date), MAX(deal_date) FROM deals")
            lo, hi = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM contracts")
            contracts = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM participants")
            participants = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM brokers")
            brokers = cur.fetchone()[0]
            conn.close()
            return _json(200, {
                "deals": deals, "contracts": contracts, "participants": participants,
                "brokers": brokers, "period": f"{lo} → {hi}",
            })
        except Exception as e:
            return _json(500, {"error": str(e)[:300]})

    if path == "/api/query":
        if method != "POST":
            return 405, "text/plain; charset=utf-8", b"method not allowed"
        try:
            data = json.loads(body.decode("utf-8") if isinstance(body, bytes) else (body or "{}"))
        except Exception:
            return _json(400, {"error": "bad json"})
        q = (data.get("question") or "").strip()
        if not q:
            return _json(400, {"answer": "Savol bo'sh. / Вопрос пустой."})
        if len(q) > 500:
            q = q[:500]
        ans, ms = _run_question(q)
        return _json(200, {"question": q, "answer": ans, "elapsed_ms": ms})

    return 404, "text/plain; charset=utf-8", b"not found"


_STATUS = {
    200: "200 OK", 400: "400 Bad Request", 404: "404 Not Found",
    405: "405 Method Not Allowed", 500: "500 Internal Server Error",
}


def app(environ, start_response):
    """WSGI entrypoint (Vercel Python runtime)."""
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    body = environ["wsgi.input"].read(length) if length > 0 else b""
    try:
        status, ctype, payload = _handle(method, path, query, body)
    except Exception:
        traceback.print_exc()
        status, ctype, payload = _json(500, {"error": "internal error"})
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    start_response(_STATUS.get(status, f"{status} Unknown"), [
        ("Content-Type", ctype),
        ("Content-Length", str(len(payload))),
        ("Cache-Control", "no-store"),
    ])
    return [payload]


# Lokal sinov: python api/index.py  (yoki: uvicorn — kerak emas)
if __name__ == "__main__":
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def _go(self, method):
            u = urlparse(self.path)
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            body = self.rfile.read(n) if n else b""
            status, ctype, payload = _handle(method, u.path, u.query, body)
            if isinstance(payload, str):
                payload = payload.encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self._go("GET")

        def do_POST(self):
            self._go("POST")

        def log_message(self, *a):
            pass

    port = int(os.getenv("PORT", "8000"))
    print(f"UZEX web: http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
