import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import SYSTEM_PROMPT

load_dotenv()

MODEL = "gemini-3-flash-preview"

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options={"timeout": 180000},  # 180 soniya
)

suhbat_tarixi = {}
joylashuvlar = {}

QIDIRUV_SOZLARI = [
    "usta", "ustaxona", "narx", "narxi", "do'kon", "dokon", "qayer",
    "qayerdan", "topib", "top", "olx", "bozor", "ehtiyot", "ehtiyot qism",
    "zapchast", "zapas", "qism", "sotib", "sotib olish", "olsam", "yaqin",
    "manzil", "telefon", "raqam", "xizmat"
]


def qidiruv_kerakmi(matn, user_id=None):
    matn = (matn or "").lower()
    bor = any(soz in matn for soz in QIDIRUV_SOZLARI)
    if bor:
        return True
    if user_id and get_joylashuv(user_id) and any(w in matn for w in ["qayer", "narx", "usta", "do'kon", "sotib"]):
        return True
    return False


def get_tarix(user_id):
    if user_id not in suhbat_tarixi:
        suhbat_tarixi[user_id] = []
    return suhbat_tarixi[user_id]


def tarixga_qosh(user_id, rol, matn):
    tarix = get_tarix(user_id)
    tarix.append(types.Content(role=rol, parts=[types.Part(text=matn)]))
    # Oxirgi 10 ta xabarni saqlash (kontekstni toza va ixcham tutish)
    if len(tarix) > 10:
        suhbat_tarixi[user_id] = tarix[-10:]


def set_joylashuv(user_id, manzil):
    joylashuvlar[user_id] = manzil


def get_joylashuv(user_id):
    return joylashuvlar.get(user_id)


def get_system_instruction(user_id):
    """System Prompt va joylashuv ma'lumotlarini birlashtirish"""
    manzil = get_joylashuv(user_id)
    if manzil:
        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"📍 FOYDALANUVCHINING ANIQ JOYLASHUVI:\n"
            f"Foydalanuvchi manzili: {manzil}. Ustaxona, usta, do'kon va ehtiyot qism "
            f"so'ralganda shu joy yaqinidan qidir va aniq tavsiya ber."
        )
    return SYSTEM_PROMPT


async def ai_sorov(user_id, contents, qidiruv=False):
    """Gemini API'ga aio (асинхронный) client bilan so'rov yuborish (Event Loop блокировкасиз)"""
    sys_instruction = get_system_instruction(user_id)
    config_args = {"system_instruction": sys_instruction}

    if qidiruv:
        config_args["tools"] = [types.Tool(google_search=types.GoogleSearch())]

    config = types.GenerateContentConfig(**config_args)

    if qidiruv:
        try:
            return await client.aio.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config
            )
        except Exception as e:
            print(f"⚠️ Google Search qidiruv xatosi, oddiy rejimda qayta uriniladi: {e}")
            config_no_search = types.GenerateContentConfig(system_instruction=sys_instruction)
            return await client.aio.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config_no_search
            )

    return await client.aio.models.generate_content(
        model=MODEL,
        contents=contents,
        config=config
    )


async def matn_javob(user_id, xabar):
    """Matnli xabarga асинхронный AI javobi"""
    tarixga_qosh(user_id, "user", xabar)
    contents = get_tarix(user_id)
    need_search = qidiruv_kerakmi(xabar, user_id)

    javob = await ai_sorov(user_id, contents, qidiruv=need_search)
    ai_javobi = javob.text
    tarixga_qosh(user_id, "model", ai_javobi)
    return ai_javobi


async def media_javob(user_id, fayl_path, izoh="", fayl_turi="rasm"):
    """Rasm, video va ovozli xabarlarga асинхронный AI javobi"""
    if fayl_turi == "ovoz":
        mime_type = "audio/ogg" if fayl_path.endswith(".ogg") else "audio/mpeg"
        asosiy_savol = (
            "Bu ovozli xabarni tingla. Foydalanuvchi maishiy texnika yoki elektronika "
            "muammosini tushuntiryapti. Xabarni tushun va AI Usta sifatida tashxis qo'y."
        )
    elif fayl_turi == "video":
        mime_type = "video/mp4"
        asosiy_savol = (
            "Bu videoni ko'rib chiq. Qanday qurilma va qanday nosozlik ko'rsatilgan? "
            "Tovushlar va harakatlarga e'tibor berib, AI Usta sifatida tashxis qo'y."
        )
    else:
        mime_type = "image/png" if fayl_path.endswith(".png") else "image/jpeg"
        asosiy_savol = (
            "Bu rasmni tahlil qil. Qanday qurilma, brend/model va qanday nosozlik "
            "ko'rinyapti? AI Usta sifatida tashxis va yechim ber."
        )

    savol = f"{asosiy_savol} Foydalanuvchi izohi: {izoh}" if izoh else asosiy_savol

    with open(fayl_path, "rb") as f:
        fayl_bytes = f.read()

    media_part = types.Part.from_bytes(data=fayl_bytes, mime_type=mime_type)
    media_xabar = types.Content(
        role="user",
        parts=[media_part, types.Part(text=savol)]
    )

    # Oldingi suhbat tarixi + joriy медиа fayl
    contents = get_tarix(user_id) + [media_xabar]
    need_search = qidiruv_kerakmi(izoh, user_id)

    javob = await ai_sorov(user_id, contents, qidiruv=need_search)
    ai_javobi = javob.text

    # Tarixga медиа haqida ixcham matnli ma'lumot qo'shish (xotirani og'irlashtirmaslik uchun)
    user_summary = f"[Foydalanuvchi {fayl_turi} yubordi] {izoh}".strip()
    tarixga_qosh(user_id, "user", user_summary)
    tarixga_qosh(user_id, "model", ai_javobi)

    return ai_javobi


def tarixni_tozala(user_id):
    suhbat_tarixi[user_id] = []
    return "Suhbat tozalandi. Yangi muammo haqida gaplashishimiz mumkin!"
