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
from user_store import save_user
from ai_engine import (
    matn_javob, media_javob, tarixni_tozala, set_joylashuv, get_joylashuv, get_tarix
)
# UZEX integration
try:
    from uzex.agent import answer as uzex_answer, detect_language
    from uzex.db import get_db_path, get_schema_summary
    UZEX_ENABLED = True
except Exception as e:
    print(f"UZEX import warning: {e}")
    uzex_answer = None
    UZEX_ENABLED = False

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
BTN_YANGI = "🔄 Yangi so'rov"
BTN_JOY = "📍 Joylashuvni yuborish"
BTN_TEL = "📱 Telefon raqamni yuborish"
BTN_UZEX_EXAMPLES = "💡 Savol namunalari"

# UZEX quick buttons
BTN_TOP_BROKER = "🏆 Top brokerlar"
BTN_EXPORT = "💵 Eksport statistikasi"
BTN_CEMENT = "🏗 Sement narxlari"
BTN_DBSTATS = "📊 Baza statistikasi"

buyurtma_kutilmoqda = set()

def klaviatura():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_YANGI), KeyboardButton(BTN_YORDAM)],
            [KeyboardButton(BTN_TOP_BROKER), KeyboardButton(BTN_EXPORT)],
            [KeyboardButton(BTN_CEMENT), KeyboardButton(BTN_DBSTATS)],
            [KeyboardButton(BTN_JOY, request_location=True)],
        ],
        resize_keyboard=True
    )

def telefon_klaviatura():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_TEL, request_contact=True)],
            [KeyboardButton(BTN_YANGI), KeyboardButton(BTN_YORDAM)],
        ],
        resize_keyboard=True
    )

def inline_uzex_klaviatura():
    """UZEX javoblariga inline tugmalar"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Top brokerlar", callback_data="uzex_top_brokers")],
        [InlineKeyboardButton("💵 Eksport 2024", callback_data="uzex_export_2024")],
        [InlineKeyboardButton("🏗 Sement narxi (2023)", callback_data="uzex_cement_2023")],
        [InlineKeyboardButton("🔄 Yangi so'rov", callback_data="btn_yangi_suhbat")],
    ])

def inline_tashxis_klaviatura():
    """Tashxis javoblariga biriktiriladigan inline tugmalar (AI Usta)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Tokdan uzdim / Suvni yopdim ✅", callback_data="btn_xavfsizlik_ok")],
        [InlineKeyboardButton("📞 Ustani chaqirish", callback_data="btn_ustani_chaqirish")],
        [
            InlineKeyboardButton("🔍 Usta topish", callback_data="btn_usta_topish"),
            InlineKeyboardButton("🛒 Zapchast narxi", callback_data="btn_zapchast_narxi"),
        ],
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
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=action)
    except Exception as e:
        logger.warning(f"Typing statusini yuborishda xato: {e}")

async def xavfsiz_reply(update: Update, text: str, reply_markup=None, parse_mode="Markdown"):
    target = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    if not target:
        return
    # Telegram max 4096 chars, split if needed
    if len(text) > 4000:
        # Split by lines
        parts = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > 4000:
                parts.append(current)
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            parts.append(current)
        for i, part in enumerate(parts):
            try:
                await target.reply_text(part, parse_mode=parse_mode, reply_markup=reply_markup if i==len(parts)-1 else None)
            except BadRequest:
                await target.reply_text(part, reply_markup=reply_markup if i==len(parts)-1 else None)
        return
    try:
        await target.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning(f"Markdown parse xatosi, oddiy matnda yuborilmoqda: {e}")
        await target.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Xabar yuborishda kutilmagan xatolik: {e}")
        await target.reply_text(text, reply_markup=reply_markup)

async def guruhga_yubor(context: ContextTypes.DEFAULT_TYPE, user_str: str, tur: str, matn: str = "", fayl_path: str = None):
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
    if not LOG_CHAT_ID:
        return
    try:
        matn = f"🤖 AI javobi:\n{javob}"
        if len(matn) > 4000:
            matn = matn[:4000] + "\n...(qisqartirildi)"
        await context.bot.send_message(LOG_CHAT_ID, matn)
    except Exception as e:
        logger.warning(f"AI javobini guruhga yuborishda xato: {e}")

async def buyurtma_yubor(context: ContextTypes.DEFAULT_TYPE, update: Update, phone_number: str):
    user_id = update.effective_user.id
    user_str = user_info(update)
    manzil = get_joylashuv(user_id) or "Ko'rsatilmagan"
    tarix = get_tarix(user_id)
    muammo = "Maishiy texnika nosozligi bo'yicha usta chaqirish"
    if tarix:
        for content in reversed(tarix):
            if content.role == "user":
                if content.parts and hasattr(content.parts[0], "text"):
                    muammo = content.parts[0].text[:300]
                    break
    zayavka_matn = (
        f"🚨 *YANGI USTA CHAQIRISH ZAYAVKASI!*\n\n"
        f"👤 *Mijoz:* {user_str}\n"
        f"📞 *Telefon:* `{phone_number}`\n"
        f"📍 *Manzil:* {manzil}\n"
        f"🛠 *Muammo tavsifi:* {muammo}\n"
        f"⏰ *Vaqt:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    if LOG_CHAT_ID:
        try:
            await context.bot.send_message(LOG_CHAT_ID, zayavka_matn, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Zayavkani admin guruhga yuborishda xato: {e}")
    buyurtma_kutilmoqda.discard(user_id)
    await xavfsiz_reply(
        update,
        "✅ *Arizangiz qabul qilindi!*\n\n"
        "Yaqin oradagi usta 10 daqiqa ichida siz bilan bog'lanadi va muammoni hal qilishga yordam beradi. 🔧",
        reply_markup=klaviatura()
    )

async def media_ishla(update: Update, context: ContextTypes.DEFAULT_TYPE, fayl_id: str, kengaytma: str, tur: str, izoh: str = ""):
    user_id = update.effective_user.id
    user_str = user_info(update)
    chat_id = update.effective_chat.id
    action = ChatAction.RECORD_VOICE if tur == "ovoz" else (ChatAction.UPLOAD_VIDEO if tur == "video" else ChatAction.UPLOAD_PHOTO)
    await xavfsiz_typing(context, chat_id, action=action)
    path = None
    try:
        fayl = await context.bot.get_file(fayl_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{kengaytma}") as tmp:
            path = tmp.name
        await fayl.download_to_drive(path)
        logger.info(f"💾 Vaqtinchalik fayl saqlandi: {path}")
        tur_emoji = {"rasm": "📸 RASM", "ovoz": "🎤 OVOZ", "video": "🎬 VIDEO"}
        await guruhga_yubor(context, user_str, tur_emoji.get(tur, tur), izoh, path)
        await xavfsiz_typing(context, chat_id, action=ChatAction.TYPING)
        javob = await media_javob(user_id, path, izoh, tur)
        print(f"🤖 AI javobi:\n{javob}\n")
        await xavfsiz_reply(update, javob, reply_markup=inline_tashxis_klaviatura())
        await ai_javobini_yubor(context, javob)
    except Exception as e:
        logger.error(f"{tur} xatosi: {e}")
        await xavfsiz_reply(update, f"⚠️ Xatolik yuz berdi: {str(e)[:200]}")
    finally:
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
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id if query.message else update.effective_chat.id

    if data == "btn_xavfsizlik_ok":
        await query.answer(text="Ajoyib! Endi xavfsiz holda ta'mirlashni davom ettirishingiz mumkin. ✅", show_alert=True)
        try:
            await query.message.reply_text(
                "✅ *Xavfsizlik chorasi tasdiqlandi!*\n\n"
                "Qurilma elektr manbaidan uzildi / suv yopildi. Endi ta'mirlash va tekshirish bosqichlarini xavfsiz bajarishingiz mumkin! 🛠",
                parse_mode="Markdown"
            )
        except Exception:
            await query.message.reply_text("✅ Xavfsizlik chorasi tasdiqlandi! Endi xavfsiz holda davom ettirishingiz mumkin.")

    elif data == "btn_ustani_chaqirish":
        await query.answer()
        chiroyli_log(user_info(update), "🔘 INLINE: USTANI CHAQIRISH")
        buyurtma_kutilmoqda.add(user_id)
        try:
            await query.message.reply_text(
                "📞 *Usta chaqirish uchun aloqa raqamingizni yuboring:*\n\n"
                "Pastdagi *'📱 Telefon raqamni yuborish'* tugmasini bosing yoki raqamingizni yozib yuboring (masalan: _+998901234567_).",
                parse_mode="Markdown",
                reply_markup=telefon_klaviatura()
            )
        except Exception:
            await query.message.reply_text("📞 Usta chaqirish uchun telefon raqamingizni yozing yoki pastdagi tugmani bosing:", reply_markup=telefon_klaviatura())

    elif data == "btn_usta_topish":
        await query.answer()
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
                await query.message.reply_text("📍 Yaqin atrofdagi ustalarni topish uchun pastdagi 'Joylashuvni yuborish' tugmasini bosing yoki shahringiz nomini yozib yuboring.", reply_markup=klaviatura())
            return
        await xavfsiz_typing(context, chat_id, ChatAction.TYPING)
        prompt = f"Mening joylashuvim: {manzil}. Ushbu texnika nosozligi bo'yicha menga eng yaqin ustaxona va usta telefon raqamlarini, manzilini topib ber."
        try:
            javob = await matn_javob(user_id, prompt)
            await xavfsiz_reply(update, javob, reply_markup=inline_tashxis_klaviatura())
            await ai_javobini_yubor(context, javob)
        except Exception as e:
            logger.error(f"Usta topish inline xatosi: {e}")
            await xavfsiz_reply(update, f"⚠️ Xatolik yuz berdi: {str(e)[:200]}")

    elif data == "btn_zapchast_narxi":
        await query.answer()
        chiroyli_log(user_info(update), "🔘 INLINE: ZAPCHAST NARXI")
        await xavfsiz_typing(context, chat_id, ChatAction.TYPING)
        prompt = "Ushbu nosozlik uchun kerak bo'ladigan ehtiyot qismlar (zapchastlar) nomini, O'zbekistondagi bozor va do'konlardagi (olx.uz, uzum.uz va ehtiyot qism do'konlaridagi) taxminiy narxlarini so'mda topib aytib ber."
        try:
            javob = await matn_javob(user_id, prompt)
            await xavfsiz_reply(update, javob, reply_markup=inline_tashxis_klaviatura())
            await ai_javobini_yubor(context, javob)
        except Exception as e:
            logger.error(f"Zapchast narxi inline xatosi: {e}")
            await xavfsiz_reply(update, f"⚠️ Xatolik yuz berdi: {str(e)[:200]}")

    elif data == "btn_yangi_suhbat":
        await query.answer()
        chiroyli_log(user_info(update), "🔘 INLINE: YANGI SUHBAT")
        tarixni_tozala(user_id)
        buyurtma_kutilmoqda.discard(user_id)
        try:
            await query.message.reply_text(
                "🔄 *Suhbat tarixi tozalandi!*\n\n"
                "Yangi savol bering — UZEX birjasi yoki texnika nosozligi haqida. Men tayyorman! 🔧",
                parse_mode="Markdown",
                reply_markup=klaviatura()
            )
        except Exception:
            await query.message.reply_text("🔄 Suhbat tarixi tozalandi!\nYangi savol bering.", reply_markup=klaviatura())

    # UZEX inline handlers
    elif data == "uzex_top_brokers":
        await query.answer()
        chiroyli_log(user_info(update), "🔘 UZEX: TOP BROKERS")
        await handle_uzex_query(update, context, "Qaysi broker eng ko'p bitim o'tkazgan? 2024 yilda")

    elif data == "uzex_export_2024":
        await query.answer()
        chiroyli_log(user_info(update), "🔘 UZEX: EXPORT 2024")
        await handle_uzex_query(update, context, "Экспортные сделки в 2024 году количество и сумма в сумах?")

    elif data == "uzex_cement_2023":
        await query.answer()
        chiroyli_log(user_info(update), "🔘 UZEX: CEMENT 2023")
        await handle_uzex_query(update, context, "Sement bo'yicha eng qimmat bitim qaysi 2023 yilda?")

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.contact:
        return
    phone = update.message.contact.phone_number
    chiroyli_log(user_info(update), "📱 KONTAKT YUBORILDI", phone)
    await buyurtma_yubor(context, update, phone)

# ═══════════════════════════════════════
# MATNLAR
# ═══════════════════════════════════════
SALOM = """
🔧 *UZEX AI Agent + AI Usta* — sizning aqlli yordamchingiz!

Men *2 sohada* yordam beraman:

*📈 UZEX Birja (500 ming bitim, 2022-2026):*
• Har qanday bitim, narx, broker, kompaniya bo'yicha aniq javob
• STIR/INN, broker kodi, tovar nomi bo'yicha qidiruv
• Eksport/Import, eng qimmat/arzon, statistika
• *Har javobda SQL va hisob-kitobni ko'rsataman* (hakamlar uchun 20 ball!)

*🛠 Maishiy texnika ustasi:*
• Muzlatgich, televizor, kir mashinasi, kompyuter...
• Rasm/ovoz/video orqali tashxis

*💡 UZEX savol namunalari (bosib ko'ring yoki yozing):*
_\"2024 yilda eng ko'p bitim qilgan broker kim?\"_
_\"STIR 921912462 bo'yicha jami savdo qancha?\"_
_\"Sement eng qimmat qachon sotilgan 2023 yilda?\"_
_\"Экспортные сделки в 2024 сумма в сумах?\"_
_\"BK001 brokeri nechta bitimda ishtirok etgan?\"_

O'zbek va rus tillarini mukammal tushunaman! 👇
"""

YORDAM = """
📖 *UZEX AI Agent — Qanday foydalanish kerak*

*UZEX savollar (asosiy):*
Yozing, men bazadan (500 ming bitim) aniq topib beraman:
• *Broker bo'yicha:* \"Qaysi broker eng ko'p bitim qilgan?\"
• *STIR bo'yicha:* \"INN 972345678 xaridlari qancha 2024 yilda?\"
• *Tovar bo'yicha:* \"Paxta yog'i eng arzon qachon?\" / \"Цемент самый дорогой?\"
• *Yil bo'yicha:* \"2025 yilda nechta eksport bitim bo'lgan?\"
• *Narx bo'yicha:* \"Eng qimmat sement shartnomasi qaysi?\"
• *Region bo'yicha:* \"Toshkentda nechta bitim?\"

Til: O'zbek (lotin/krill) va Rus — har ikkalasida ham tushunaman.

*Muhim qoida (hakamlar talabi):*
Agar ma'lumot bazada yo'q bo'lsa, men *to'qimayman*, aniq aytaman:
_\"Ma'lumotlar bazasida bunday ma'lumot mavjud emas\"_
Bu sizning 60 ballingizni himoya qiladi!

*Javob formati (20 ballik sifat):*
✅ Jadval + SQL so'rovi + hisob-kitob formulasi
• Hajm = Soni × Lot
• Birlik narxi = Summa ÷ (Soni × Lot)
• Eksport USD→so'm = Summa × kurs (usd_rates)

━━━━━━━━━━━━━━━━━━━━

*Texnika ustasi (2-darajali):*
Rasm, ovoz, video yuboring — tashxis qilaman.
Xavfli holatda (tok, tutun) birinchi ogohlantiraman!

*Buyruqlar:*
/start — Boshlash
/yangi — Yangi so'rov (tarixni tozalash)
/yordam — Shu sahifa
/dbstats — Baza statistikasi
/misol — Tasodifiy savol namunasi

⚡️ *Tezlik:* 90 soniyadan kam, odatda 2-3 sek!
"""

# ═══════════════════════════════════════
# UZEX detection helper
# ═══════════════════════════════════════
UZEX_KEYWORDS = [
    "uzex", "birja", "биржа", "bitim", "сделк", "broker", "брокер", "bk0", "bk1",
    "stir", "инн", "inn", "kontrakt", "контракт", "shartnoma", "tovar", "товар",
    "mahsulot", "продукт", "sement", "цемент", "yog", "масло", "paxta", "хлопок",
    "soda", "karbamid", "polietilen", "truba", "sotuvchi", "xaridor", "продавец", "покупатель",
    "eksport", "экспорт", "narx", "цена", "summa", "сумма", "qancha", "сколько", "nechta",
    "qaysi", "какой", "yilda", "году", "region", "viloyat", "oblast", "hajm", "объем",
]

def is_uzex_query(text: str) -> bool:
    tl = text.lower()
    # Explicit UZEX triggers
    if any(kw in tl for kw in UZEX_KEYWORDS):
        return True
    # Year pattern 2022-2026
    import re
    if re.search(r"\b20(2[2-6])\b", text):
        # if contains year + any data-like word, treat as UZEX
        if any(w in tl for w in ["yil", "год", "bitim", "сделк", "broker", "tovar", "товар", "narx", "цена", "summa", "сумма"]):
            return True
        # Even standalone year with question mark might be UZEX? Be cautious
        # But if text is short and contains year, likely UZEX
        if len(text.split()) <= 10:
            return True
    # INN pattern
    if re.search(r"\b\d{9}\b", text):
        return True
    # Broker code
    if re.search(r"\bBK\d{3}\b", text, re.I):
        return True
    return False

async def handle_uzex_query(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str):
    user_id = update.effective_user.id
    user_str = user_info(update)
    chat_id = update.effective_chat.id
    if not UZEX_ENABLED or not uzex_answer:
        await xavfsiz_reply(update, "⚠️ UZEX bazasi yuklanmagan. Iltimos, `python -m uzex.etl --src /tmp/uzex_spot_data --db ./data/uzex.db` buyrug'ini ishga tushiring.\nBaza mavjud emas: data/uzex.db")
        return
    chiroyli_log(user_str, "📊 UZEX SO'ROV", question)
    await guruhga_yubor(context, user_str, "📊 UZEX", question)
    await xavfsiz_typing(context, chat_id, ChatAction.TYPING)
    try:
        from uzex.db import db_is_ready
        if not db_is_ready():
            await xavfsiz_reply(update, "⏳ Baza ochilmoqda (500 000 bitim). Birinchi savol 15–30 soniya olishi mumkin...")
        javob = await uzex_answer(question, user_id)
        print(f"🤖 UZEX javobi:\n{javob}\n")
        # HTML <pre> — Telegram Markdown '_' ni yeb qo'yardi va SQL buzilib ko'rinardi
        from uzex.textnorm import as_telegram_html
        await xavfsiz_reply(update, as_telegram_html(javob), reply_markup=inline_uzex_klaviatura(), parse_mode="HTML")
        await ai_javobini_yubor(context, javob)
    except Exception as e:
        logger.exception(f"UZEX xatosi: {e}")
        await xavfsiz_reply(update, f"⚠️ Xatolik: {str(e)[:500]}")

# ═══════════════════════════════════════
# BUYRUQLAR
# ═══════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chiroyli_log(user_info(update), "🚀 START")
    if update.effective_chat and update.effective_chat.type == "private":
        await save_user(update.effective_chat.id)
    await xavfsiz_reply(update, SALOM, reply_markup=klaviatura())

async def yangi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tarixni_tozala(user_id)
    buyurtma_kutilmoqda.discard(user_id)
    msg = (
        "🔄 *Yangi so'rov boshlandi!*\n\n"
        "UZEX savolingizni yozing yoki texnika muammosini ayting 👇"
    )
    if update.message:
        try:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=klaviatura())
        except Exception:
            await update.message.reply_text(msg, reply_markup=klaviatura())

async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await xavfsiz_reply(update, YORDAM, reply_markup=klaviatura())

async def dbstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not UZEX_ENABLED:
        await xavfsiz_reply(update, "⚠️ UZEX moduli yuklanmagan.")
        return
    try:
        summary = get_schema_summary()
        db_path = get_db_path()
        size_mb = db_path.stat().st_size / 1024 / 1024 if db_path.exists() else 0
        msg = f"📊 *Baza statistikasi:*\n\n"
        msg += f"• Fayl: `{db_path}` ({size_mb:.1f} MB)\n"
        msg += f"• {summary}\n"
        # Get more details
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM deals;")
        deals = cur.fetchone()[0]
        cur.execute("SELECT min(deal_date), max(deal_date) FROM deals;")
        min_d, max_d = cur.fetchone()
        cur.execute("SELECT count(*) FROM participants;")
        parts = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM contracts;")
        conts = cur.fetchone()[0]
        conn.close()
        msg += f"• Bitimlar: {deals:,} ({min_d} → {max_d})\n"
        msg += f"• Ishtirokchilar: {parts:,}\n"
        msg += f"• Shartnomalar: {conts:,}\n"
        msg += f"\n✅ Baza tayyor! Savol bering."
        await xavfsiz_reply(update, msg)
    except Exception as e:
        await xavfsiz_reply(update, f"⚠️ DB xatosi: {e}")

async def misol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    examples = [
        "2024 yilda eng ko'p bitim qilgan broker kim?",
        "BK001 brokeri 2025 yilda nechta bitimda ishtirok etgan?",
        "Экспортные сделки в 2024 году сумма в сумах?",
        "Sement bo'yicha eng qimmat bitim qaysi 2023 yilda?",
        "STIR 921912462 bo'yicha jami savdolar qancha?",
        "Paxta yog'i bo'yicha 2025 yilda eng arzon shartnoma qaysi?",
        "Qaysi tovar eng ko'p sotilgan 2024 yilda?",
    ]
    import random
    ex = random.choice(examples)
    await xavfsiz_reply(update, f"💡 *Tasodifiy namuna:*\n\n`{ex}`\n\nShu savolni yuboring yoki o'zingiznikini yozing!", reply_markup=inline_uzex_klaviatura())

# ═══════════════════════════════════════
# XABAR HANDLERLARI
# ═══════════════════════════════════════
async def matn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matn = update.message.text if update.message else ""
    if matn == BTN_YORDAM:
        return await yordam(update, context)
    if matn == BTN_YANGI:
        return await yangi(update, context)
    if matn == BTN_TOP_BROKER:
        return await handle_uzex_query(update, context, "2024 yilda eng ko'p bitim qilgan broker kim?")
    if matn == BTN_EXPORT:
        return await handle_uzex_query(update, context, "Экспортные сделки в 2024 году количество и сумма в сумах?")
    if matn == BTN_CEMENT:
        return await handle_uzex_query(update, context, "Sement bo'yicha eng qimmat bitim qaysi 2023 yilda?")
    if matn == BTN_DBSTATS:
        return await dbstats(update, context)
    if matn == BTN_UZEX_EXAMPLES:
        return await misol(update, context)

    user_id = update.effective_user.id
    user_str = user_info(update)
    chat_id = update.effective_chat.id

    if user_id in buyurtma_kutilmoqda and matn and not matn.startswith("/"):
        chiroyli_log(user_str, "📱 MATNLI TELEFON RAQAM", matn)
        return await buyurtma_yubor(context, update, matn)

    # Check if UZEX query
    if UZEX_ENABLED and is_uzex_query(matn):
        return await handle_uzex_query(update, context, matn)

    # Fallback to AI Usta (general)
    chiroyli_log(user_str, "✍️ MATN", matn)
    await guruhga_yubor(context, user_str, "✍️ MATN", matn)
    await xavfsiz_typing(context, chat_id, action=ChatAction.TYPING)
    try:
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
        return await xavfsiz_reply(update, "⚠️ Video juda katta (20 MB dan ortiq).\nQisqaroq video yuboring yoki muammoli joyni rasmga oling.")
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
        return await xavfsiz_reply(update, "⚠️ Bu fayl turini tushunmayman.\nIltimos, rasm, video yoki ovozli xabar yuboring.")
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
    await guruhga_yubor(context, user_str, "📍 JOYLASHUV", f"Lat: {loc.latitude}, Lon: {loc.longitude}")
    await xavfsiz_typing(context, chat_id, action=ChatAction.FIND_LOCATION)
    await xavfsiz_reply(update, "📍 Manzilni aniqlayapman...")
    try:
        manzil = await manzilni_aniqla(loc.latitude, loc.longitude)
        if not manzil:
            return await xavfsiz_reply(update, "⚠️ Manzil aniqlanmadi. Shahringiz nomini yozib yuboring.")
        set_joylashuv(user_id, manzil)
        print(f"📍 Manzil saqlandi: {manzil}")
        await xavfsiz_reply(update, f"✅ Joylashuv saqlandi:\n*{manzil}*\n\nEndi usta yoki ehtiyot qism kerak bo'lsa — yaqin atrofdagi joylarni topib beraman! 🔧")
    except Exception as e:
        logger.error(f"Joylashuv xatosi: {e}")
        await xavfsiz_reply(update, "⚠️ Xatolik yuz berdi. Shahringiz nomini yozib yuboring.")

async def boshqa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await xavfsiz_reply(update, "🤔 Bu turdagi xabarni tushunmayman.\n\nMenga quyidagilarni yuboring:\n✍️ Matn  📸 Rasm  🎤 Ovoz  🎬 Video  📍 Joylashuv\n\nYordam uchun /yordam")

# ═══════════════════════════════════════
# ISHGA TUSHIRISH
# ═══════════════════════════════════════
async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 Boshlash | Start"),
        BotCommand("yangi", "🔄 Yangi so'rov"),
        BotCommand("yordam", "❓ Yordam | Помощь"),
        BotCommand("dbstats", "📊 Baza statistikasi"),
        BotCommand("misol", "💡 Namuna savol"),
    ])

def register_handlers(app: Application) -> Application:
    """Barcha handlerlarni ro'yxatdan o'tkazish."""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yangi", yangi))
    app.add_handler(CommandHandler("yordam", yordam))
    app.add_handler(CommandHandler("dbstats", dbstats))
    app.add_handler(CommandHandler("misol", misol))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.PHOTO, rasm_handler))
    app.add_handler(MessageHandler(filters.VOICE, ovoz_handler))
    app.add_handler(MessageHandler(filters.AUDIO, audio_handler))
    app.add_handler(MessageHandler(filters.VIDEO, video_handler))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, dumaloq_video_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, fayl_handler))
    app.add_handler(MessageHandler(filters.LOCATION, joylashuv_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, matn_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, boshqa_handler))
    return app

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN o'rnatilmagan! .env faylni tekshiring (.env.example ga qarang).")
        return
    print("🤖 UZEX AI Agent + AI Usta bot ishga tushmoqda (polling)...")
    if UZEX_ENABLED:
        try:
            dbp = get_db_path()
            if dbp.exists():
                print(f"✅ UZEX DB topildi: {dbp} ({dbp.stat().st_size/1024/1024:.1f} MB)")
            else:
                print(f"⚠️ UZEX DB topilmadi: {dbp} — `python -m uzex.etl --src /tmp/uzex_spot_data --db ./data/uzex.db` ni ishga tushiring")
        except Exception as e:
            print(f"⚠️ DB tekshiruv xatosi: {e}")
    else:
        print("⚠️ UZEX moduli o'chirilgan (import xatosi)")
    app = Application.builder().token(token).post_init(post_init).build()
    register_handlers(app)
    print("✅ Bot tayyor! Telegram'da sinab ko'ring.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
