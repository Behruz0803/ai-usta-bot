"""AI Usta bot — Vercel serverless WEBHOOK nuqtasi (24/7).

Telegram yangilanishlarni POST /api/webhook ga yuboradi.
Har bir so'rov: update -> PTB process_update -> javob "ok".

Kerakli env:
  TELEGRAM_TOKEN  — bot tokeni (BotFather)
  GEMINI_API_KEY  — Google Gemini kaliti
  WEBHOOK_SECRET  — ixtiyoriy, webhook xavfsizlik tokeni
  WEBHOOK_URL     — ixtiyoriy; bo'lmasa VERCEL_URL'dan olinadi
  LOG_CHAT_ID     — ixtiyoriy, log guruh ID'si
"""
import asyncio
import json
import logging
import os
import threading
from collections import deque

from telegram import Update
from telegram.ext import ApplicationBuilder

import bot as bot_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-usta.webhook")

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# ── Yagona doimiy event-loop (alohida threadda) ─────────────────────
_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True, name="ptb-loop").start()


def _run(coro, timeout=55):
    """Koronani doimiy loop'da sinxron bajarish."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout=timeout)


_app = None
_ready = False
_seen = deque(maxlen=1024)


async def _build_and_init():
    app = ApplicationBuilder().token(TOKEN).updater(None).build()
    bot_module.register_handlers(app)
    await app.initialize()
    await app.start()
    await bot_module.post_init(app)          # /start /yangi /yordam buyruqlari
    return app


def _webhook_url():
    base = os.getenv("WEBHOOK_URL") or os.getenv("VERCEL_URL", "")
    if base and not base.startswith("http"):
        base = "https://" + base
    return f"{base}/api/webhook"


def _ensure_ready():
    global _app, _ready
    if _ready:
        return
    _app = _run(_build_and_init())
    url = _webhook_url()
    if url and TOKEN:
        _run(_app.bot.set_webhook(
            url=url,
            secret_token=WEBHOOK_SECRET or None,
            allowed_updates=Update.ALL_TYPES,
        ))
        logger.info("Webhook o'rnatildi: %s", url)
    _ready = True


def handler(request):
    """Vercel Python entry point."""
    if request.method == "GET":              # health-check
        return json.dumps({"status": "ok", "bot": "ai-usta", "mode": "webhook"}), 200

    if request.method != "POST":
        return "method not allowed", 405

    # Telegram webhook secret tekshiruvi
    if WEBHOOK_SECRET:
        got = request.headers.get("x-telegram-bot-api-secret-token", "")
        if got != WEBHOOK_SECRET:
            return "forbidden", 403

    if not TOKEN:
        return "TELEGRAM_TOKEN not set", 500

    try:
        _ensure_ready()
        body = request.body
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        data = json.loads(body)
    except Exception:
        logger.exception("update'ni o'qib bo'lmadi")
        return "bad request", 400

    update_id = data.get("update_id")
    if update_id in _seen:                   # Telegram retry'dan himoya
        return "ok", 200
    _seen.append(update_id)

    try:
        update = Update.de_json(data, _app.bot)
        _run(_app.process_update(update))
    except Exception:
        logger.exception("update processing error, update_id=%s", update_id)
    return "ok", 200
