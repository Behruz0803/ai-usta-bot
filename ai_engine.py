import os
import time
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
    "usta", "ustaxona", "narx", "do'kon", "dokon", "qayer",
    "qayerdan", "topib", "top", "olx", "bozor", "ehtiyot",
    "zapchast", "zapas", "qism", "sotib", "olsam", "yaqin",
    "manzil", "telefon", "raqam"
]


def qidiruv_kerakmi(matn):
    matn = (matn or "").lower()
    return any(soz in matn for soz in QIDIRUV_SOZLARI)


qidiruv_config = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())]
)


def get_tarix(user_id):
    if user_id not in suhbat_tarixi:
        suhbat_tarixi[user_id] = []
    return suhbat_tarixi[user_id]


def tarixga_qosh(user_id, rol, matn):
    tarix = get_tarix(user_id)
    tarix.append(types.Content(role=rol, parts=[types.Part(text=matn)]))
    if len(tarix) > 12:
        suhbat_tarixi[user_id] = tarix[-12:]


def set_joylashuv(user_id, manzil):
    joylashuvlar[user_id] = manzil


def get_joylashuv(user_id):
    return joylashuvlar.get(user_id)


def bosh_qism(user_id):
    qismlar = [
        types.Content(role="user", parts=[types.Part(text=SYSTEM_PROMPT)]),
        types.Content(
            role="model",
            parts=[types.Part(text="Tushundim. Men AI Usta sifatida yordam berishga tayyorman.")]
        ),
    ]
    manzil = get_joylashuv(user_id)
    if manzil:
        qismlar.append(types.Content(
            role="user",
            parts=[types.Part(text=(
                f"[TIZIM MA'LUMOTI: Foydalanuvchi joylashuvi: {manzil}. "
                "Ustaxona va narxlarni shu joydan qidir.]"
            ))]
        ))
        qismlar.append(types.Content(
            role="model",
            parts=[types.Part(text="Tushundim, joylashuvni hisobga olaman.")]
        ))
    return qismlar


def ai_sorov(contents, qidiruv=False):
    if qidiruv:
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=qidiruv_config
            )
        except Exception as e:
            print(f"⚠️ Qidiruv xatosi, oddiy javob beriladi: {e}")

    return client.models.generate_content(
        model=MODEL,
        contents=contents
    )


def matn_javob(user_id, xabar):
    """Matnli xabarga javob — bu funksiya tushib qolgan edi"""
    tarixga_qosh(user_id, "user", xabar)
    javob = ai_sorov(
        bosh_qism(user_id) + get_tarix(user_id),
        qidiruv=qidiruv_kerakmi(xabar)
    )
    ai_javobi = javob.text
    tarixga_qosh(user_id, "model", ai_javobi)
    return ai_javobi


def media_javob(user_id, fayl_path, izoh="", fayl_turi="rasm"):
    if fayl_turi == "ovoz":
        mime_type = "audio/ogg" if fayl_path.endswith(".ogg") else "audio/mpeg"
        asosiy_savol = (
            "Bu ovozli xabarni tingla. Foydalanuvchi texnika muammosini "
            "gapirmoqchi. Uni tushun va AI Usta sifatida javob ber."
        )
    elif fayl_turi == "video":
        mime_type = "video/mp4"
        asosiy_savol = (
            "Bu videoni ko'rib chiq. Qanday qurilma va qanday muammo "
            "ko'rsatilgan? Tovushlarga ham e'tibor ber. Tashxis qo'y."
        )
    else:
        mime_type = "image/png" if fayl_path.endswith(".png") else "image/jpeg"
        asosiy_savol = (
            "Bu rasmni tahlil qil. Qanday qurilma? Brendi ko'rinyaptimi? "
            "Muammo yoki nosozlik bormi?"
        )

    savol = f"{asosiy_savol} Foydalanuvchi izohi: {izoh}" if izoh else asosiy_savol
    tarixga_qosh(user_id, "user", f"[Foydalanuvchi {fayl_turi} yubordi] {izoh}")

    with open(fayl_path, "rb") as f:
        fayl_bytes = f.read()

    media_part = types.Part.from_bytes(data=fayl_bytes, mime_type=mime_type)
    media_xabar = types.Content(
        role="user",
        parts=[media_part, types.Part(text=savol)]
    )

    javob = ai_sorov(
        bosh_qism(user_id) + get_tarix(user_id)[:-1] + [media_xabar],
        qidiruv=qidiruv_kerakmi(izoh)
    )

    ai_javobi = javob.text
    tarixga_qosh(user_id, "model", ai_javobi)
    return ai_javobi


def tarixni_tozala(user_id):
    suhbat_tarixi[user_id] = []
    return "Suhbat tozalandi. Yangi muammo haqida gaplashishimiz mumkin!"
