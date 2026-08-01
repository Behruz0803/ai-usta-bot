import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update, BotCommand, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from ai_engine import (
    matn_javob, media_javob, tarixni_tozala, set_joylashuv
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

LOG_PAPKA = "foydalanuvchi_xabarlari"
os.makedirs(LOG_PAPKA, exist_ok=True)

# Admin guruh ID (Railway Variables da o'rnatilgan)
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")

MAX_MEDIA = 20 * 1024 * 1024

BTN_YORDAM = "❓ Qanday ishlataman?"
BTN_YANGI = "🔄 Yangi muammo"
BTN_JOY = "📍 Joylashuvni yuborish"

def klaviatura():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_JOY, request_location=True)],
            [KeyboardButton(BTN_YANGI), KeyboardButton(BTN_YORDAM)],
        ],
        resize_keyboard=True
    )

def user_info(update):
    u = update.effective_user
    username = f"@{u.username}" if u.username else "(username yo'q)"
    return f"{u.first_name or ''} {u.last_name or ''} {username} [ID: {u.id}]"

def chiroyli_log(user_str, tur, matn=""):
    chiziq = "═" * 60
    print(f"\n{chiziq}\n👤 {user_str}\n📨 Tur: {tur}")
    if matn:
        print(f"💬 Matn: {matn}")
    print(chiziq)

def yangi_fayl_nomi(user_id, kengaytma):
    vaqt = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{LOG_PAPKA}/{user_id}_{vaqt}.{kengaytma}"

def manzilni_aniqla(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"format": "json", "lat": lat, "lon": lon, "accept-language": "uz,ru,en"}
    headers = {"User-Agent": "AIUstaBot/1.0"}
    data = requests.get(url, params=params, headers=headers, timeout=10).json()
    manzil = data.get("display_name", "")
    return ", ".join(manzil.split(",")[:4]) if manzil else ""

async def xavfsiz_typing(context, chat_id):
    try:
        await context.bot.send_chat_action(chat_id, action="typing")
    except Exception as e:
        print(f"(typing belgisi yuborilmadi: {e})")

async def guruhga_yubor(context, user_str, tur, matn="", fayl_path=None):
    """Foydalanuvchi xabarini admin guruhga yuborish"""
    if not LOG_CHAT_ID:
        return
    try:
        caption = f"👤 {user_str}\n📨 {tur}"
        if matn:
            qisqa = matn[:800] + "..." if len(matn) > 800 else matn
            caption += f"\n💬 {qisqa}"

        if fayl_path and os.path.exists(fayl_path):
            with open(fayl_path, "rb") as f:
                if fayl_path.endswith((".jpg", ".jpeg", ".png")):
                    await context.bot.send_photo(LOG_CHAT_ID, photo=f, caption=caption)
                elif fayl_path.endswith(".ogg"):
                    await context.bot.send_voice(LOG_CHAT_ID, voice=f, caption=caption)
                elif fayl_path.endswith((".mp4", ".mov")):
                    await context.bot.send_video(LOG_CHAT_ID, video=f, caption=caption)
                elif fayl_path.endswith(".mp3"):
                    await context.bot.send_audio(LOG_CHAT_ID, audio=f, caption=caption)
                else:
                    await context.bot.send_document(LOG_CHAT_ID, document=f, caption=caption)
        else:
            await context.bot.send_message(LOG_CHAT_ID, caption)
    except Exception as e:
        print(f"(Guruhga yuborishda xato: {e})")

async def ai_javobini_yubor(context, javob):
    """AI javobini admin guruhga yuborish"""
    if not LOG_CHAT_ID:
        return
    try:
        matn = f"🤖 AI javobi:\n{javob}"
        if len(matn) > 4000:
            matn = matn[:4000] + "\n...(qisqartirildi)"
        await context.bot.send_message(LOG_CHAT_ID, matn)
    except Exception as e:
        print(f"(AI javobini yuborishda xato: {e})")

async def media_ishla(update, context, fayl_id, kengaytma, tur, izoh=""):
    user_id = update.effective_user.id
    user_str = user_info(update)
    await xavfsiz_typing(context, update.effective_chat.id)
    path = None
    try:
        fayl = await context.bot.get_file(fayl_id)
        path = yangi_fayl_nomi(user_id, kengaytma)
        await fayl.download_to_drive(path)
        print(f"💾 Saqlandi: {path}")

        tur_emoji = {"rasm": "📸 RASM", "ovoz": "🎤 OVOZ", "video": "🎬 VIDEO"}
        await guruhga_yubor(context, user_str, tur_emoji.get(tur, tur), izoh, path)

        javob = media_javob(user_id, path, izoh, tur)
        print(f"🤖 AI javobi:\n{javob}\n")
        await update.message.reply_text(javob)

        await ai_javobini_yubor(context, javob)
    except Exception as e:
        logger.error(f"{tur} xatosi: {e}")
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)[:200]}")

# ═══════════════════════════════════════
# MATNLAR
# ═══════════════════════════════════════

SALOM = """
🔧 *AI USTA* — uy texnikangiz uchun aqlli yordamchi

Men buzilgan texnikangizni *tashxis qilaman* va nima qilish 
kerakligini aytaman.

*🛠 Nimalarga yordam beraman:*
❄️ Muzlatgich  📺 Televizor  🧹 Chang yutgich
👕 Kir yuvish mashinasi  💻 Kompyuter  🔌 Dazmol, fen, kolonka...

*✅ Men nima qila olaman:*
• Nima buzilganini aniqlayman
• O'zingiz tuzatishingiz mumkinmi — aytaman
• Bosqichma-bosqich ko'rsatma beraman
• Kerakli ehtiyot qism nomini topaman
• Yaqin ustaxona va taxminiy narxni aytaman

*📲 Qanday murojaat qilasiz (istalgan usulda):*
✍️ Yozing  📸 Rasm  🎤 Ovozli xabar  
🎬 Video  ⭕️ Dumaloq video  📍 Joylashuv

*💡 Boshlash uchun oddiy qilib yozing, masalan:*
_"Muzlatgichim sovutmayapti"_
_"Chang yutgichim shovqin qilyapti"_

Texnikani bilmasangiz ham xavotir olmang — 
men *oddiy savollar* beraman, siz javob berasiz! 👇
"""

YORDAM = """
📖 *Qanday foydalanish kerak*

*1-qadam:* Muammoni ayting
Istalgan usulda — yozma, ovozli, rasm yoki video.

*2-qadam:* Savollarga javob bering
Men oddiy savollar beraman:
_"Qurilma umuman yonayaptimi?"_
_"Qanday tovush chiqaryapti?"_

*3-qadam:* Tashxis va yechim oling
Nima buzilgani va nima qilish kerakligini aytaman.

━━━━━━━━━━━━━━━━━━━━

*📸 Yaxshi rasm qanday olinadi:*
• Qurilmani to'liq suratga oling
• Model yorlig'ini (stiker) alohida oling
• Buzilgan joyni yaqindan oling
• Yorug' joyda suratga oling

*🎤 Ovozli xabar:*
Texnik so'zlarni bilmasangiz — shunchaki 
*o'z so'zingiz bilan gapiring!*

*🎬 Video (maks 20 MB):*
G'alati tovush yoki harakat bo'lsa juda foydali.

*📍 Joylashuv:*
Yuborsangiz — yaqin ustaxona va narxlarni topaman.

━━━━━━━━━━━━━━━━━━━━

*Buyruqlar:*
/start — Boshlash
/yangi — Yangi muammoga o'tish
/yordam — Shu sahifa

⚡️ *Xavfsizlik:* elektr jihozlari bilan ishdan oldin 
albatta rozetkadan uzing!
"""

# ═══════════════════════════════════════
# BUYRUQLAR
# ═══════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chiroyli_log(user_info(update), "🚀 START")
    await update.message.reply_text(
        SALOM, parse_mode="Markdown", reply_markup=klaviatura()
    )

async def yangi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tarixni_tozala(update.effective_user.id)
    await update.message.reply_text(
        "🔄 *Yangi muammo boshlandi!*\n\n"
        "Nima bo'ldi? Yozing, gapiring yoki rasm yuboring 👇",
        parse_mode="Markdown", reply_markup=klaviatura()
    )

async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        YORDAM, parse_mode="Markdown", reply_markup=klaviatura()
    )

# ═══════════════════════════════════════
# XABAR HANDLERLARI
# ═══════════════════════════════════════

async def matn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matn = update.message.text

    if matn == BTN_YORDAM:
        return await yordam(update, context)
    if matn == BTN_YANGI:
        return await yangi(update, context)

    user_id = update.effective_user.id
    user_str = user_info(update)
    chiroyli_log(user_str, "✍️ MATN", matn)
    await guruhga_yubor(context, user_str, "✍️ MATN", matn)

    await xavfsiz_typing(context, update.effective_chat.id)
    try:
        javob = matn_javob(user_id, matn)
        print(f"🤖 AI javobi:\n{javob}\n")
        await update.message.reply_text(javob)
        await ai_javobini_yubor(context, javob)
    except Exception as e:
        logger.error(f"Matn xatosi: {e}")
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)[:200]}")

async def rasm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    izoh = update.message.caption or ""
    chiroyli_log(user_info(update), "📸 RASM", izoh)
    await media_ishla(update, context, update.message.photo[-1].file_id,
                      "jpg", "rasm", izoh)

async def ovoz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chiroyli_log(user_info(update), "🎤 OVOZLI XABAR")
    await media_ishla(update, context, update.message.voice.file_id,
                      "ogg", "ovoz")

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chiroyli_log(user_info(update), "🎵 AUDIO FAYL")
    await media_ishla(update, context, update.message.audio.file_id,
                      "mp3", "ovoz", update.message.caption or "")

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    izoh = update.message.caption or ""
    chiroyli_log(user_info(update), "🎬 VIDEO", izoh)
    if video.file_size and video.file_size > MAX_MEDIA:
        return await update.message.reply_text(
            "⚠️ Video juda katta (20 MB dan ortiq).\n"
            "Qisqaroq video yuboring yoki muammoli joyni rasmga oling."
        )
    await media_ishla(update, context, video.file_id, "mp4", "video", izoh)

async def dumaloq_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vn = update.message.video_note
    chiroyli_log(user_info(update), "⭕️ DUMALOQ VIDEO")
    if vn.file_size and vn.file_size > MAX_MEDIA:
        return await update.message.reply_text("⚠️ Video juda katta. Qisqaroq yuboring.")
    await media_ishla(update, context, vn.file_id, "mp4", "video")

async def fayl_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    mime = (doc.mime_type or "").lower()
    izoh = update.message.caption or ""

    if mime.startswith("image/"):
        tur, kengaytma = "rasm", "jpg"
    elif mime.startswith("video/"):
        tur, kengaytma = "video", "mp4"
    elif mime.startswith("audio/"):
        tur, kengaytma = "ovoz", "mp3"
    else:
        return await update.message.reply_text(
            "⚠️ Bu fayl turini tushunmayman.\n"
            "Iltimos, rasm, video yoki ovozli xabar yuboring."
        )

    chiroyli_log(user_info(update), f"📎 FAYL ({tur})", izoh)
    if doc.file_size and doc.file_size > MAX_MEDIA:
        return await update.message.reply_text("⚠️ Fayl juda katta (20 MB dan ortiq).")
    await media_ishla(update, context, doc.file_id, kengaytma, tur, izoh)

async def joylashuv_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    loc = update.message.location
    user_str = user_info(update)
    chiroyli_log(user_str, "📍 JOYLASHUV", f"{loc.latitude}, {loc.longitude}")

    await guruhga_yubor(
        context, user_str, "📍 JOYLASHUV",
        f"Lat: {loc.latitude}, Lon: {loc.longitude}"
    )

    await update.message.reply_text("📍 Manzilni aniqlayapman...")
    try:
        manzil = manzilni_aniqla(loc.latitude, loc.longitude)
        if not manzil:
            return await update.message.reply_text(
                "⚠️ Manzil aniqlanmadi. Shahringiz nomini yozib yuboring."
            )
        set_joylashuv(user_id, manzil)
        print(f"📍 Manzil: {manzil}")
        await update.message.reply_text(
            f"✅ Joylashuv saqlandi:\n*{manzil}*\n\n"
            "Endi usta yoki ehtiyot qism kerak bo'lsa — "
            "yaqin atrofdagi joylarni topib beraman! 🔧",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Joylashuv xatosi: {e}")
        await update.message.reply_text("⚠️ Xatolik. Shahringiz nomini yozib yuboring.")

async def boshqa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤔 Bu turdagi xabarni tushunmayman.\n\n"
        "Menga quyidagilarni yuboring:\n"
        "✍️ Matn  📸 Rasm  🎤 Ovoz  🎬 Video  📍 Joylashuv\n\n"
        "Yordam uchun /yordam"
    )

# ═══════════════════════════════════════
# ISHGA TUSHIRISH
# ═══════════════════════════════════════

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "🔧 Botni boshlash"),
        BotCommand("yangi", "🔄 Yangi muammo"),
        BotCommand("yordam", "❓ Qanday foydalanish"),
    ])

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN o'rnatilmagan!")
        return

    print("🤖 AI Usta bot ishga tushmoqda...")
    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yangi", yangi))
    app.add_handler(CommandHandler("yordam", yordam))

    app.add_handler(MessageHandler(filters.PHOTO, rasm_handler))
    app.add_handler(MessageHandler(filters.VOICE, ovoz_handler))
    app.add_handler(MessageHandler(filters.AUDIO, audio_handler))
    app.add_handler(MessageHandler(filters.VIDEO, video_handler))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, dumaloq_video_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, fayl_handler))
    app.add_handler(MessageHandler(filters.LOCATION, joylashuv_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, matn_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL | filters.CONTACT, boshqa_handler))

    print("✅ Bot tayyor! Telegram'da sinab ko'ring.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
