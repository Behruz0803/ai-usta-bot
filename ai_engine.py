import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from prompts import SYSTEM_PROMPT

load_dotenv()

MODEL = "gemini-3-flash-preview"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

suhbat_tarixi = {}
joylashuvlar = {}

# ═══════════════════════════════════════
# AQLLI QIDIRUV — faqat kerak bo'lganda
# ═══════════════════════════════════════

QIDIRUV_SOZLARI = [
    "usta", "ustaxona", "narx", "do'kon", "dokon", "qayer",
    "qayerdan", "topib", "top", "olx", "bozor", "ehtiyot",
    "zapchast", "zapas", "qism", "sotib", "olsam", "yaqin",
    "manzil", "telefon", "raqam", "shlang", "filtr"
]

def qidiruv_kerakmi(matn):
    matn = (matn or "").lower()
    return any(soz in matn for soz in QIDIRUV_SOZLARI)

qidiruv_config = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())]
)

# ═══════════════════════════════════════
# SUHBAT TARIXI
# ═══════════════════════════════════════

def get_tarix(user_id):
    if user_id not in suhbat_tarixi:
        suhbat_tarixi[user_id] = []
    return suhbat_tarixi[user_id]

def tarixga_qosh(user_id, rol, matn):
    tarix = get_tarix(user_id)
    tarix.append(types.Content(role=rol, parts=[types.Part(text=matn)]))
    if len(tarix) > 20:
        suhbat_tarixi[user_id] = tarix[-20:]

def set_joylashuv(user_id, manzil):
    joylashuvlar[user_id] = manzil

def get_joylashuv(user_id):
    return joylashuvlar.get(user_id)

def bosh_qism(user_id):
    qismlar = [
        types.Content(role="user", parts=[types.Part(text=SYSTEM_PROMPT)]),
        types.Content(role="model", parts=[types.Part(text="Tushundim. Men AI Usta sifatida yordam berishga tayyorman.")]),
    ]
    manzil = get_joylashuv(user_id)
    if manzil:
        qismlar.append(types.Content(
            role="user",
            parts=[types.Part(text=f"[TIZIM MA'LUMOTI: Foydalanuvchi joylashuvi: {manzil}. Ustaxona va narxlarni shu joydan qidir.]")]
        ))
        qismlar.append(types.Content(
            role="model",
            parts=[types.Part(text="Tushundim, joylashuvni hisobga olaman.")]
        ))
    return qismlar

# ═══════════════════════════════════════
# AI GA SO'ROV — XAVFSIZ (avto-fallback)
# ═══════════════════════════════════════

def ai_sorov(contents, qidiruv=False):
    """Qidiruv ishlamasa, avtomatik qidiruvsiz javob beradi"""
    if qidiruv:
        try:
            return client.models.generate_content(
                model=MODEL, contents=contents, config=qidiruv_config
            )
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("⚠️ Internet qidiruv limiti tugadi — AI o'z bilimi bilan javob beradi")
            else:
                raise
    return client.models.generate_content(model=MODEL, contents=contents)

# ═══════════════════════════════════════
# JAVOB FUNKSIYALARI
# ═══════════════════════════════════════

def matn_javob(user_id, xabar):
    tarixga_qosh(user_id, "user", xabar)
    javob = ai_sorov(
        bosh_qism(user_id) + get_tarix(user_id),
        qidiruv=qidiruv_kerakmi(xabar)
    )
    ai_javobi = javob.text
    tarixga_qosh(user_id, "model", ai_javobi)
    return ai_javobi

def media_javob(user_id, fayl_path, izoh="", fayl_turi="rasm"):
    media_fayl = client.files.upload(file=fayl_path)

    for _ in range(15):
        media_fayl = client.files.get(name=media_fayl.name)
        if media_fayl.state.name == "ACTIVE":
            break
        time.sleep(1)

    if fayl_turi == "ovoz":
        asosiy_savol = ("Bu ovozli xabarni tingla. Foydalanuvchi texnika "
                        "muammosini gapirmoqchi. Uni tushun va AI Usta "
                        "sifatida javob ber yoki savol ber.")
    elif fayl_turi == "video":
        asosiy_savol = ("Bu videoni ko'rib chiq. Qanday qurilma va qanday "
                        "muammo ko'rsatilgan? Tovushlarga ham e'tibor ber. "
                        "AI Usta sifatida tashxis qo'y.")
    else:
        asosiy_savol = ("Bu rasmni tahlil qil. Qanday qurilma? "
                        "Muammo ko'rinyaptimi?")

    savol = f"{asosiy_savol} Foydalanuvchi izohi: {izoh}" if izoh else asosiy_savol

    tarixga_qosh(user_id, "user", f"[Foydalanuvchi {fayl_turi} yubordi] {izoh}")

    media_xabar = types.Content(
        role="user",
        parts=[
            types.Part(file_data=types.FileData(
                file_uri=media_fayl.uri,
                mime_type=media_fayl.mime_type
            )),
            types.Part(text=savol)
        ]
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