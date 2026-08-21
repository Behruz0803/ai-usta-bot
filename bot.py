import os
import logging
import tempfile
import httpx
from datetime import datetime
from dotenv import load_dotenv

from telegram import (
    Update, BotCommand, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from ai_engine import (
    matn_javob, media_javob, tarixni_tozala, set_joylashuv, get_joylashuv
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════
# GURUH ID RAQAMINI PARSING QILISH
# ═══════════════════════════════════════
LOG_CHAT_ID_STR = os.getenv("LOG_CHAT_ID")
LOG_CHAT_ID = None
if LOG_CHAT_ID_STR:
    try:
        LOG_CHAT_ID = int(LOG_CHAT_ID_STR)
    except ValueError:
        LOG_CHAT_ID = LOG_CHAT_ID_STR

MAX_MEDIA = 20 * 1024 * 1024  # 20 MB

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


def inline_tashxis_klaviatura():
    """Tashxis javoblariga biriktiriladigan inline tugmalar"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Yaqin atrofdan usta topish", callback_data="btn_usta_topish")],
        [InlineKeyboardButton("🛒 Ehtiyot qismlar narxi", callback_data="btn_zapchast_narxi")],
        [InlineKeyboardButton("🔄 Yangi suhbat", callback_data="btn_yangi_suhbat")],
    ])


def user_info(update: Update) -> str:
    u = update.effective_user
    username = f"@{u.username}" if u and u.username else "(username yo'q)"
    first = u.first_name if u and u.first_name else ""
    last = u.last_name if u and u.last_name else ""
    uid = u.id if u else 0
    return f"{first} {last} {username} [ID: {uid}]".strip()


def chiroyli_log(user_str: str, tur: str, matn: str = ""):
    chiziq = "═" * 60
    print(f"\n{chiziq}\n👤 {user_str}\n📨 Tur: {tur}")
    if matn:
        print(f"💬 Matn: {matn}")
    print(chiziq)


async def manzilni_aniqla(lat: float, lon: float) -> str:
    """Async HTTP geocoding orqali manzilni aniqlash (httpx)"""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"format": "json", "lat": lat, "lon": lon, "accept-language": "uz,ru,en"}
    headers = {"User-Agent": "AIUstaBot/1.0"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            res = await client_http.get(url, params=params, headers=headers)
            if res.status_code == 200:
                data = res.json()
                manzil = data.get("display_name", "")
                return ", ".join(manzil.split(",")[:4]) if manzil else ""
    except Exception as e:
        logger.error(f"Geocoding xatosi: {e}")
    return ""


async def xavfsiz_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int, action=ChatAction.TYPING):
    """Foydalanuvchiga jarayon ketayotgani haqida ChatAction ko'rsatish"""
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=action)
    except Exception as e:
        logger.warning(f"Typing statusini yuborishda xato: {e}")


async def xavfsiz_reply(update: Update, text: str, reply_markup=None):
    """Markdown rejimida javob yuborish, agar Telegram parse xatosi bersa oddiy matnda yuborish"""
    if not update.message:
        return
    try:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"Markdown parse xatosi, oddiy matnda yuborilmoqda: {e}")
        await update.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Xabar yuborishda kutilmagan xatolik: {e}")
        await update.message.reply_text(text, reply_markup=reply_markup)


async def guruhga_yubor(context: ContextTypes.DEFAULT_TYPE, user_str: str, tur: str, matn: str = "", fayl_path: str = None):
    """Foydalanuvchi xabarini admin guruhiga yuborish"""
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
        logger.warning(f"Admin guruhiga yuborishda xato: {e}")


async def ai_javobini_yubor(context: ContextTypes.DEFAULT_TYPE, javob: str):
    """AI javobini admin guruhiga yuborish"""
    if not LOG_CHAT_ID:
        return
    try:
        matn = f"🤖 AI javobi:\n{javob}"
        if len(matn) > 4000:
            matn = matn[:4000] + "\n...(qisqartirildi)"
        await context.bot.send_message(LOG_CHAT_ID, matn)
    except Exception as e:
        logger.warning(f"AI javobini guruhga yuborishda xato: {e}")


async def media_ishla(update: Update, context: ContextTypes.DEFAULT_TYPE, fayl_id: str, kengaytma: str, tur: str, izoh: str = ""):
    user_id = update.effective_user.id
    user_str = user_info(update)
    chat_id = update.effective_chat.id

    action = ChatAction.RECORD_VOICE if tur == "ovoz" else (ChatAction.UPLOAD_VIDEO if tur == "video" else ChatAction.UPLOAD_PHOTO)
    await xavfsiz_typing(context, chat_id, action=action)

    path = None
    try:
        fayl = await context.bot.get_file(fayl_id)

        # Tempfile ishlatish — Railway диск хотирасини тўлдирмаслик учун
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{kengaytma}") as tmp:
            path = tmp.name

        await fayl.download_to_drive(path)
        logger.info(f"💾 Vaqtinchalik fayl saqlandi: {path}")

        tur_emoji = {"rasm": "📸 RASM", "ovoz": "🎤 OVOZ", "video": "🎬 VIDEO"}
        await guruhga_yubor(context, user_str, tur_emoji.get(tur, tur), izoh, path)

        await xavfsiz_typing(context, chat_id, action=ChatAction.TYPING)

        # Async AI media javobini olish
        javob = await media_javob(user_id, path, izoh, tur)
        print(f"🤖 AI javobi:\n{javob}\n")

        await xavfsiz_reply(update, javob, reply_markup=inline_tashxis_klaviatura())
        await ai_javobini_yubor(context, javob)

    except Exception as e:
        logger.error(f"{tur} xatosi: {e}")
        await xavfsiz_reply(update, f"⚠️ Xatolik yuz berdi: {str(e)[:200]}")

    finally:
        # Disk Leak oldini olish: Vaqtinchalik faylni albatta o'chirish
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"🧹 Vaqtinchalik fayl o'chirildi: {path}")
            except Exception as cleanup_err:
                logger.error(f"Faylni o'chirishda xato ({path}): {cleanup_err}")


# ═══════════════════════════════════════
# INLINE CALLBACK HANDLER
# ═══════════════════════════════════════

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id if query.message else update.effective_chat.id

    if data == "btn_usta_topish":
        chiroyli_log(user_info(update), "🔘 INLINE: USTA TOPISH")
        manzil = get_joylashuv(user_id)
        if not manzil:
            try:
                await query.message.reply_text(
                    "📍 *Yaqin atrofdagi ustalarni topish uchun:*\n\n"
                    "1. Pastdagi *'📍 Joylashuvni yuborish'* tugmasini bosing;\n"
                    "2. Yoki shahringiz va tumaningiz nomini yozib yuboring (masalan: _Toshkent, Chilonzor_).",
                    parse_mode="Markdown",
                    reply_markup=klaviatura()
                )
            except Exception:
                await query.message.reply_text(
                    "📍 Yaqin atrofdagi ustalarni topish uchun pastdagi 'Joylashuvni yuborish' tugmasini bosing yoki shahringiz nomini yozib yuboring.",
                    reply_markup=klaviatura()
                )
            return

        await xavfsiz_typing(context, chat_id, ChatAction.TYPING)
        prompt = f"Mening joylashuvim: {manzil}. Ushbu texnika nosozligi bo'yicha menga eng yaqin ustaxona va usta telefon raqamlarini, manzilini topib ber."
        try:
            javob = await matn_javob(user_id, prompt)
            try:
                await query.message.reply_text(javob, parse_mode="Markdown", reply_markup=inline_tashxis_klaviatura())
            except Exception:
                await query.message.reply_text(javob, reply_markup=inline_tashxis_klaviatura())
            await ai_javobini_yubor(context, javob)
        except Exception as e:
            logger.error(f"Usta topish inline xatosi: {e}")
            await query.message.reply_text(f"⚠️ Xatolik yuz berdi: {str(e)[:200]}")

    elif data == "btn_zapchast_narxi":
        chiroyli_log(user_info(update), "🔘 INLINE: ZAPCHAST NARXI")
        await xavfsiz_typing(context, chat_id, ChatAction.TYPING)
        prompt = "Ushbu nosozlik uchun kerak bo'ladigan ehtiyot qismlar (zapchastlar) nomini, O'zbekistondagi bozor va do'konlardagi (olx.uz, uzum.uz va ehtiyot qism do'konlaridagi) taxminiy narxlarini so'mda topib aytib ber."
        try:
            javob = await matn_javob(user_id, prompt)
            try:
                await query.message.reply_text(javob, parse_mode="Markdown", reply_markup=inline_tashxis_klaviatura())
            except Exception:
                await query.message.reply_text(javob, reply_markup=inline_tashxis_klaviatura())
            await ai_javobini_yubor(context, javob)
        except Exception as e:
            logger.error(f"Zapchast narxi inline xatosi: {e}")
            await query.message.reply_text(f"⚠️ Xatolik yuz berdi: {str(e)[:200]}")

    elif data == "btn_yangi_suhbat":
        chiroyli_log(user_info(update), "🔘 INLINE: YANGI SUHBAT")
        tarixni_tozala(user_id)
        try:
            await query.message.reply_text(
                "🔄 *Suhbat tarixi tozalandi!*\n\n"
                "Yangi texnika yoki nosozlik haqida yozing, rasm, ovoz yoki video yuboring. Men tayyorman! 🔧",
                parse_mode="Markdown",
                reply_markup=klaviatura()
            )
        except Exception:
            await query.message.reply_text(
                "🔄 Suhbat tarixi tozalandi!\nYangi muammo haqida yozing.",
                reply_markup=klaviatura()
            )


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
• Qurilma to'liq suratga olinsin
• Model yorlig'ini (stiker) alohida oling
• Buzilgan joyni yaqinroqdan oling
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
    await xavfsiz_reply(update, SALOM)


async def yangi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tarixni_tozala(update.effective_user.id)
    msg = (
        "🔄 *Yangi muammo boshlandi!*\n\n"
        "Nima bo'ldi? Yozing, gapiring yoki rasm yuboring 👇"
    )
    if update.message:
        try:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=klaviatura())
        except Exception:
            await update.message.reply_text(msg, reply_markup=klaviatura())


async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await xavfsiz_reply(update, YORDAM)


# ═══════════════════════════════════════
# XABAR HANDLERLARI
# ═══════════════════════════════════════

async def matn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matn = update.message.text if update.message else ""

    if matn == BTN_YORDAM:
        return await yordam(update, context)
    if matn == BTN_YANGI:
        return await yangi(update, context)

    user_id = update.effective_user.id
    user_str = user_info(update)
    chat_id = update.effective_chat.id

    chiroyli_log(user_str, "✍️ MATN", matn)
    await guruhga_yubor(context, user_str, "✍️ MATN", matn)

    await xavfsiz_typing(context, chat_id, action=ChatAction.TYPING)
    try:
        # Async AI matn javobini olish
        javob = await matn_javob(user_id, matn)
        print(f"🤖 AI javobi:\n{javob}\n")

        await xavfsiz_reply(update, javob, reply_markup=inline_tashxis_klaviatura())
        await ai_javobini_yubor(context, javob)
    except Exception as e:
        logger.error(f"Matn xatosi: {e}")
        await xavfsiz_reply(update, f"⚠️ Xatolik yuz berdi: {str(e)[:200]}")


async def rasm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    izoh = update.message.caption or ""
    chiroyli_log(user_info(update), "📸 RASM", izoh)
    await media_ishla(update, context, update.message.photo[-1].file_id, "jpg", "rasm", izoh)


async def ovoz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chiroyli_log(user_info(update), "🎤 OVOZLI XABAR")
    await media_ishla(update, context, update.message.voice.file_id, "ogg", "ovoz")


async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chiroyli_log(user_info(update), "🎵 AUDIO FAYL")
    await media_ishla(update, context, update.message.audio.file_id, "mp3", "ovoz", update.message.caption or "")


async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    izoh = update.message.caption or ""
    chiroyli_log(user_info(update), "🎬 VIDEO", izoh)
    if video.file_size and video.file_size > MAX_MEDIA:
        return await xavfsiz_reply(
            update,
            "⚠️ Video juda katta (20 MB dan ortiq).\n"
            "Qisqaroq video yuboring yoki muammoli joyni rasmga oling."
        )
    await media_ishla(update, context, video.file_id, "mp4", "video", izoh)


async def dumaloq_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vn = update.message.video_note
    chiroyli_log(user_info(update), "⭕️ DUMALOQ VIDEO")
    if vn.file_size and vn.file_size > MAX_MEDIA:
        return await xavfsiz_reply(update, "⚠️ Video juda katta. Qisqaroq yuboring.")
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
        return await xavfsiz_reply(
            update,
            "⚠️ Bu fayl turini tushunmayman.\n"
            "Iltimos, rasm, video yoki ovozli xabar yuboring."
        )

    chiroyli_log(user_info(update), f"📎 FAYL ({tur})", izoh)
    if doc.file_size and doc.file_size > MAX_MEDIA:
        return await xavfsiz_reply(update, "⚠️ Fayl juda katta (20 MB dan ortiq).")
    await media_ishla(update, context, doc.file_id, kengaytma, tur, izoh)


async def joylashuv_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    loc = update.message.location
    user_str = user_info(update)
    chat_id = update.effective_chat.id

    chiroyli_log(user_str, "📍 JOYLASHUV", f"{loc.latitude}, {loc.longitude}")

    await guruhga_yubor(
        context, user_str, "📍 JOYLASHUV",
        f"Lat: {loc.latitude}, Lon: {loc.longitude}"
    )

    await xavfsiz_typing(context, chat_id, action=ChatAction.FIND_LOCATION)
    await xavfsiz_reply(update, "📍 Manzilni aniqlayapman...")

    try:
        manzil = await manzilni_aniqla(loc.latitude, loc.longitude)
        if not manzil:
            return await xavfsiz_reply(
                update,
                "⚠️ Manzil aniqlanmadi. Shahringiz nomini yozib yuboring."
            )
        set_joylashuv(user_id, manzil)
        print(f"📍 Manzil saqlandi: {manzil}")
        await xavfsiz_reply(
            update,
            f"✅ Joylashuv saqlandi:\n*{manzil}*\n\n"
            "Endi usta yoki ehtiyot qism kerak bo'lsa — "
            "yaqin atrofdagi joylarni topib beraman! 🔧"
        )
    except Exception as e:
        logger.error(f"Joylashuv xatosi: {e}")
        await xavfsiz_reply(update, "⚠️ Xatolik yuz berdi. Shahringiz nomini yozib yuboring.")


async def boshqa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await xavfsiz_reply(
        update,
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

    app.add_handler(CallbackQueryHandler(callback_query_handler))

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
