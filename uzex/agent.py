# -*- coding: utf-8 -*-
"""Agent yadrosi: savol → SQL → natija → javob.

Bu modul auditdagi quyidagi kamchiliklarni tuzatadi:
  * 0 natijada "yaqin javoblar" taklif qiladi (to'qimasdan, ochiq belgi bilan).
  * Mavjud bo'lmagan yil/sana uchun to'g'ri "yo'q" javobi va foydali izoh.
  * Bitim raqami, shartnoma raqami, BK kodi, STIR kabi qisqa savollarni tushunadi.
  * Har bir model 2 marta sinaladi (503/429), keyin zaxira modelga o'tadi.
  * Javob tili faqat o'zbek yoki rus (boshqa til chiqmaydi).
"""
import json
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .answer import (
    format_error,
    format_near_and_empty,
    format_no_data,
    format_result,
    is_no_data,
)
from .db import execute_sql, is_safe_select
from .schema import FEW_SHOT_EXAMPLES, SCHEMA_DESCRIPTION
from .textnorm import (
    detect_language,
    is_cotton_oil_question,
    prepare_sql,
    search_hints,
    translate_terms,
    ufold,
)

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
# 503 UNAVAILABLE / 429 RESOURCE_EXHAUSTED eng ko'p uchraydigan xato.
# Har bir model RETRY_ATTEMPTS marta sinaladi, keyin zaxirasiga o'tadi.
MODEL_FALLBACKS = [
    MODEL,
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]
RETRY_ATTEMPTS = max(1, int(os.getenv("UZEX_LLM_RETRIES", "2")))
_client = None


def get_client():
    global _client
    if _client is None:
        api_key = (os.getenv("UZEX_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("UZEX_GEMINI_API_KEY not set. Add to .env or Vercel env.")
        _client = genai.Client(api_key=api_key, http_options={"timeout": 60000})
    return _client


SYSTEM_PROMPT = f"""
Sen — UZEX AI Agent, O'zbekiston Tovar-Xomashyo Birjasi ma'lumotlari bo'yicha mutaxassisan.
Ты — UZEX AI Agent, эксперт по данным Товарно-сырьевой биржи Узбекистана.

ENG MUHIM QOIDA (DISKVALIFIKATSIYA XAVFI):
- Hech qachon ma'lumot to'qima: INN, kompaniya nomi, tovar nomi, broker kodi,
  narx yoki sonni o'zingdan qo'shma. Javobdagi har bir raqam SQL natijasidan keladi.
- SQL natijasi bo'sh bo'lsa (0 qator, COUNT=0, SUM=NULL) → foydalanuvchi tilida ayt:
  "Ma'lumotlar bazasida bunday ma'lumot mavjud emas" / "В базе данных такой информации нет".
- Natija aniq mos kelmasa, LEKIN o'xshash ma'lumot bo'lsa — to'qima emas, ochiq ayt:
  "Sizning shartlaringizga aynan mos ma'lumot topilmadi, lekin shunga yaqin natijalar bor",
  keyin yaqin natijalarni ko'rsat va nega mos kelmasligini tushuntir (boshqa sana,
  boshqa summa, boshqa valyuta). Har bir yaqin qator "yaqin" deb belgilanadi.
- Mavjud bo'lmagan kompaniya/tovar haqida savol bersa: SQL 0 qator qaytaradi, sen
  "bunday ma'lumot yo'q" deb aytasan va nomni o'zingdan to'qib yozmaysan.

TEXNIK QOIDALAR:
- Faqat SQLite SELECT yoki WITH. INSERT/UPDATE/DELETE/DROP mumkin emas.
- Tovar nomlari iflos: "1 сорт" va "1-сорта", katta/kichik harf aralash.
  SQLite COLLATE NOCASE kirillni buklamaydi → ufold(product_name) LIKE ufold('%...%').
- O'zbekcha tovar nomini ruscha qidir: paxta→хлопок, paxta yog'i→хлопковое масло,
  sement→цемент, shakar→сахар, bug'doy→пшеница, un→мука, benzin→бензин.
- Sana: "2024 yil" / "в 2024 году" → deal_date BETWEEN '2024-01-01' AND '2024-12-31'.
  Bazada 2022-01-03 … 2026-10-30 bor. Undan tashqari yil (2018, 2030) → 0 qator,
  bu to'g'ri javob, raqam to'qilmaydi.
- Eksport (Доллар США) summasi so'mda: deal_sum_uzs (deal_sum * usd_rate).
- Hajm = quantity * lot. Birlik narxi = deal_sum / (quantity * lot).
- Bitim raqami (masalan 604000) → deals.deal_id.
  Shartnoma raqami (100001–106616) → contracts.contract_id.
- Aggregatsiyada LIMIT kerak emas; ro'yxatlarda LIMIT 100.
- "qaysi biri" savolida LIMIT 1, "top N" da LIMIT N.
- Bekor qilingan bitimlar (Аннулирован) aylanma/statistikaga qo'shilmaydi,
  agar foydalanuvchi alohida so'ramasa.

JAVOB TILI:
- Foydalanuvchi qaysi tilda yozsa, shu tilda (UZ lotin/kirill yoki RU).
- Faqat shu ikki til. Boshqa til (ispan, ingliz) — hech qachon.

CHIQISH FORMATI (qat'iy JSON, boshqa matn yo'q):
{{
  "sql": "SELECT ...",
  "explanation": "Nima hisoblandi, qaysi formula va qaysi davr — qisqa izoh",
  "language": "uz" yoki "ru",
  "needs_data": true
}}

Agar savol bazaga aloqador bo'lmasa (salom, maqtov, texnika ta'miri, umumiy suhbat):
{{"sql": "", "explanation": "sabab", "language": "uz", "needs_data": false}}

{SCHEMA_DESCRIPTION}

{FEW_SHOT_EXAMPLES}
"""


# ── Gemini bilan SQL yaratish ──────────────────────────────────────
_RETRYABLE = ("503", "unavailable", "429", "resource_exhausted", "overloaded",
              "deadline", "timeout", "500", "internal", "try again")
_FATAL = ("api key", "api_key", "permission", "unauthenticated", "403", "401",
          "invalid_argument", "not found", "404")


def _is_retryable(err_text: str) -> bool:
    msg = (err_text or "").lower()
    return any(k in msg for k in _RETRYABLE)


def _is_fatal(err_text: str) -> bool:
    msg = (err_text or "").lower()
    return any(k in msg for k in _FATAL)


def _clean_json_text(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _parse_answer(text, question, lang_hint):
    """JSON yoki undan SQL ni ajratib olish."""
    t = _clean_json_text(text)
    try:
        data = json.loads(t)
        if "sql" not in data:
            raise ValueError("no sql key")
        data["language"] = data.get("language") if data.get("language") in ("uz", "ru") else lang_hint
        return data
    except Exception as e:
        print(f"⚠️ JSON parse failed: {e}, raw: {t[:300]}")
    # Zaxira: matndan SQL ni ajratish
    m = re.search(r"((?:SELECT|WITH)\b[\s\S]+?)(?:;|\n\n|$)", t, re.IGNORECASE)
    if m:
        sql = m.group(1).strip()
        if not sql.endswith(";"):
            sql += ";"
        return {
            "sql": sql,
            "explanation": "Savol bo'yicha bazadan aniq SELECT bajarildi.",
            "language": lang_hint,
            "needs_data": True,
        }
    return None


async def _gemini_generate(question, lang_hint):
    """Gemini'dan SQL JSON olish: model fallback + retry/backoff."""
    client = get_client()
    user_prompt = f"""
Savol / Вопрос: "{question}"

Til / Язык (auto): {lang_hint}
Talab: Yuqoridagi schema asosida to'g'ri SQLite SELECT so'rovini JSON formatda tuz.
Требование: Составь корректный SQLite SELECT на основе схемы выше, в формате JSON.

Return ONLY JSON, no markdown, no extra text.

{search_hints(question)}
"""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.1,
        max_output_tokens=2000,
    )
    last_err = None
    tried = set()
    for model_name in MODEL_FALLBACKS:
        if not model_name or model_name in tried:
            continue
        tried.add(model_name)
        for attempt in range(RETRY_ATTEMPTS):
            try:
                resp = await client.aio.models.generate_content(
                    model=model_name,
                    contents=[types.Content(role="user", parts=[types.Part(text=user_prompt)])],
                    config=config,
                )
                print(f"✅ Gemini model: {model_name} (urinish {attempt + 1})")
                return resp
            except Exception as e:
                last_err = e
                msg = f"{type(e).__name__}: {e}"
                print(f"⚠️ Gemini {model_name} urinish {attempt + 1}/{RETRY_ATTEMPTS}: {msg[:200]}")
                if _is_fatal(msg) or not _is_retryable(msg):
                    # Bu model bu xatoni keyingi urinishda ham qaytaradi.
                    if _is_fatal(msg):
                        raise
                    break
                # 503/429: kichik backoff, keyin qayta urinish
                import asyncio
                await asyncio.sleep(0.8 * (attempt + 1))
        # keyingi modelga o'tamiz
    if last_err:
        raise last_err
    raise RuntimeError("Gemini javob bermadi")


async def generate_sql(question: str) -> dict:
    """Savol → {sql, explanation, language, needs_data}."""
    lang_hint = detect_language(question)

    # 1) Ishonchli naqshlar (sana, summa, valyuta) — Gemini'siz ham aniq ishlaydi.
    try:
        from .heuristic import heuristic_sql
        sure = heuristic_sql(question)
        if sure.get("confident") and sure.get("sql"):
            sure.setdefault("language", lang_hint)
            sure["language"] = lang_hint if lang_hint in ("uz", "ru") else "uz"
            return sure
    except Exception as e:
        print(f"confident heuristic error: {e}")

    api_key = os.getenv("UZEX_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _heuristic_only(question, lang_hint, "GEMINI_API_KEY o'rnatilmagan")

    try:
        resp = await _gemini_generate(question, lang_hint)
    except Exception as e:
        print(f"⚠️ Gemini API error, heuristic fallback: {e}")
        return _heuristic_only(question, lang_hint, f"Gemini xatosi: {e}")

    text = (resp.text or "").strip()
    parsed = _parse_answer(text, question, lang_hint)
    if parsed and parsed.get("sql"):
        return parsed

    # Gemini javob bermadi/JSON buzuq — heuristic
    return _heuristic_only(question, lang_hint, f"Gemini javobi o'qilmadi: {text[:200]}")


def _heuristic_only(question, lang_hint, reason):
    from .heuristic import heuristic_sql
    try:
        h = heuristic_sql(question) or {}
    except Exception as e:
        h = {"sql": "", "explanation": f"heuristic error: {e}", "language": lang_hint}
    h.setdefault("language", lang_hint)
    h["language"] = lang_hint if lang_hint in ("uz", "ru") else "uz"
    h.setdefault("explanation", reason)
    h.setdefault("needs_data", bool(h.get("sql")))
    return h


# ── "Yaqin natija" strategiyasi ────────────────────────────────────
_NEAR_HINTS = [
    # (regex savolda, izoh uz, izoh ru)
    (r"\b(20[0-9]{2})\b", "Yil filtri olib tashlandi — bazada mavjud barcha yillar ko'rsatildi.",
     "Фильтр по году снят — показаны все годы, которые есть в базе."),
]


def _year_range_hint(question, lang):
    years = re.findall(r"\b(19|20)\d{2}\b", question or "")
    if years:
        return ("So'ralgan yil bazada yo'q (bazada 2022-01-03 … 2026-10-30)."
                if lang == "uz" else
                "Запрошенного года нет в базе (в базе 2022-01-03 … 2026-10-30).")
    return None


def _strip_year(sql, question):
    """Yilni olib tashlab qayta urinish uchun SQL ni yumshatadi."""
    patched = re.sub(
        r"(?:AND\s+)?(?:d\.)?deal_date\s+BETWEEN\s+'\d{4}-01-01'\s+AND\s+'\d{4}-12-31'",
        "1=1",
        sql,
        flags=re.IGNORECASE,
    )
    patched = re.sub(
        r"(?:AND\s+)?strftime\('%Y',\s*(?:d\.)?deal_date\)\s*=\s*'\d{4}'",
        "1=1",
        patched,
        flags=re.IGNORECASE,
    )
    patched = re.sub(
        r"(?:AND\s+)?(?:d\.)?deal_date\s+LIKE\s+'\d{4}-%'",
        "1=1",
        patched,
        flags=re.IGNORECASE,
    )
    if patched == sql:
        return None
    # Bo'sh bo'lib qolgan WHERE larni tozalash
    patched = re.sub(r"WHERE\s+AND\s+", "WHERE ", patched, flags=re.IGNORECASE)
    patched = re.sub(r"AND\s+AND\s+", "AND ", patched, flags=re.IGNORECASE)
    patched = re.sub(r"WHERE\s+1=1\s+AND\s+", "WHERE ", patched, flags=re.IGNORECASE)
    patched = re.sub(r"AND\s+1=1\s*", "", patched, flags=re.IGNORECASE)
    return patched


def _loosen_text_filter(sql):
    """Tovar/nom filtri 0 qator qaytarsa, filtrni olib tashlab yaqinini ko'rsatish."""
    patched = re.sub(
        r"(?:AND\s+)?ufold\(([\w.]+)\)\s+(?:NOT\s+)?LIKE\s+ufold\('[^']*'\)",
        "1=1",
        sql,
        flags=re.IGNORECASE,
    )
    if patched == sql:
        return None
    patched = re.sub(r"WHERE\s+AND\s+", "WHERE ", patched, flags=re.IGNORECASE)
    patched = re.sub(r"AND\s+AND\s+", "AND ", patched, flags=re.IGNORECASE)
    patched = re.sub(r"WHERE\s+1=1\s+AND\s+", "WHERE ", patched, flags=re.IGNORECASE)
    patched = re.sub(r"\s+AND\s+1=1", "", patched, flags=re.IGNORECASE)
    return patched


def _near_result(sql, question, lang, gen=None):
    """0 qator bo'lganda BITTA yumshatilgan so'rov bilan yaqin natija izlaydi.

    Cheklovlar (audit: "to'qib chiqarmasin"):
      * Nom filtri olib tashlansa, natija mavzuga aloqasiz bo'lib qoladi
        ("asdfghjkl" -> random 10 kompaniya). Shu sabab bu qadam FAQAT
        so'ralgan nom bazada umuman uchramasa qo'llanadi va 10 qator bilan cheklanadi.
      * Kompaniya qidiruvida ism o'xshashligi < 0.55 bo'lsa qator tashlanadi.
      * Har bir so'rov 12 soniya bilan chegaralangan (db.execute_sql).

    Qaytadi: (rows, columns, label) yoki None. Raqam hech qachon to'qilmaydi.
    """
    attempts = []
    softened = _strip_year(sql, question)
    if softened:
        attempts.append((softened, "Yil filtri olib tashlandi" if lang == "uz"
                         else "Фильтр по году снят"))

    for cand_sql, label in attempts:
        ok, _ = is_safe_select(cand_sql)
        if not ok:
            continue
        rows, columns, rowcount, error = execute_sql(cand_sql, limit=10, timeout_ms=8000)
        if rows and rowcount and not is_no_data(rows, columns, rowcount):
            return rows, columns, label

    # Nom filtri: faqat kompaniya izlashda va nom bazada umuman bo'lmasa
    if gen and gen.get("search_name"):
        loosened = _loosen_text_filter(sql)
        if loosened and loosened != softened:
            ok, _ = is_safe_select(loosened)
            if ok:
                rows, columns, rowcount, error = execute_sql(loosened, limit=40, timeout_ms=8000)
                if rows and rowcount:
                    from .heuristic import filter_company_rows
                    kept = filter_company_rows(rows, columns, gen)[:5]
                    if kept:
                        return kept, columns, ("Nom bo'yicha aniq mos yo'q — o'xshash nomlar"
                                               if lang == "uz" else
                                               "Точного названия нет — похожие компании")
    return None


# ── Umumiy yordamchi javoblar ──────────────────────────────────────
def _greeting(lang):
    if lang == "uz":
        return (
            "Salom! Men UZEX birja ma'lumotlari bo'yicha AI yordamchiman.\n\n"
            "Savol bering, masalan:\n"
            "• 2024-yilda eng ko'p bitim qilgan broker kim?\n"
            "• STIR 921912462 bo'yicha jami savdo qancha?\n"
            "• Sement bo'yicha eng qimmat bitim qaysi?\n"
            "• BK001 brokeri nechta bitimda ishtirok etgan?\n\n"
            "Raqamlar faqat bazadan olinadi — topilmasa, to'qimayman."
        )
    return (
        "Здравствуйте! Я AI-ассистент по данным биржи UZEX.\n\n"
        "Задайте вопрос, например:\n"
        "• Какой брокер провёл больше всего сделок в 2024 году?\n"
        "• Какая сумма сделок по ИНН 921912462?\n"
        "• Самая дорогая сделка по цементу?\n\n"
        "Цифры берутся только из базы — если данных нет, я не выдумываю."
    )


def _market_fallback(lang):
    if lang == "uz":
        return (
            "Savolingizni tushundim, lekin aniq SQL tuza olmadim.\n"
            "Iltimos, sana, summa yoki tovar nomini aniqroq yozing.\n"
            "Masalan: \"2026-08-03 kuni 1 dollarlik shartnoma bormi?\""
        )
    return (
        "Вопрос понял, но точный SQL собрать не удалось.\n"
        "Уточните дату, сумму или название товара.\n"
        "Например: \"Есть ли контракт на 1 доллар от 2026-08-03?\""
    )


GREETING_WORDS = ("salom", "assalom", "hello", "hi ", "привет", "здравств",
                  "qandaysan", "rahmat", "спасибо", "yaxshimisan")


def _unknown_goods(lang):
    """Savoldagi tovar bazada umuman yo'q (oltin, kosmik kema, telefon…)."""
    if lang == "uz":
        return (
            "❌ Ma'lumotlar bazasida bunday ma'lumot mavjud emas.\n\n"
            "Savolda so'ralgan tovar/mavzu birja bitimlari bazasida (2022–2026, "
            "500 000 bitim) uchramaydi. Men javobni to'qib chiqarmayman.\n\n"
            "Bazada bor yo'nalishlar: neft mahsulotlari (benzin, dizel, gaz), "
            "kimyo (selitra, karbamid, polimerlar), qurilish materiallari (sement, "
            "armatura, shifer), qishloq xo'jaligi (paxta, bug'doy, shakar, un), metall.\n\n"
            "Aniq tovar nomi bilan qayta so'rang — masalan: «Sement narxi 2024»."
        )
    return (
        "❌ В базе данных такой информации нет.\n\n"
        "Запрошенный товар/тема отсутствует в базе биржевых сделок (2022–2026, "
        "500 000 сделок). Я не выдумываю ответ.\n\n"
        "В базе есть: нефтепродукты (бензин, дизель, газ), химия (селитра, "
        "карбамид, полимеры), стройматериалы (цемент, арматура, шифер), "
        "сельхозпродукция (хлопок, пшеница, сахар, мука), металл.\n\n"
        "Уточните название товара — например: «Цена цемента 2024»."
    )


def _unclear(lang):
    if lang == "uz":
        return (
            "🤔 Savolingizni tushunmadim.\n\n"
            "Men faqat UZEX birja ma'lumotlari bo'yicha javob beraman (500 000 bitim, 2022–2026).\n"
            "Savolni aniqroq yozing, masalan:\n"
            "• 2024 yilda eng ko'p bitim qilgan broker kim?\n"
            "• STIR 921912462 bo'yicha jami savdo qancha?\n"
            "• Sement bo'yicha eng qimmat bitim qaysi?\n\n"
            "Ma'lumot topilmasa — to'qimayman, ochiq aytaman."
        )
    return (
        "🤔 Не понял вопрос.\n\n"
        "Я отвечаю только по данным биржи UZEX (500 000 сделок, 2022–2026).\n"
        "Сформулируйте точнее, например:\n"
        "• Какой брокер провёл больше всего сделок в 2024 году?\n"
        "• Какая сумма сделок по ИНН 921912462?\n"
        "• Самая дорогая сделка по цементу?\n\n"
        "Если данных нет — я не выдумываю."
    )


def _no_sql_hint(question, lang):
    """Savol turiga qarab: salomlashuv, bazaga oid, yoki tushunarsiz."""
    q = (question or "").lower()
    if any(w in q for w in GREETING_WORDS) and len(q.split()) <= 4:
        return _greeting(lang)
    try:
        from .heuristic import unknown_product
        if unknown_product(question):
            return _unknown_goods(lang)
    except Exception:
        pass
    try:
        from .heuristic import looks_like_market
        if looks_like_market(question):
            return _market_fallback(lang)
    except Exception:
        pass
    return _unclear(lang)


# ── Asosiy kirish nuqtasi ──────────────────────────────────────────
async def answer(question: str, user_id=None):
    start = time.time()
    lang = detect_language(question)
    if lang not in ("uz", "ru"):
        lang = "uz"

    gen = await generate_sql(question)
    sql = (gen.get("sql") or "").strip()
    explanation = gen.get("explanation") or ""
    lang = gen.get("language") if gen.get("language") in ("uz", "ru") else lang
    needs_data = gen.get("needs_data", True)

    # ⛔ Anti-hallucination: savoldagi tovar/mavzu bazada umuman yo'q bo'lsa,
    # Gemini SQL tuzsa ham ishlatmaymiz (u "umumiy statistika" qaytarib yuborardi).
    try:
        from .heuristic import unknown_product
        if unknown_product(question):
            return _unknown_goods(lang if lang in ("uz", "ru") else "uz")
    except Exception:
        pass

    # Heuristika aniq javob bersa ishlatamiz. Gemini "ma'lumot yo'q" desa yoki
    # SQL bermasa — heuristikaga qaytamiz. Heuristika ham "yo'q" desa, javob yo'q.
    h = {}
    try:
        from .heuristic import heuristic_sql
        h = heuristic_sql(question) or {}
    except Exception as e:
        print(f"heuristic error: {e}")

    if not sql or gen.get("needs_data") is False:
        if h.get("sql"):
            sql = h["sql"]
            explanation = h.get("explanation") or explanation
            lang = h.get("language") if h.get("language") in ("uz", "ru") else lang
            needs_data = True
        elif not sql:
            # Heuristika ham SQL topmadi — SQL yo'q
            needs_data = False
            if h.get("explanation") and h.get("confident"):
                explanation = h["explanation"]

    elapsed = lambda: int((time.time() - start) * 1000)  # noqa: E731

    if not sql:
        # Heuristika izohi mazmunli bo'lsa (masalan "bunday hudud yo'q") — o'shani aytamiz
        if explanation and len(explanation) > 40:
            prefix = "❌ Ma'lumotlar bazasida bunday ma'lumot mavjud emas.\n\n" if lang == "uz" \
                else "❌ В базе данных такой информации нет.\n\n"
            return prefix + explanation + f"\n\n⏱ {elapsed()} ms"
        return _no_sql_hint(question, lang) if not needs_data else _market_fallback(lang)

    # Unicode LIKE + paxta yog'i + "faqat ijro etilgan"
    sql = prepare_sql(sql, question)

    safe, msg = is_safe_select(sql)
    if not safe:
        print(f"⚠️ Unsafe SQL blocked: {msg} | {sql[:200]}")
        hint = ("So'rov xavfsizlik tekshiruvidan o'tmadi — faqat o'qish (SELECT) so'rovlari ruxsat etilgan."
                if lang == "uz" else
                "Запрос не прошёл проверку безопасности — разрешены только чтение (SELECT).")
        return format_error(sql, msg, explanation, lang, elapsed(), hint=hint)

    rows, columns, rowcount, error = execute_sql(sql, limit=100)

    # So'rov vaqtida tugamadi (og'ir JOIN) — foydalanuvchiga texnik xato ko'rsatmaymiz
    if error and "ms ichida tugamadi" in str(error):
        hint = ("So'rov juda og'ir bo'lib chiqdi. Savolni yil yoki tovar nomi bilan "
                "aniqlashtiring." if lang == "uz" else
                "Запрос оказался слишком тяжёлым. Уточните год или название товара.")
        return format_no_data(sql, explanation, lang, elapsed(), hint=hint)

    # SQL xatosi (sintaksis) — jadval/ustun nomi noto'g'ri
    if error and "truncated" not in error.lower():
        hint = None
        if isinstance(error, str) and ("no such column" in error or "no such table" in error):
            hint = ("SQL ustun/jadval nomi xato. Bu texnik xato, raqam to'qilmaydi — savolni "
                    "boshqacha yozib ko'ring." if lang == "uz" else
                    "Ошибка в имени столбца/таблицы. Это техническая ошибка, данные не выдумываются.")
        return format_error(sql, error, explanation, lang, elapsed(), hint=hint)

    truncated = error if error and "truncated" in error.lower() else None
    empty = is_no_data(rows, columns, rowcount)

    # Kompaniya qidiruvi: LIKE topgan qatorlar orasidan haqiqiy nom mos kelganini ajratamiz
    if not empty and gen.get("search_name"):
        try:
            from .heuristic import filter_company_rows
            filtered = filter_company_rows(rows, columns, gen)
            if len(filtered) != len(rows):
                print(f"🔎 Kompaniya nomi filtri: {len(rows)} -> {len(filtered)} qator")
            rows = filtered
            rowcount = len(rows)
            empty = is_no_data(rows, columns, rowcount)
        except Exception as e:
            print(f"company filter error: {e}")

    if not empty:
        hint = None
        if truncated:
            hint = ("Natija qisqartirildi. Aniqroq savol bering yoki yil/davrni ko'rsating."
                    if lang == "uz" else
                    "Результат сокращён. Уточните вопрос или укажите год/период.")
        return format_result(sql, rows, columns, rowcount, explanation, lang,
                             elapsed(), truncated=truncated, hint=hint)

    # ── 0 qator: yaqin natija bormi? ──────────────────────────────
    near = _near_result(sql, question, lang, gen)
    year_hint = _year_range_hint(question, lang)
    if near:
        near_rows, near_columns, label = near
        return format_near_and_empty(
            sql, explanation, lang, elapsed(),
            near_rows=near_rows, near_columns=near_columns,
            near_label=label, hint=year_hint,
        )
    return format_no_data(sql, explanation, lang, elapsed(), hint=year_hint)


def answer_sync(question: str):
    import asyncio
    return asyncio.run(answer(question))
