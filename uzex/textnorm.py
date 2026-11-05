# -*- coding: utf-8 -*-
"""Unicode + til (uz/ru) normalizatsiyasi.

Nima uchun kerak:
- SQLite COLLATE NOCASE kirillni ham, o'zbekcha apostroflarni ham buklamaydi
  (Farg‘ona ≠ farg'ona). Shu sabab LIKE lar ufold() orqali ishlatiladi.
- Ma'lumot bazasi nomlari rus tilida ("Хлопок", "Масло хлопковое"), savollar esa
  o'zbekcha bo'ladi ("paxta", "paxta yog'i"). Shuning uchun so'zma-so'z tarjima
  lug'ati (uz -> ru) bor; u faqat qidiruvda, javob matnida ishlatilmaydi.
- Telegram Markdown '_' ni yeb qo'yadi, shuning uchun javob <pre> HTML bo'lib ketadi.
"""
import html
import re

# Apostrof va qo'shtirnoq variantlari (UZEX fayllarida U+2018 ishlatiladi).
_STRIP = "'\u2018\u2019\u201b\u02bc\u02bb\u2032\u0060\u00b4\"«»“”"


def ufold(value):
    """Registrni buklash + apostrof/qo'shtirnoqlarni olib tashlash."""
    if value is None:
        return None
    s = str(value).casefold()
    for ch in _STRIP:
        s = s.replace(ch, "")
    return s


def fold_text(text: str) -> str:
    """Savolni qidiruvga tayyorlash: apostroflar bir xil, ortiqcha bo'shliq yo'q."""
    if not text:
        return ""
    s = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u02bb", "'")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ── Lotin (o'zbek) -> kirill (rus) qidiruv lug'ati ─────────────────
# Kalit: o'zbekcha ildiz (apostrofsiz, kichik harf), qiymat: bazadagi ruscha shakl.
# Faqat qidiruv uchun — javobda foydalanuvchi tilidagi nom ko'rsatiladi.
UZ_RU_TERMS = {
    # oziq-ovqat
    "paxta yog": "хлопковое масло",
    "paxta yogi": "хлопковое масло",
    "paxta": "хлопок",
    "yog'": "масло",
    "yog": "масло",
    "kungaboqar": "подсолнечное",
    "shakar": "сахар",
    "qand": "сахар",
    "un": "мука",
    "muka": "мука",
    "bug'doy": "пшеница",
    "bugdoy": "пшеница",
    "bug'": "пшеница",
    "guruch": "рис",
    "sholi": "рис",
    "arpа": "ячмень",
    "arpa": "ячмень",
    "makkajo'xori": "кукуруза",
    "makkajoxori": "кукуруза",
    "shrot": "шрот",
    "kunjara": "шрот",
    "tuxum": "яйцо",
    "go'sht": "мясо",
    "gosht": "мясо",
    "sut": "молоко",
    # yoqilg'i / kimyo
    "benzin": "бензин",
    "dizel": "дизельное топливо",
    "solyarka": "дизельное топливо",
    "yoqilg'i": "топливо",
    "yoqilgi": "топливо",
    "gaz": "газ",
    "suyultirilgan gaz": "сжиженный газ",
    "karbamid": "карбамид",
    "mochevina": "карбамид",
    "selitra": "селитра",
    "ammiakli selitra": "аммиачная селитра",
    "polietilen": "полиэтилен",
    "polipropilen": "полипропилен",
    "polivinilxlorid": "поливинилхлорид",
    "pvh": "поливинилхлорид",
    "sulfat kislota": "кислота серная",
    "oltingugurt kislota": "кислота серная",
    "kislota": "кислота",
    "soda": "сода",
    "kaustik soda": "сода каустическая",
    # qurilish / metall
    "sement": "цемент",
    "tsement": "цемент",
    "portlandsement": "портландцемент",
    "beton": "бетон",
    "gips": "гипс",
    "ohak": "известь",
    "armatura": "арматура",
    "po'lat": "сталь",
    "polat": "сталь",
    "metall": "металл",
    "mis": "медь",
    "alyuminiy": "алюминий",
    "profil": "профиль",
    "truba": "труба",
    "quvur": "труба",
    "shifer": "шифер",
    "plita": "плита",
    "keramika": "керамика",
    "shisha": "стекло",
    "qog'oz": "бумага",
    "qogoz": "бумага",
    "karton": "картон",
    "yog'och": "древесина",
    "yogoch": "древесина",
    # to'qimachilik / boshqa
    "ip": "пряжа",
    "ip-kalava": "пряжа",
    "kalava": "пряжа",
    "matо": "ткань",
    "mato": "ткань",
    "teri": "кожа",
    "jun": "шерсть",
    "tolа": "волокно",
    "tola": "волокно",
    # umumiy
    "tovar": "товар",
    "mahsulot": "продукт",
}


# Qo'shimcha so'zlar (auditda topilgan bo'shliqlar)
UZ_RU_TERMS.update({
    "neft": "нефть",
    "neft mahsulot": "нефтепродукты",
    "neftgaz": "нефтегаз",
    "gaz": "газ",
    "suyultirilgan": "сжиженный",
    "propan": "пропан",
    "butan": "бутан",
    "metan": "метан",
    "spirt": "спирт",
    "etanol": "спирт этиловый",
    "xom ashyo": "сырьё",
    "xomashyo": "сырьё",
    "tolа": "волокно",
    "tola": "волокно",
    "kalava ip": "пряжа",
    "moy": "масло",
    "yog'och": "древесина",
    "yogoch": "древесина",
    "alyuminiy": "алюминий",
    "mis": "медь",
    "rux": "цинк",
    "qo'rg'oshin": "свинец",
    "qorgoshin": "свинец",
    "poroshok": "порошок",
    "sovun": "мыло",
    "tax": "тахта",
    "list": "лист",
    "profil": "профиль",
    "quvur": "труба",
    "kanalizatsiya": "канализация",
    "elektr": "электро",
    "kabel": "кабель",
    "sim": "провод",
    "akkumulyator": "аккумулятор",
    "shina": "шина",
    "rezina": "резина",
    "plastik": "пластик",
    "granula": "гранулы",
    "smola": "смола",
    "lak": "лак",
    "bo'yoq": "краска",
    "boyoq": "краска",
    "kley": "клей",
    "sellyuloza": "целлюлоза",
    "kraxmal": "крахмал",
    "patoka": "патока",
    "melassa": "меласса",
    "silos": "силос",
    "kunjara": "шрот",
    "beda": "люцерна",
    "somon": "солома",
    "paxta tolasi": "хлопковое волокно",
    "lint": "линт",
    "chigit": "семена хлопка",
    "teri": "кожа",
    "jun": "шерсть",
    "ipak": "шелк",
    "matо": "ткань",
    "mato": "ткань",
})

# Teskari lug'at: ruscha ildiz -> javobda ko'rsatiladigan o'zbekcha nom.
RU_UZ_LABEL = {
    "хлопковое масло": "paxta yog'i",
    "масло хлопковое": "paxta yog'i",
    "хлопок": "paxta",
    "пшеница": "bug'doy",
    "мука": "un",
    "сахар": "shakar",
    "цемент": "sement",
    "портландцемент": "sement (portland)",
    "карбамид": "karbamid",
    "селитра": "selitra",
    "полиэтилен": "polietilen",
    "бензин": "benzin",
    "дизельное": "dizel",
}


def translate_terms(question: str) -> list:
    """Savoldagi o'zbekcha tovar so'zlarini bazadagi ruscha shaklga o'giradi.

    So'z chegarasi bilan qidiriladi: "O'zbekneftgaz" ichidagi "gaz" tovar deb
    olinmaydi (audit: kompaniya nomi tovar bilan aralashib ketgan edi).

    Qaytadi: [(ruscha_qidiruv_matni, original_so'z), ...] — takrorlanmaydi.
    """
    q = ufold(question or "")
    # Apostroflar olib tashlangan matnda ham so'z chegarasi uchun bo'shliq/raqam.
    norm = " " + re.sub(r"[^0-9a-z\u0400-\u04ff]+", " ", q) + " "
    found = []
    seen = set()
    # Uzun kalitlar birinchi — "paxta yogi" "yog" dan oldin topilsin.
    for uz_key in sorted(UZ_RU_TERMS, key=len, reverse=True):
        key = uz_key.replace("'", "")
        if not key:
            continue
        # Ko'p so'zli kalit: qismlar ketma-ket bormi?
        pattern = r"(?<![\w])" + r"\s+".join(re.escape(part) for part in key.split()) + r"(?![\w])"
        if re.search(pattern, norm):
            ru = UZ_RU_TERMS[uz_key]
            if ru in seen:
                continue
            seen.add(ru)
            found.append((ru, uz_key))
    return found


# ── Til aniqlash ───────────────────────────────────────────────────
_LATIN_UZ = re.compile(
    r"\b("
    r"qancha|qaysi|qachon|nechta|necha|qanday|kim|nima|qayer|bormi|jami|"
    r"yilda|yil|oyda|sana|bo'yicha|boyicha|uchun|bilan|hamda|va|yoki|"
    r"bitim|shartnoma|shartoma|broker|sotuvchi|xaridor|sotilgan|xarid|savdo|"
    r"narx|narxi|summa|so'm|som|aylanma|aylanmasi|viloyat|viloyatida|"
    r"tovar|mahsulot|kompaniya|korxona|hisobot|statistika|eng|ko'p|kop|kam|"
    r"qimmat|arzon|top|kurs|dollar|eksport|import|beradi|bering|ko'rsat|korsat|"
    r"bk\d|stir|inn|uzex|birja|gaz|neft|neftgaz|paxta|sement|shakar|benzin|"
    r"aksia|foiz|dona|litr|tonna|kg|gramm|kun|hafta|chorak|oraliq|davomida|"
    r"kerak|mumkin|boladimi|bormikan|ayt|aytib|yoz|ko'rsatib|misol|namuna"
    r")(?![\w])",
    re.IGNORECASE,
)
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_RU_WORDS = re.compile(
    r"\b(сколько|какой|какая|какие|когда|кто|что|где|чего|почему|"
    r"сделк|контракт|брокер|покупател|продавец|товар|цена|стоимость|сумм|"
    r"объ[её]м|оборот|год|году|месяц|регион|област|компани|предприят|"
    r"экспорт|импорт|курс|доллар|самый|самая|самые|больше|меньше|наибольш|"
    r"выручк|количество|средн|всего|итого|данн|база|покажи|скажи|есть)\b",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    """Savol tili: 'uz' yoki 'ru'. Default — o'zbek (asosiy auditoriya).

    Ilgari funksiya faqat 14 ta so'zga qarab qaror qilardi va "BK001",
    "Sement narxlari", "Eng yirik savdo" kabi savollarga rus tilida javob
    berardi. Endi: kirill + ruscha so'zlar hisobga olinadi, lotin harflar
    va o'zbekcha markerlar ustun bo'lsa — o'zbek.
    """
    t = text or ""
    # BK001, STIR, UZEX, 921912462 — hech qanday til belgisi emas.
    # Bunday savol o'zbek foydalanuvchidan keladi (asosiy auditoriya).
    if not re.search(r"[A-Za-z\u0400-\u04FF]{2,}", re.sub(r"\b(BK|STIR|INN|UZEX|USD|UZS)\b", "", t, flags=re.I)):
        return "uz"
    cyr = len(_CYRILLIC.findall(t))
    lat = len(re.findall(r"[A-Za-z]", t))
    ru_hits = len(_RU_WORDS.findall(t))
    uz_hits = len(_LATIN_UZ.findall(t))

    # Kirill matn ichida o'zbekcha lotin so'zlar juda kam bo'ladi.
    if cyr == 0:
        return "uz"
    if lat > cyr:
        # Lotin ustun: "2024 yilda eng ko'p STIR" kabi aralash yozuvlar
        return "uz" if uz_hits >= ru_hits else "ru"
    if ru_hits == 0 and uz_hits > 0:
        return "uz"
    if ru_hits > uz_hits:
        return "ru"
    if uz_hits > 0:
        return "uz"
    # Faqat kirill, lekin ruscha marker yo'q — baribir rus tili.
    return "ru"


# ── SQL matn almashtirish (Unicode LIKE) ───────────────────────────
_LIKE = re.compile(
    r"(?P<col>(?:[A-Za-z_][\w]*\.)?[A-Za-z_][\w]*)\s+(?P<not>NOT\s+)?LIKE\s+"
    r"(?P<pat>'(?:[^']|'')*')(?:\s+COLLATE\s+\w+)?",
    re.IGNORECASE,
)

_COTTON_STRONG = (
    "(ufold(product_name) LIKE ufold('%хлопковое масло%') "
    "OR ufold(product_name) LIKE ufold('%масло хлопковое%'))"
)


def is_cotton_oil_question(question: str) -> bool:
    q = ufold(question or "")
    if "paxta" in q and "yog" in q:
        return True
    if "пахта" in q and ("ёг" in q or "йог" in q or "масл" in q):
        return True
    if "хлопковое масло" in q or "масло хлопковое" in q:
        return True
    return False


def _cotton_like(pattern_sql: str) -> bool:
    raw = pattern_sql.replace("''", "").casefold()
    return any(tok in raw for tok in ("хлопков", "пахта", "йог", "ёг", "хлопковое"))


def strengthen_product_likes(sql: str, question: str = "") -> str:
    """Paxta yog'i uchun ikkala so'z tartibini ham qidiradi."""
    cotton_q = is_cotton_oil_question(question)
    if not cotton_q and not _cotton_like(sql):
        return sql

    def repl(m):
        if m.group("not"):
            return m.group(0)
        pat = m.group("pat")
        col = m.group("col")
        if "product_name" not in col.lower():
            return m.group(0)
        if cotton_q or _cotton_like(pat):
            return _COTTON_STRONG
        return m.group(0)

    return _LIKE.sub(repl, sql)


def rewrite_like(sql: str) -> str:
    """Qolgan LIKE larni Unicode-aware ufold() ga o'giradi."""

    def repl(m):
        if m.group(0).lower().startswith("ufold"):
            return m.group(0)
        not_kw = "NOT " if m.group("not") else ""
        col = m.group("col")
        pat = m.group("pat")
        return f"ufold({col}) {not_kw}LIKE ufold({pat})"

    return _LIKE.sub(repl, sql)


def tighten_executed_only(sql: str, question: str) -> str:
    """'faqat ijro etilgan' qisman yetkazilganlarni qo'shmasin."""
    q = ufold(question or "")
    strict = ("faqat ijro" in q) or ("tolko ispol" in q) or ("только исполнен" in (question or "").lower())
    if not strict:
        return sql
    sql = sql.replace(", 'Исполнен(Частично)'", "")
    sql = sql.replace("'Исполнен(Частично)', ", "")
    return sql


def prepare_sql(sql: str, question: str = "") -> str:
    if not sql:
        return sql
    sql = strengthen_product_likes(sql, question)
    sql = tighten_executed_only(sql, question)
    sql = rewrite_like(sql)
    return sql


# ── Gemini promptiga qo'shimcha qidiruv qoidalari ──────────────────
def search_hints(question: str) -> str:
    lines = [
        "QIDIRUV QOIDALARI / ПРАВИЛА ПОИСКА:",
        "- SQLite COLLATE NOCASE кириллни кичик ҳарф қилмайди. Маҳсулот номи русча ва бош ҳарфда: 'Хлопковое масло', 'Масло хлопковое'.",
        "- Apostrof bazada oddiy ' emas, Unicode ' (U+2018): Farg'ona, Mo'jotat. '%Mo%jotat%' yoki '%Farg%ona%' ishlating.",
        "- Bir bitimni ikki marta sanamang. Broker uchun: WHERE seller_broker=X OR buyer_broker=X (UNION ALL emas).",
        "- savdo/sotgan/продажи = faqat seller_inn. xarid/olgan/покуп = faqat buyer_inn.",
        "- 'faqat ijro etilgan' = deal_status = 'Исполнен' aniq. 'Исполнен(Частично)' va 'Аннулирован' ni qo'shmang.",
        "- Eksport summasini so'mda so'rasa, deal_sum_uzs (dollar * shu kundagi kurs) ishlating, yalang deal_sum emas.",
        "- 0 qator yoki COUNT=0 bo'lsa raqam to'qimang. 'yo'q' deb ayting.",
        "- Mavjud bo'lmagan sana/yil (masalan 2018, 2030) → 0 qator. Bu to'g'ri javob, raqam to'qilmaydi.",
        "- Bitim raqami (masalan 604000) so'ralsa: deals.deal_id. Shartnoma raqami (100001–106616): contracts.contract_id.",
        "- O'zbekcha tovar nomini ruscha nom bilan qidiring: paxta→хлопок, sement→цемент, shakar→сахар, un→мука.",
    ]
    # Tarjima qilingan so'zlar bo'lsa, ularni aniq ko'rsatamiz.
    terms = translate_terms(question)
    if terms:
        pairs = ", ".join(f"{uz}→{ru}" for ru, uz in terms)
        lines.append(f"- Bu savoldagi tovar nomlari bazada ruscha: {pairs}. Shu ruscha shaklni qidiring.")
    if is_cotton_oil_question(question):
        lines.append(
            "- Bu savol PAXTA YOG'I haqida. product_name: 'Хлопковое масло' YOKI 'Масло хлопковое'. "
            "Kungaboqar (подсолнечн) va shrotni QO'SHMANG."
        )
    qf = ufold(question or "")
    if "toshkent shah" in qf:
        lines.append("- Toshkent shahri va Toshkent viloyati BOSHQA-BOSHQA. Shahar so'ralsa viloyatni chiqarib tashlang.")
    return "\n".join(lines)


def as_telegram_html(text: str) -> str:
    """Javobni Telegram HTML <pre> sifatida berish (SQL '_' yeb qo'yilmasin)."""
    cleaned = text.replace("**", "").replace("```sql", "").replace("```", "")
    # quote=False: Telegram HTML &#x27; ni ishonchli ochmaydi, SQL esa qo'shtirnoqqa to'la.
    return "<pre>" + html.escape(cleaned, quote=False) + "</pre>"
