# -*- coding: utf-8 -*-
"""Evristik (Gemini'siz) savol → SQL.

Nima uchun kerak:
  * Gemini 503/429 bersa yoki kalit bo'lmasa — bot baribir javob berishi shart.
  * Auditda "BK001", "Sement narxlari", "Eng yirik savdo" kabi qisqa savollar
    salom deb o'qilib, foydali javob berilmagan. Endi ular aniq naqsh bilan
    ushlanadi.

`confident=True` — naqsh aniq, Gemini'siz ham ishonchli (masalan STIR yoki BK kod).
`confident=False` — taxminiy; avval Gemini sinaladi.
"""
import calendar
import re
from functools import lru_cache

from .textnorm import translate_terms, ufold

# ── Til ────────────────────────────────────────────────────────────
def detect_lang(text):
    from .textnorm import detect_language
    return detect_language(text)


# ── Ekstraktorlar ─────────────────────────────────────────────────
def extract_inn(text):
    """STIR/INN — 9 xonali raqam (yil, summa emas)."""
    for m in re.finditer(r"\b(\d{9})\b", text):
        val = m.group(1)
        if not val.startswith(("19", "20")):
            return val
    return None


def extract_broker(text):
    m = re.search(r"\b(BK)\s*[-]?\s*(\d{1,3})\b", text or "", re.IGNORECASE)
    return f"BK{int(m.group(2)):03d}" if m else None


def extract_year(text):
    m = re.search(r"\b(202[2-6])\b", text or "")
    return m.group(1) if m else None


def extract_any_year(text):
    m = re.search(r"\b(19\d{2}|20\d{2})\b", text or "")
    return m.group(1) if m else None


_MONTHS = (
    ("yanvar", "январ", 1),
    ("fevral", "феврал", 2),
    ("mart", "март", 3),
    ("aprel", "апрел", 4),
    ("may", "май", 5),
    ("iyun", "июн", 6),
    ("iyul", "июл", 7),
    ("avgust", "август", 8),
    ("sentabr", "сентябр", 9),
    ("sentabr", "сентябр", 9),
    ("oktabr", "октябр", 10),
    ("noyabr", "ноябр", 11),
    ("dekabr", "декабр", 12),
)


def extract_month(text):
    low = (text or "").lower().replace("’", "'").replace("‘", "'")
    for uz, ru, num in _MONTHS:
        if re.search(rf"\b{uz}", low) or re.search(rf"\b{ru}", low):
            return num
    m = re.search(r"\b(0?[1-9]|1[0-2])\s*[-/.]?\s*oy", low)
    if m:
        return int(m.group(1))
    return None


def extract_deal_or_contract(text):
    """6 xonali raqam: 100001-106616 shartnoma, 100001-604956 bitim."""
    for m in re.finditer(r"\b(\d{6})\b", text or ""):
        val = int(m.group(1))
        if 100001 <= val <= 999999:
            return val
    return None


def _period(year, month):
    if year and month:
        last = calendar.monthrange(int(year), int(month))[1]
        return (f"deal_date BETWEEN '{year}-{int(month):02d}-01' "
                f"AND '{year}-{int(month):02d}-{last:02d}'",
                f"{year}-{int(month):02d}")
    if year:
        return f"deal_date BETWEEN '{year}-01-01' AND '{year}-12-31'", str(year)
    return "1=1", "barcha yillar" if True else ""


def _done(sql, exp, lang, confident=True):
    return {
        "sql": sql,
        "explanation": exp,
        "language": lang,
        "needs_data": True,
        "confident": confident,
    }


def _no_data(lang, reason, confident=False):
    return {
        "sql": "",
        "explanation": reason,
        "language": lang,
        "needs_data": False,
        "confident": confident,
    }



# Xizmat so'zlari — kompaniya nomi bo'lishi mumkin emas
_STOP = {
    "qancha", "nechta", "qaysi", "kim", "haqida", "boyicha", "uchun", "yilda", "yil",
    "jami", "summa", "summasi", "bitim", "bitimlari", "savdo", "savdosi", "aylanma",
    "aylanmasi", "kompaniya", "kompaniyasi", "korxona", "statistika", "malumot",
    "malumotlari", "bormi", "kop", "eng", "top", "barcha", "davr", "davrlar",
    "viloyat", "viloyati", "shahar", "tuman", "respublika", "hudud", "tovar",
    "mahsulot", "narx", "narxi", "yangi", "kerak", "menga", "mening", "qanday",
    "davomida", "oraali", "oralig", "yaqin", "keyingi", "oldingi", "birinchi",
    "сколько", "какой", "какая", "какие", "сделк", "сделки", "компани", "предприят",
    "информация", "есть", "данные", "общая", "сумма", "оборот", "году", "год",
    "все", "всего", "итого", "регион", "област", "город", "товар", "цена",
    "покажи", "скажи", "найди", "про", "за", "по", "как", "что", "где",
}

# ── Keng tarqalgan imlo xatolari ───────────────────────────────────
_TYPO_MAP = {
    "bakor": "bekor", "bekr": "bekor", "annulirovan": "аннулирован",
    "bitm": "bitim", "bitmi": "bitim", "shartoma": "shartnoma", "shartnom": "shartnoma",
    "brokr": "broker", "brokker": "broker", "kmpaniya": "kompaniya", "kompaniy": "kompaniya",
    "sementt": "sement", "pxta": "paxta", "paxtaa": "paxta", "shakr": "shakar",
    "bugdoy": "bug'doy", "bug'doy": "bug'doy", "narxi": "narx", "nari": "narx",
    "qanch": "qancha", "necht": "nechta", "qysi": "qaysi", "qay": "qaysi",
    "yildaa": "yilda", "yilida": "yilida", "экспортн": "экспорт",
}


def fix_typos(text):
    """Keng tarqalgan imlo xatolarini tuzatadi (so'z chegarasi bilan)."""
    if not text:
        return text
    out = text
    for wrong, right in _TYPO_MAP.items():
        out = re.sub(rf"(?<![\w]){re.escape(wrong)}(?![\w])", right, out, flags=re.IGNORECASE)
    return out


def _strip_topic_words(text):
    """Suhbat mavzusiga oid so'zlarni olib tashlaydi — qolgani nom bo'ladi."""
    q = ufold(text)
    out = q
    for w in _TOPIC_WORDS:
        out = re.sub(rf"(?<![\w]){re.escape(w)}(?![\w])", " ", out)
    return re.sub(r"\s+", " ", out).strip()


_TOPIC_WORDS = set(_STOP) | {
    "savdo", "savdosi", "savdolar", "aylanma", "aylanmasi", "tovar", "tovari",
    "mahsulot", "mahsuloti", "narx", "narxi", "narxlari", "bitim", "bitimlar",
    "shartnoma", "shartnomalar", "kompaniya", "korxona", "broker", "usta",
    "malumot", "malumotlar", "statistika", "hisobot", "raqam", "raqami", "kodi",
    "eksport", "import", "valyuta", "dollar", "som", "sum", "kg", "tonna",
    "сделк", "сделки", "товар", "товара", "цена", "цены", "компани", "предприят",
    "брокер", "экспорт", "импорт", "информация", "данные", "статистика",
    "qimmatbaho", "qimmat", "arzon", "tosh", "toshlar", "kim", "qaysi",
    "narx", "narxi", "narxlari", "qancha", "nechta", "bormi", "kerak",
}



# ── Bazadagi tovar nomlari (tekshirilgan ro'yxat) ─────────────────
# Faqat shu nomlar bazada bor; mos kelmasa — "ma'lumot topilmadi".
PRODUCT_WORDS = """
цемент портландцемент известь гипс кирпич шифер бетон раствор гравий щебень песок
арматура металлопрокат прокат профиль труба трубопровод лист сталь чугун лом алюминий
кабель провод катанка уголок швеллер
бензин дизельное дизтопливо топливо керосин мазут битум масло смазка солярка
газ пропан бутан метан кислород азот аргон
полиэтилен полипропилен поливинилхлорид полистирол пластик пластмасса полимер
смола каучук резина минеральное удобрение селитра карбамид мочевина аммиак
кислота щелочь сода соль сульфат нитрат фосфат хлор сера
пшеница пшеничная мука рожь ячмень овес кукуруза рис просо сорго отруби комбикорм
хлопок хлопковое волокно хлопок-сырец пряжа нить ткань вата
сахар масло растительное подсолнечное соевое семена шрот жмых
мясо говядина баранина курица куриное рыба яйцо молоко сыр творог кефир
фрукты яблоко груша виноград дыня арбуз персик абрикос слива вишня гранат лимон
овощ картофель лук морковь помидор томат огурец капуста свекла перец баклажан
ягоды изюм орех миндаль фисташка арахис
кожа шерсть шелк каракуль пух перо
пиломатериал древесина фанера доска брус шпала
стекло керамика плитка сантехника
нефть нефтепродукт газоконденсат
уголь торф
""".split()

# Tovar bo'lmagan mavzular — bazada YO'Q, darhol "topilmadi"
NON_PRODUCT_WORDS = """
олтин oltin золото алмаз brillant бриллиант quymasi quyma kumush серебро платина
kosmik kosmos spacex ракета samolyot самолет avtomobil автомобиль mashina машина
telefon телефон noutbuk ноутбук kompyuter компьютер televizor телевизор
dori лекарство dorixona аптека tibbiyot медицина
""".split()


# Bazaga aloqasiz mavzular — "qimmatbaho toshlar", "iPhone narxi" kabi.
OFF_TOPIC_WORDS = """
tosh toshlar qimmatbaho brilliant olmos алмаз бриллиант ювелир zargarlik
telefon смартфон iphone samsung noutbuk ноутбук kompyuter компьютер
mashina автомобиль avtomobil машина moto velosiped велосипед
futbol спорт sport kino film musiqa концерт o'yin игра
uy uy-joy квартира kvartira недвижимость ipoteka ипотека kredit кредит
ob-havo погода sayohat туризм restoran ресторан kafe
dori лекарство dorixona аптека shifokor врач tibbiyot медицина
kosmik kosmos spacex ракета samolyot самолет poyezd поезд
elektr ток электроэнергия suv вода isitish отопление
""" .split()


@lru_cache(maxsize=1)
def _db_product_names():
    """Bazadagi barcha product_name (bir marta o'qiladi, 0.02 s)."""
    try:
        import sqlite3
        from .db import ensure_db
        conn = sqlite3.connect(str(ensure_db()))
        try:
            rows = conn.execute("SELECT DISTINCT product_name FROM deals").fetchall()
        finally:
            conn.close()
        return tuple(ufold(r[0] or "") for r in rows if r[0])
    except Exception:
        return ()


def unknown_product(question):
    """Savolda bazada yo'q tovar so'ralganmi?

    Faqat aniq signal bo'lsa True qaytaradi:
      * NON_PRODUCT_WORDS ichida so'z bor (oltin, kosmik, telefon…), YOKI
      * savol "tovar turi" so'zlaridan iborat, lekin hech biri bazada yo'q.
    "2025 yil jami aylanma" kabi tovarsiz savollarga tegmaydi.
    """
    q = " " + ufold(question) + " "
    if re.search(r"\bbk\s*\d|\bstir\b|\binn\b|\b\d{8,9}\b", q):
        return False
    words = set(re.findall(r"[a-zа-я']{4,}", q))
    if not words:
        return False
    if words & set(NON_PRODUCT_WORDS):
        return True
    # Bazaga umuman aloqasiz lug'at (sport, mashina, telefon, oltin…) —
    # "qimmatbaho toshlar" kabi savollar "eng yirik bitim" bo'lib ketmasin.
    if words & set(OFF_TOPIC_WORDS):
        return True
    names = _db_product_names()
    if not names:
        return False
    products = [w for w in words if w in PRODUCT_WORDS]
    if not products:
        return False  # tovar so'zi yo'q — bu boshqa turdagi savol
    for w in products:
        if any(w[:5] in n for n in names):
            return False
    return True


def is_meaningless(question):
    """Ma'nosiz (gibberish) yoki mavzuga aloqasiz so'rovni aniqlaydi.

    Audit: "asdfghjkl nimadir" kabi matnga bot 10 ta tasodifiy kompaniya
    ko'rsatgan. Bunday so'rovga aniq "tushunmadim" javobi berilishi kerak.
    """
    q = fix_typos(question or "")
    core = _strip_topic_words(q)
    # Mavzu so'zlari olib tashlangandan keyin mazmunli lotin/kirill so'z qoldimi?
    words = re.findall(r"[A-Za-z\u0400-\u04FF]{4,}", core)
    if not words:
        return False  # faqat mavzu so'zlari — normal savol
    for w in words:
        low = ufold(w)
        # Unli harflar kam bo'lsa (asdfghjkl) yoki 3+ bir xil harf ketma-ket
        vowels = len(re.findall(r"[aeiouаеёиоуыэюя]", low))
        if vowels == 0:
            return True
        if re.search(r"(.)\1\1", low):
            return True
        if len(low) >= 8 and vowels / len(low) < 0.2:
            return True
    return False


# ── Savol turini aniqlash ──────────────────────────────────────────
ASK_COUNT = ("nechta", "qancha", "soni", "сколько", "количество", "количеств")
ASK_SUM = ("summa", "jami", "qiymat", "сумм", "итого", "общая", "общий", "объем", "hajm")
ASK_PRICE = ("narx", "narxi", "цена", "цены", "стоимость", "qimmat", "arzon",
             "дорог", "дешев", "дешёв", "eng qimmat", "eng arzon")
ASK_TOP = ("eng ko'p", "eng kop", "top", "топ", "больше всего", "лидер", "yetakchi",
           "eng yirik", "eng katta", "наибольш", "самый больш")
REGION_WORDS = ("viloyat", "област", "region", "hudud", "shahar", "город", "respublika")
STATUS_WORDS = ("bekor", "аннулир", "otmen", "исполнен", "ijro etil", "оплачен",
                "подписан", "yopilgan", "qaytaril")

# (matnda uchraydigan nomlar, bazadagi aniq qiymat)
REGIONS = (
    ("Toshkent shahri", "Toshkent shahri"),
    ("Toshkent viloyati", "Toshkent viloyati"),
    ("Toshkent", "Toshkent shahri"),
    ("Tashkent", "Toshkent shahri"),
    ("Samarqand", "Samarqand viloyati"),
    ("Buxoro", "Buxoro viloyati"),
    ("Andijon", "Andijon viloyati"),
    ("Namangan", "Namangan viloyati"),
    ("Farg", "Farg"),
    ("Navoiy", "Navoiy viloyati"),
    ("Qashqadaryo", "Qashqadaryo viloyati"),
    ("Surxondaryo", "Surxondaryo viloyati"),
    ("Jizzax", "Jizzax viloyati"),
    ("Sirdaryo", "Sirdaryo viloyati"),
    ("Xorazm", "Xorazm viloyati"),
    ("Qoraqalpog", "Qoraqalpog"),
    # ruscha: "Навоийской областью", "в Навои", "Бухарской области"…
    ("Ташкент", "Toshkent"),
    ("Самарканд", "Samarqand"),
    ("Бухар", "Buxoro"),
    ("Андижан", "Andijon"),
    ("Наманган", "Namangan"),
    ("Ферган", "Farg"),
    ("Навои", "Navoiy"),
    ("Наваий", "Navoiy"),
    ("Навий", "Navoiy"),
    ("Навоий", "Navoiy"),
    ("Кашкадар", "Qashqadaryo"),
    ("Сурхандар", "Surxondaryo"),
    ("Джизак", "Jizzax"),
    ("Сырдар", "Sirdaryo"),
    ("Хорезм", "Xorazm"),
    ("Каракалпак", "Qoraqalpog"),
)


def extract_region(text):
    """Savoldagi hududni bazadagi aniq nomga o'giradi (uz + ru shakllari)."""
    q = ufold(text)
    best = None
    for needle, value in REGIONS:
        n = ufold(needle)
        if n and n in q and (best is None or len(n) > len(ufold(best[0]))):
            best = (needle, value)
    return best[1] if best else None


def asks(text, words):
    q = ufold(text)
    return any(ufold(w) in q for w in words)


def extract_product(text):
    """O'zbekcha/ruscha tovar nomini bazadagi ruscha shaklga o'giradi.

    Ko'p so'zli nom ustun: "paxta yog'i" -> "хлопковое масло" ("yog" emas).
    Mos kelmasa, eng o'xshash nom ("sement" -> "цемент") tanlanadi.
    """
    terms = translate_terms(text)
    if terms:
        # "tovar", "mahsulot" — umumiy so'z, tovar nomi emas
        clean = [t for t in terms if ufold(t[1]) not in _TOPIC_WORDS]
        if not clean:
            return None
        terms = clean
        # Eng uzun o'zbekcha kalit = eng aniq nom
        best = max(terms, key=lambda t: len(t[1]))
        return best[0]
    # Allaqachon ruscha yozilgan bo'lsa
    q = ufold(text)
    for ru in (
        "цемент", "портландцемент", "хлопок", "хлопковое масло", "масло хлопковое",
        "пшеница", "мука", "сахар", "карбамид", "селитра", "полиэтилен",
        "полипропилен", "бензин", "дизельное", "сжиженный газ", "шрот",
        "арматура", "профиль", "труба", "сода", "кислота", "поливинилхлорид",
        "медь", "алюминий", "пряжа", "ткань", "бумага", "стекло",
    ):
        if ufold(ru) in q:
            return ru
    return None


# ── Naqshlar ──────────────────────────────────────────────────────
def broker_card(question, lang):
    """'BK001' / 'BK001 brokeri haqida' — broker kartasi va statistikasi."""
    code = extract_broker(question)
    if not code:
        return None
    year = extract_year(question)
    year_sql = f" AND d.deal_date BETWEEN '{year}-01-01' AND '{year}-12-31'" if year else ""
    label_uz = f"{year}-yil" if year else "barcha yillar"
    label_ru = f"{year} год" if year else "все годы"
    sql = f"""
SELECT b.broker_code, b.name AS broker_nomi, b.region,
       COUNT(DISTINCT d.deal_id) AS bitimlar_soni,
       ROUND(SUM(DISTINCT d.deal_id) * 0) AS _x
FROM brokers b
LEFT JOIN deals d ON (d.seller_broker = b.broker_code OR d.buyer_broker = b.broker_code)
     AND d.deal_status != 'Аннулирован(Не оплачен)'{year_sql}
WHERE b.broker_code = '{code}'
GROUP BY b.broker_code, b.name, b.region;
""".strip()
    # Yuqoridagi yordamchi ustun kerak emas — soddaroq va tezroq so'rov:
    sql = f"""
WITH t AS (
  SELECT d.* FROM deals d
  WHERE (d.seller_broker = '{code}' OR d.buyer_broker = '{code}')
    AND d.deal_status != 'Аннулирован(Не оплачен)'{year_sql}
)
SELECT b.broker_code,
       b.name AS broker_nomi,
       b.region,
       (SELECT COUNT(*) FROM t) AS bitimlar_soni,
       ROUND((SELECT IFNULL(SUM(deal_sum_uzs), 0) FROM deals_enriched de
              WHERE (de.seller_broker = '{code}' OR de.buyer_broker = '{code}')
                AND de.deal_status != 'Аннулирован(Не оплачен)'{year_sql.replace('d.deal_date', 'de.deal_date')}), 2)
         AS jami_aylanma_som,
       ROUND((SELECT IFNULL(SUM(deal_sum_uzs), 0) FROM deals_enriched de
              WHERE de.seller_broker = '{code}' AND de.deal_status != 'Аннулирован(Не оплачен)'{year_sql.replace('d.deal_date', 'de.deal_date')}), 2)
         AS sotuvchi_tomonida_som,
       ROUND((SELECT IFNULL(SUM(deal_sum_uzs), 0) FROM deals_enriched de
              WHERE de.buyer_broker = '{code}' AND de.deal_status != 'Аннулирован(Не оплачен)'{year_sql.replace('d.deal_date', 'de.deal_date')}), 2)
         AS xaridor_tomonida_som
FROM brokers b
WHERE b.broker_code = '{code}';
""".strip()
    exp = (f"{code} broker kartasi: nomi, hududi, {label_uz} bo'yicha bitimlar soni va "
           f"so'mdagi aylanmasi (bekor qilingan bitimlar hisobga olinmagan)."
           if lang == "uz" else
           f"Карточка брокера {code}: название, регион, число сделок и оборот в сумах "
           f"за {label_ru} (аннулированные не учитываются).")
    return _done(sql, exp, lang)


def inn_card(question, lang):
    """STIR bo'yicha kompaniya kartasi va statistikasi."""
    inn = extract_inn(question)
    if not inn:
        return None
    year = extract_year(question)
    fy = f" AND deal_date BETWEEN '{year}-01-01' AND '{year}-12-31'" if year else ""
    sql = f"""
SELECT p.inn, p.name AS kompaniya, p.region, p.activity_type AS faoliyat, p.role AS roli,
       (SELECT COUNT(*) FROM deals d WHERE d.seller_inn = '{inn}'{fy}) AS sotgan_bitimlar,
       (SELECT COUNT(*) FROM deals d WHERE d.buyer_inn = '{inn}'{fy}) AS sotib_olgan_bitimlar,
       ROUND((SELECT IFNULL(SUM(deal_sum_uzs),0) FROM deals_enriched de
              WHERE de.seller_inn = '{inn}' AND de.deal_status != 'Аннулирован(Не оплачен)'{fy}), 2) AS sotgan_summasi_som,
       ROUND((SELECT IFNULL(SUM(deal_sum_uzs),0) FROM deals_enriched de
              WHERE de.buyer_inn = '{inn}' AND de.deal_status != 'Аннулирован(Не оплачен)'{fy}), 2) AS sotib_olgan_summasi_som
FROM participants p
WHERE p.inn = '{inn}';
""".strip()
    exp = (f"STIR {inn}: kompaniya kartasi, sotuvchi va xaridor sifatidagi bitimlari hamda "
           f"so'mdagi summasi{f' ({year}-yil)' if year else ''}."
           if lang == "uz" else
           f"ИНН {inn}: карточка компании, сделки как продавца и покупателя и суммы в сумах"
           f"{f' ({year} г.)' if year else ''}.")
    return _done(sql, exp, lang)


def deal_card(question, lang):
    """Bitim raqami bo'yicha to'liq kartochka."""
    num = extract_deal_or_contract(question)
    if not num:
        return None
    q = ufold(question)
    if "shartnoma" in q or "контракт" in q:
        if num > 106616:
            return _done(
                "SELECT 'shartnoma topilmadi' AS xato WHERE 0;",
                f"Shartnoma raqamlari 100001–106616 oralig'ida. {num} shartnoma emas.",
                lang,
            )
        sql = f"""
SELECT c.contract_id, c.product_name AS mahsulot, c.currency AS valyuta,
       ROUND(c.base_price, 2) AS bazaviy_narx, c.unit AS birlik, c.lot,
       c.contract_type AS turi, c.contract_form AS shakli, c.region,
       p.name AS sotuvchi, c.reg_date AS royxatga_olingan, c.valid_until AS amal_qiladi
FROM contracts c
LEFT JOIN participants p ON p.inn = c.seller_inn
WHERE c.contract_id = {num};
""".strip()
        exp = f"{num}-shartnoma kartasi: tovar, valyuta, bazaviy narx, sotuvchi."
        return _done(sql, exp, lang)

    if num > 604956:
        return _done(
            "SELECT 'bitim topilmadi' AS xato WHERE 0;",
            f"Bitim raqamlari 100001–604956 oralig'ida. {num} bitim emas.",
            lang,
        )
    sql = f"""
SELECT d.deal_id, d.deal_date AS sana, d.deal_time AS vaqt, d.product_name AS mahsulot,
       d.quantity AS soni, d.lot, d.unit AS birlik, ROUND(d.deal_sum, 2) AS summa,
       c.currency AS valyuta, ROUND(d.deal_sum_uzs, 2) AS summa_som,
       d.deal_status AS holat, d.contract_type AS turi,
       ps.name AS sotuvchi, pb.name AS xaridor,
       d.seller_broker, d.buyer_broker, d.region,
       d.payment_date AS tolov_sanasi, d.delivery_date AS yetkazish_sanasi
FROM deals_enriched d
LEFT JOIN contracts c ON c.contract_id = d.contract_id
LEFT JOIN participants ps ON ps.inn = d.seller_inn
LEFT JOIN participants pb ON pb.inn = d.buyer_inn
WHERE d.deal_id = {num};
""".strip()
    exp = (f"{num}-bitim kartasi: tovar, summa (valyutada va so'mda), sotuvchi, xaridor, holat."
           if lang == "uz" else
           f"Карточка сделки {num}: товар, сумма (в валюте и в сумах), продавец, покупатель, статус.")
    return _done(sql, exp, lang)


def product_queries(question, lang):
    """Tovar bo'yicha: narxlar, sonlar, eng qimmat/arzon."""
    product = extract_product(question)
    if not product:
        return None
    year, month = extract_any_year(question), extract_month(question)
    deal_col = "d.deal_date"
    pred, label = _period(year, month)
    pred = pred.replace("deal_date", deal_col)
    pat = f"ufold(d.product_name) LIKE ufold('%{product}%')"
    executed = "d.deal_status IN ('Исполнен','Исполнен(Частично)')"

    # "eng qimmat/arzon bitim qaysi?" — reyting ustun turadi
    # Ikkalasi ham so'ralsa ("eng qimmat VA eng arzon") — UNION bilan ikkitasini beramiz
    wants_hi = asks(question, ("qimmat", "дорог"))
    wants_lo = asks(question, ("arzon", "дешев", "дешёв"))
    if wants_hi and wants_lo and ("va" in ufold(question) or " и " in (question or "").lower()):
        sql = f"""
SELECT * FROM (
  SELECT 'eng qimmat' AS mezon, d.deal_id, d.deal_date AS sana, d.product_name AS mahsulot,
         d.unit AS birlik, ROUND(d.unit_price_uzs, 2) AS birlik_narxi_som,
         ROUND(d.deal_sum_uzs, 2) AS summa_som
  FROM deals_enriched d
  WHERE ufold(d.product_name) LIKE ufold('%{product}%')
    AND d.deal_status = 'Исполнен' AND d.unit_price_uzs > 0 AND {pred}
  ORDER BY d.unit_price_uzs DESC LIMIT 1
)
UNION ALL
SELECT * FROM (
  SELECT 'eng arzon', d.deal_id, d.deal_date, d.product_name,
         d.unit, ROUND(d.unit_price_uzs, 2), ROUND(d.deal_sum_uzs, 2)
  FROM deals_enriched d
  WHERE ufold(d.product_name) LIKE ufold('%{product}%')
    AND d.deal_status = 'Исполнен' AND d.unit_price_uzs > 0 AND {pred}
  ORDER BY d.unit_price_uzs ASC LIMIT 1
);
""".strip()
        exp = (f"'{product}' bo'yicha eng qimmat va eng arzon ijro etilgan bitim (birlik narxi, so'mda), {label}."
               if lang == "uz" else
               f"«{product}»: самая дорогая и самая дешёвая исполненные сделки, {label}.")
        return _done(sql, exp, lang)

    # Narx reytingi: tovar + qimmat/arzon so'zi yetarli ("Самый дорогой цемент").
    if asks(question, ("qimmat", "arzon", "дорог", "дешев", "дешёв")):
        cheapest = asks(question, ("arzon", "дешев", "дешёв")) and not asks(
            question, ("qimmat", "дорог", "самый дорог"))
        order = "ASC" if cheapest else "DESC"
        sql = f"""
SELECT d.deal_id, d.deal_date AS sana, d.product_name AS mahsulot, d.unit AS birlik,
       ROUND(d.unit_price_uzs, 2) AS birlik_narxi_som,
       ROUND(d.deal_sum_uzs, 2) AS summa_som,
       d.quantity AS soni, d.lot, d.deal_status AS holat, d.region
FROM deals_enriched d
WHERE ufold(d.product_name) LIKE ufold('%{product}%')
  AND d.deal_status = 'Исполнен' AND d.unit_price_uzs > 0 AND {pred}
ORDER BY d.unit_price_uzs {order}
LIMIT 5;
""".strip()
        exp = (f"'{product}' bo'yicha {'eng arzon' if cheapest else 'eng qimmat'} birlik narxidagi "
               f"ijro etilgan bitimlar (so'mda), {label}."
               if lang == "uz" else
               f"«{product}»: {'самые дешёвые' if cheapest else 'самые дорогие'} исполненные сделки, {label}.")
        return _done(sql, exp, lang)

    if asks(question, ASK_COUNT) and not asks(question, ASK_SUM):
        sql = f"""
SELECT COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.volume), 2) AS hajm,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som
FROM deals_enriched d
WHERE {pat} AND {pred};
""".strip()
        exp = (f"'{product}' bo'yicha {label} dagi bitimlar soni, hajmi va summasi (so'mda)."
               if lang == "uz" else
               f"«{product}» за {label}: число сделок, объём и сумма в сумах.")
        return _done(sql, exp, lang)

    # "eng yirik sotuvchi / kim sotgan" — tovar bo'yicha top sotuvchi
    if asks(question, ("sotuvchi", "sotgan", "продавец", "продал", "sotilgan")) and asks(
            question, ASK_TOP + ("kim", "кто", "qaysi", "какой")):
        sql = f"""
SELECT p.name AS sotuvchi, p.inn, p.region,
       COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som,
       ROUND(SUM(d.volume), 2) AS hajm
FROM deals_enriched d
JOIN participants p ON p.inn = d.seller_inn
WHERE {pat} AND d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY p.inn, p.name, p.region
ORDER BY summa_som DESC
LIMIT 5;
""".strip()
        exp = (f"'{product}' bo'yicha {label} eng yirik sotuvchilar — so'mdagi summa bo'yicha."
               if lang == "uz" else
               f"«{product}» — крупнейшие продавцы за {label} по сумме в сумах.")
        return _done(sql, exp, lang)

    # "eng qimmat tovar" — tovar turlari bo'yicha (birlik narxi emas, umumiy summa)
    if asks(question, ("qimmat", "дорог", "eng katta", "eng yirik")) and asks(
            question, ("tovar", "товар", "mahsulot", "продукт")):
        sql = f"""
SELECT d.product_name AS mahsulot, d.unit AS birlik,
       ROUND(MAX(d.deal_sum_uzs), 2) AS eng_katta_summa_som,
       ROUND(AVG(d.unit_price_uzs), 2) AS ortacha_birlik_narxi_som,
       COUNT(*) AS bitimlar_soni
FROM deals_enriched d
WHERE d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY d.product_name, d.unit
ORDER BY eng_katta_summa_som DESC
LIMIT 10;
""".strip()
        exp = (f"{label} eng qimmat bitimlar tuzilgan tovarlar (so'mdagi summa bo'yicha)."
               if lang == "uz" else f"Самые дорогие товары по сумме сделок, {label}.")
        return _done(sql, exp, lang)

    sql = f"""
SELECT d.deal_date AS sana, d.product_name AS mahsulot, d.unit AS birlik,
       d.quantity AS soni, ROUND(d.deal_sum_uzs, 2) AS summa_som,
       ROUND(d.unit_price_uzs, 2) AS birlik_narxi_som, d.deal_status AS holat, d.region
FROM deals_enriched d
WHERE {pat} AND {pred}
ORDER BY d.deal_date DESC
LIMIT 20;
""".strip()
    exp = (f"'{product}' bo'yicha {label} dagi bitimlar (oxirgi 20 ta)."
           if lang == "uz" else f"«{product}» за {label}: последние 20 сделок.")
    return _done(sql, exp, lang, confident=False)


UNKNOWN_REGION_RE = re.compile(
    r"([A-Za-z\u0400-\u04FF'\u2019-]{3,})\s+(?:shahri|shahar|viloyati|viloyat|tumani|"
    r"област\w*|город\w*|регион\w*|район\w*)", re.I)


def unknown_region(question):
    """Hudud nomi aytilgan, lekin bazadagi 14 hududga mos kelmasa (masalan London)."""
    if extract_region(question):
        return False
    m = UNKNOWN_REGION_RE.search(question or "")
    if not m:
        return False
    word = ufold(m.group(1))
    if word in _TOPIC_WORDS or word in ("butun", "barcha", "har", "qaysi", "qancha"):
        return False
    return True


def region_query(question, lang):
    region = extract_region(question)
    if not region:
        if unknown_region(question):
            reason = ("Bunday hudud bazada yo'q — birjada faqat O'zbekistonning 14 hududi "
                      "(Toshkent, Samarqand, Buxoro, Navoiy, Namangan, Farg'ona, Andijon, "
                      "Qashqadaryo, Surxondaryo, Jizzax, Sirdaryo, Xorazm, Qoraqalpog'iston, "
                      "Toshkent viloyati) bo'yicha ma'lumot bor."
                      if lang == "uz" else
                      "Такого региона в базе нет — данные есть только по 14 регионам "
                      "Узбекистана (Ташкент, Самарканд, Бухара, Навои, Наманган, Фергана, "
                      "Андижан, Кашкадарья, Сурхандарья, Джизак, Сырдарья, Хорезм, "
                      "Каракалпакстан, Ташкентская область).")
            return _no_data(lang, reason)
        return None
    year, month = extract_any_year(question), extract_month(question)
    pred, label = _period(year, month)

    # "Toshkent shahrida eng ko'p sotgan kompaniya kim?" — hudud bo'yicha top sotuvchi
    if asks(question, ("sotuvchi", "sotgan", "продавец", "компани", "korxona")) and asks(
            question, ASK_TOP + ("kim", "кто", "qaysi", "какой")):
        sql = f"""
SELECT p.name AS sotuvchi, p.inn, p.region,
       COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som
FROM deals_enriched d
JOIN participants p ON p.inn = d.seller_inn
WHERE ufold(d.region) LIKE ufold('%{region}%')
  AND d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY p.inn, p.name, p.region
ORDER BY summa_som DESC
LIMIT 5;
""".strip()
        exp = (f"{region} bo'yicha {label} eng ko'p sotgan kompaniyalar (so'mdagi summa bo'yicha)."
               if lang == "uz" else
               f"{region}: крупнейшие продавцы за {label} по сумме в сумах.")
        return _done(sql, exp, lang)

    # "qaysi tovar eng ko'p sotilgan" — hudud bo'yicha top tovar
    if asks(question, ("tovar", "товар", "mahsulot", "продукт")) and asks(question, ASK_TOP + ("ko'p", "kop")):
        sql = f"""
SELECT d.product_name AS mahsulot, COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som
FROM deals_enriched d
WHERE ufold(d.region) LIKE ufold('%{region}%')
  AND d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY d.product_name
ORDER BY bitimlar_soni DESC
LIMIT 10;
""".strip()
        exp = (f"{region} bo'yicha {label} eng ko'p bitim qilingan tovarlar."
               if lang == "uz" else f"{region}: самые торгуемые товары за {label}.")
        return _done(sql, exp, lang)

    sql = f"""
SELECT d.region, COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som,
       COUNT(DISTINCT d.seller_inn) AS sotuvchilar
FROM deals_enriched d
WHERE ufold(d.region) LIKE ufold('%{region}%') AND d.deal_status != 'Аннулирован(Не оплачен)'
  AND {pred}
GROUP BY d.region;
""".strip()
    exp = (f"{region} bo'yicha {label}: bitimlar soni, so'mdagi summasi, sotuvchilar soni."
           if lang == "uz" else
           f"{region} за {label}: число сделок, сумма в сумах, число продавцов.")
    return _done(sql, exp, lang)


def market_overview(question, lang):
    """Umumiy savollar: eng katta bitim, yillik aylanma, top broker, eksport..."""
    q = ufold(question)
    year, month = extract_any_year(question), extract_month(question)
    pred, label = _period(year, month)
    last_year = "2026"

    # Shartnoma shakli: forvard / fyuchers / spot
    form = None
    if asks(question, ("forvard", "форвард")):
        form = "Форвард"
    elif asks(question, ("fyuchers", "фьючерс", "fyuche")):
        form = "Фьючерс"
    elif asks(question, ("spot", "спот")):
        form = "Спот"
    if form:
        sql = f"""
SELECT d.contract_form AS shakl, d.contract_type AS turi,
       COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som
FROM deals_enriched d
WHERE d.contract_form = '{form}' AND {pred}
GROUP BY d.contract_form, d.contract_type;
""".strip()
        exp = (f"{form} shartnomalari, {label}: soni va so'mdagi summasi (bekor qilinganlar ham kiradi — "
               f"shakl bo'yicha statistika)."
               if lang == "uz" else
               f"Контракты «{form}», {label}: число и сумма в сумах.")
        return _done(sql, exp, lang, confident=False)

    # Bekor qilingan / annullangan bitimlar
    if asks(question, ("bekor", "бекор", "аннулир", "annul", "otmen")):
        sql = f"""
SELECT d.deal_status AS holat, COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som
FROM deals_enriched d
WHERE d.deal_status = 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY d.deal_status;
""".strip()
        exp = (f"Bekor qilingan (to'lanmagan) bitimlar, {label}: soni va summasi. "
               f"Ular umumiy aylanmaga qo'shilmaydi."
               if lang == "uz" else
               f"Аннулированные (неоплаченные) сделки, {label}: количество и сумма.")
        return _done(sql, exp, lang)

    # Eng ko'p sotilgan tovar / top sotuvchi
    if asks(question, ("tovar", "товар", "mahsulot", "продукт")) and asks(
            question, ASK_TOP + ("ko'p", "kop", "популяр", "самый")):
        sql = f"""
SELECT d.product_name AS mahsulot, COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som,
       ROUND(SUM(d.volume), 2) AS hajm, d.unit AS birlik
FROM deals_enriched d
WHERE d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY d.product_name, d.unit
ORDER BY bitimlar_soni DESC
LIMIT 10;
""".strip()
        exp = (f"{label} eng ko'p bitim qilingan tovarlar (bitimlar soni bo'yicha)."
               if lang == "uz" else f"Самые торгуемые товары за {label} по числу сделок.")
        return _done(sql, exp, lang)

    if asks(question, ("kompaniya", "компани", "korxona", "предприят", "sotuvchi", "продавец")) and asks(
            question, ASK_TOP + ("kim", "кто", "qaysi", "какой")):
        sql = f"""
SELECT p.name AS kompaniya, p.inn, p.region,
       COUNT(*) AS bitimlar_soni,
       ROUND(SUM(d.deal_sum_uzs), 2) AS summa_som
FROM deals_enriched d
JOIN participants p ON p.inn = d.seller_inn
WHERE d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY p.inn, p.name, p.region
ORDER BY summa_som DESC
LIMIT 5;
""".strip()
        exp = (f"{label} eng ko'p sotgan kompaniyalar (so'mdagi summa bo'yicha)."
               if lang == "uz" else f"Крупнейшие продавцы за {label} по сумме в сумах.")
        return _done(sql, exp, lang)

    # Aylanma / oborot
    if asks(question, ("aylan", "оборот", "оборач", "to'lov", "выручк")):
        sql = f"""
SELECT COUNT(*) AS bitimlar_soni,
       ROUND(SUM(deal_sum_uzs), 2) AS aylanma_som,
       ROUND(AVG(deal_sum_uzs), 2) AS ortacha_summa_som
FROM deals_enriched
WHERE deal_status != 'Аннулирован(Не оплачен)' AND {pred};
""".strip()
        exp = (f"{label} bo'yicha jami aylanma (so'mda), bitimlar soni va o'rtacha summa."
               if lang == "uz" else f"Оборот за {label} в сумах и число сделок.")
        return _done(sql, exp, lang)

    if asks(question, ("eksport", "экспорт")):
        sql = f"""
SELECT COUNT(*) AS eksport_bitimlar,
       ROUND(SUM(deal_sum_uzs), 2) AS summa_som,
       ROUND(SUM(CASE WHEN currency = 'Доллар США' THEN deal_sum ELSE 0 END), 2) AS summa_usd,
       ROUND(AVG(deal_sum_uzs), 2) AS ortacha_summa_som
FROM deals_enriched
WHERE contract_type = 'Экспортный' AND deal_status != 'Аннулирован(Не оплачен)' AND {pred};
""".strip()
        exp = (f"Eksport bitimlari, {label}: soni, so'mdagi va dollardagi summasi. "
               f"Dollar summasi shu kundagi kurs bo'yicha so'mga o'girilgan."
               if lang == "uz" else
               f"Экспортные сделки, {label}: количество, сумма в сумах и в долларах.")
        return _done(sql, exp, lang)

    if asks(question, ("broker", "брокер")) and asks(question, ASK_TOP + ("qaysi", "какой", "kim")):
        sql = f"""
SELECT b.broker_code, b.name AS broker_nomi, b.region,
       COUNT(*) AS bitimlar_soni
FROM deals d
JOIN brokers b ON b.broker_code = d.seller_broker OR b.broker_code = d.buyer_broker
WHERE d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
GROUP BY b.broker_code, b.name, b.region
ORDER BY bitimlar_soni DESC
LIMIT 5;
""".strip()
        exp = (f"Top 5 broker {label}: bitimlar soni bo'yicha. Har bitim bir marta sanaladi "
               f"(sotuvchi yoki xaridor tomonida)."
               if lang == "uz" else
               f"Топ-5 брокеров {label} по числу сделок.")
        return _done(sql, exp, lang)

    if asks(question, ("yirik", "katta", "qimmat", "дорог", "больш")) and asks(
            question, ("bitim", "savdo", "сделк", "shartnoma", "контракт")):
        sql = f"""
SELECT d.deal_id, d.deal_date AS sana, d.product_name AS mahsulot,
       ROUND(d.deal_sum_uzs, 2) AS summa_som, d.unit AS birlik,
       d.deal_status AS holat, ps.name AS sotuvchi, pb.name AS xaridor
FROM deals_enriched d
LEFT JOIN participants ps ON ps.inn = d.seller_inn
LEFT JOIN participants pb ON pb.inn = d.buyer_inn
WHERE d.deal_status != 'Аннулирован(Не оплачен)' AND {pred}
ORDER BY d.deal_sum_uzs DESC
LIMIT 5;
""".strip()
        exp = (f"Eng yirik bitimlar {label} — so'mdagi summa bo'yicha, 5 ta."
               if lang == "uz" else f"Крупнейшие сделки {label} по сумме в сумах.")
        return _done(sql, exp, lang)

    # Narx reytingi (tovar ko'rsatilmagan): eng qimmat / eng arzon birlik narxi
    if asks(question, ("qimmat", "arzon", "дорог", "дешев", "дешёв")) and not asks(
            question, ("kompaniya", "broker", "брокер", "сделк")):
        cheap = asks(question, ("arzon", "дешев", "дешёв"))
        order = "ASC" if cheap else "DESC"
        sql = f"""
SELECT d.deal_id, d.deal_date AS sana, d.product_name AS mahsulot, d.unit AS birlik,
       ROUND(d.unit_price_uzs, 2) AS birlik_narxi_som,
       ROUND(d.deal_sum_uzs, 2) AS summa_som, d.quantity AS soni, d.lot,
       d.deal_status AS holat
FROM deals_enriched d
WHERE d.deal_status IN ('Исполнен','Исполнен(Частично)')
  AND d.unit_price_uzs > 0 AND {pred}
ORDER BY d.unit_price_uzs {order}
LIMIT 5;
""".strip()
        exp = (f"{'Eng arzon' if cheap else 'Eng qimmat'} birlik narxidagi bitimlar (so'mda), {label}."
               if lang == "uz" else
               f"{'Самые дешёвые' if cheap else 'Самые дорогие'} сделки по цене за единицу, {label}.")
        return _done(sql, exp, lang)

    if asks(question, ("jami", "summ", "aylanma", "оборот", "всего", "итого")):
        sql = f"""
SELECT COUNT(*) AS bitimlar_soni,
       ROUND(SUM(deal_sum_uzs), 2) AS jami_summa_som,
       ROUND(AVG(deal_sum_uzs), 2) AS ortacha_summa_som,
       MIN(deal_date) AS birinchi_sana, MAX(deal_date) AS oxirgi_sana
FROM deals_enriched
WHERE deal_status != 'Аннулирован(Не оплачен)' AND {pred};
""".strip()
        exp = (f"{label} bo'yicha jami: bitimlar soni, so'mdagi summasi, o'rtacha summa "
               f"(bekor qilinganlar hisobga olinmagan)."
               if lang == "uz" else
               f"Итого за {label}: число сделок, сумма и средняя сумма в сумах.")
        return _done(sql, exp, lang)

    if year or month:
        sql = f"""
SELECT COUNT(*) AS bitimlar_soni,
       ROUND(SUM(deal_sum_uzs), 2) AS summa_som,
       COUNT(DISTINCT product_name) AS tovar_turlari,
       COUNT(DISTINCT seller_inn) AS sotuvchilar
FROM deals_enriched
WHERE deal_status != 'Аннулирован(Не оплачен)' AND {pred};
""".strip()
        exp = (f"{label} bo'yicha umumiy ko'rsatkichlar (bitimlar, summa, tovar turlari)."
               if lang == "uz" else f"Общие показатели за {label}.")
        return _done(sql, exp, lang, confident=False)
    return None


def _bigrams(s):
    s = ufold(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 2 else {s}


def _similarity(a, b):
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return 2 * len(ga & gb) / (len(ga) + len(gb))


def _proper_nouns(question):
    """Savoldagi ehtimoliy nomlar: bosh harfli, 4+ harf, raqamsiz.

    "O'zbekneftgaz aylanmasi" -> ["O'zbekneftgaz"]
    "asdfghjkl nimadir" -> ["asdfghjkl", "nimadir"] (lekin bular bazada topilmaydi)
    """
    words = re.findall(r"[A-Za-z\u0400-\u04FF][\w\u0400-\u04FF'\u2019-]{3,}", question or "")
    out = []
    for i, w in enumerate(words):
        low = ufold(w)
        if low in _STOP:
            continue
        # Bosh harfli yoki gap ichida (birinchi so'z bo'lmasa) — nom ehtimoli
        if w[0].isupper() or i > 0:
            out.append(w)
    return out


def company_search(question, lang):
    """Kompaniya nomi bo'yicha qidiruv. Topilmasa — 0 qator (to'qimaymiz)."""
    core = _strip_topic_words(question)
    names = _proper_nouns(core)
    if not names:
        return None
    name = max(names, key=len)
    tokens = [ufold(t) for t in _proper_nouns(question)]
    # SQL: har bir so'z ustuni bo'yicha LIKE, keyin Python'da o'xshashlik bo'yicha saralash
    like_sql = " OR ".join(
        f"ufold(p.name) LIKE ufold('%{t}%')" for t in tokens
    ) or f"ufold(p.name) LIKE ufold('%{ufold(name)}%')"
    sql = f"""
SELECT p.inn, p.name AS kompaniya, p.region, p.role AS roli,
       (SELECT COUNT(*) FROM deals d WHERE d.seller_inn = p.inn OR d.buyer_inn = p.inn) AS bitimlar_soni,
       ROUND((SELECT IFNULL(SUM(de.deal_sum_uzs),0) FROM deals_enriched de
              WHERE (de.seller_inn = p.inn OR de.buyer_inn = p.inn)
                AND de.deal_status != 'Аннулирован(Не оплачен)'), 2) AS summa_som
FROM participants p
WHERE {like_sql}
LIMIT 40;
""".strip()
    exp = (f"'{name}' nomi bo'yicha kompaniya qidiruvi. Topilmasa — bazada bunday kompaniya yo'q, "
           f"nom to'qilmaydi."
           if lang == "uz" else
           f"Поиск компании по названию «{name}». Если не найдено — такой компании в базе нет.")
    res = _done(sql, exp, lang, confident=False)
    # Qo'shimcha ma'lumot: poisk kaliti (keyin tekshirish uchun)
    res["search_name"] = name
    res["search_tokens"] = tokens
    return res




def filter_company_rows(rows, columns, res):
    """Kompaniya nomi bo'yicha topilgan qatorlarni o'xshashlik bilan filtrlaydi.

    "O'zbekneftgaz" bazada yo'q — LIKE '%gaz%' bilan topilgan "Gaz" kompaniyalari
    qaytmasligi kerak. Faqat haqiqiy nom o'xshashligi >= 0.55 bo'lsa qoladi.
    """
    if not rows or not res.get("search_name"):
        return rows
    name = res["search_name"]
    tokens = res.get("search_tokens") or [ufold(name)]
    kept = []
    for r in rows:
        comp = str(r["kompaniya"] or "")
        comp_fold = ufold(comp)
        # Har bir nom bo'lagi kompaniya nomida bo'lishi shart
        if not all(t in comp_fold for t in tokens):
            continue
        score = max(_similarity(name, comp), _similarity(tokens[0], comp))
        if score >= 0.55:
            kept.append(r)
    return kept


def totals_query(question, lang):
    """Umumiy ko'rsatkichlar: aylanma, bitim soni, o'rtacha summa, davr.

    `confident=False` — Gemini ham sinaladi (u aniqroq SQL tuzishi mumkin).
    """
    qn = ufold(question)
    if not asks(question, ("jami", "summ", "aylan", "оборот", "всего", "итого",
                           "статистик", "statistika", "umumiy", "общ")):
        return None
    # Tovar/hudud/kompaniya nomi tushib qolmasin: "Oltin quymasi 2025" umumiy
    # statistika EMAS — bunday savolga "107 678 bitim" deb javob berish xato.
    product = extract_product(question)
    if product or extract_region(question) or re.search(r"\bBK\s*\d{1,3}\b|\b\d{8,9}\b", question or ""):
        return None
    if not asks(question, ("jami", "umumiy", "umumiysi", "итого", "всего", "общ",
                           "aylanma", "aylanmasi", "оборот", "statistika", "статистика")):
        return None
    year, month = extract_any_year(question), extract_month(question)
    if not year and not re.search(r"\b(19|20)\d{2}\b|\b20\d{2}\s*[-–]\s*20\d{2}", question or ""):
        if not any(w in qn for w in ("jami", "aylan", "оборот", "всего", "итого", "umumiy")):
            return None
    pred, label = _period(year, month)
    sql = f"""
SELECT COUNT(*) AS bitimlar_soni,
       ROUND(SUM(deal_sum_uzs), 2) AS jami_summa_som,
       ROUND(AVG(deal_sum_uzs), 2) AS ortacha_summa_som,
       MIN(deal_date) AS birinchi_sana, MAX(deal_date) AS oxirgi_sana
FROM deals_enriched
WHERE deal_status != 'Аннулирован(Не оплачен)' AND {pred};
""".strip()
    exp = (f"{label} bo'yicha jami: bitimlar soni, so'mdagi summasi va o'rtacha summa."
           if lang == "uz" else f"Итого за {label}: сделки, сумма и средняя сумма в сумах.")
    return _done(sql, exp, lang, confident=False)


# ── Sana + summa (mavjud naqsh, kengaytirilgan) ───────────────────
def _amt(amount):
    return f"{float(amount):.4f}".rstrip("0").rstrip(".")


def _money_amount(text):
    ql = (text or "").lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    usd = re.search(
        r"(\d+(?:[.,]\d+)?)(?:\s*(ming|тысяч\w*))?\s*[-]?\s*(?:\$|usd|dollar\w*|доллар\w*)"
        r"|\$\s*(\d+(?:[.,]\d+)?)", ql)
    if not usd and re.search(r"\b(bir|один|одна)\s*[-]?\s*(?:\$|dollar\w*|доллар\w*|usd)", ql):
        return 1.0, "USD"
    if usd:
        raw = usd.group(1) or usd.group(3)
        val = float(raw.replace(",", "."))
        if usd.group(2):
            val *= 1000.0
        return val, "USD"
    uzs = re.search(
        r"(\d+(?:[.,]\d+)?)(?:\s*(ming|тысяч\w*))?\s*[-]?\s*(?:so'm\w*|somlik|som\w*|сум\w*|uzs\w*)",
        ql)
    if uzs:
        val = float(uzs.group(1).replace(",", "."))
        if uzs.group(2):
            val *= 1000.0
        return val, "UZS"
    return None, None


def extract_calendar(text):
    low = (text or "").lower().replace("’", "'").replace("‘", "'")
    m = re.search(r"\b(202[2-6])-(\d{2})-(\d{2})\b", text or "")
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](202[2-6])\b", text or "")
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    year = extract_any_year(text)
    month = extract_month(text)
    day = None
    if month:
        for uz, ru, num in _MONTHS:
            if num != month:
                continue
            found = re.search(rf"\b(\d{{1,2}})(?:\s*[-]?(?:го|chi|i))?\s*[-.]?\s*(?:{uz}|{ru})\w*", low)
            if not found:
                found = re.search(rf"\b(?:{uz}|{ru})\w*\s+(\d{{1,2}})\b", low)
            if found:
                d = int(found.group(1))
                if 1 <= d <= 31:
                    day = d
            break
    return (int(year) if year else None), month, day


def _date_pred(col, year, month, day):
    if year and month and day:
        if not (1 <= int(day) <= calendar.monthrange(int(year), int(month))[1]):
            return None, None
        iso = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        return f"{col} = '{iso}'", iso
    if year and month:
        last = calendar.monthrange(int(year), int(month))[1]
        return (f"{col} BETWEEN '{int(year):04d}-{int(month):02d}-01' "
                f"AND '{int(year):04d}-{int(month):02d}-{last:02d}'",
                f"{int(year):04d}-{int(month):02d}")
    if year:
        return f"{col} BETWEEN '{int(year)}-01-01' AND '{int(year)}-12-31'", str(year)
    return "1=1", "barcha sanalar"


def looks_like_market(question: str) -> bool:
    q = ufold(question or "")
    if any(w in q for w in (
        "$", "dollar", "доллар", "usd", "shartn", "shartom", "bitim", "сдел",
        "kontrakt", "контракт", "broker", "брокер", "stir", "инн", "so'm", "сум",
        "kurs", "курс", "qimmat", "arzon", "aksiya", "акция", "narx", "цена",
        "tovar", "товар", "kompaniya", "компани", "viloyat", "област",
    )):
        return True
    year, month, day = extract_calendar(question or "")
    return bool(year and (month or day))


def dated_money_sql(question):
    """Sana + aniq summa + valyuta: aniq mos, bo'lmasa 'yaqin' qatorlar."""
    lang = detect_lang(question)
    ql = (question or "").lower().replace("’", "'").replace("‘", "'")
    amount, money = _money_amount(question)
    year, month, day = extract_calendar(question)
    if amount is None or money is None:
        return None
    if not year:
        return None
    ranking = any(w in ql for w in ("qimmat", "arzon", "eng ko", "дорог", "дешев", "топ"))
    if ranking:
        return None

    currency = "Доллар США" if money == "USD" else "Узбекский сум"
    unit_name = "USD" if money == "USD" else "so'm"
    deal_pred, deal_label = _date_pred("d.deal_date", year, month, day)
    reg_pred, reg_label = _date_pred("reg_date", year, month, day)
    if deal_pred is None:
        return _done("SELECT 'sana xato' AS xato WHERE 0;",
                     "Sana kalendarda yo'q." if lang == "uz" else "Такой даты нет в календаре.",
                     lang)
    tol = 0.01 if amount >= 1 else 0.0001
    product = extract_product(question)
    prod_d = f" AND ufold(d.product_name) LIKE ufold('%{product}%')" if product else ""
    prod_c = f" AND ufold(product_name) LIKE ufold('%{product}%')" if product else ""
    sql = f"""
WITH exact AS (
  SELECT 'shartnoma bazaviy narxi' AS manba, CAST(contract_id AS TEXT) AS id,
         reg_date AS sana, product_name AS mahsulot, ROUND(base_price, 2) AS summa,
         currency AS valyuta, unit AS birlik, contract_type AS holat,
         ROUND(ABS(base_price - {amount}), 2) AS farq
  FROM contracts
  WHERE currency = '{currency}' AND ABS(base_price - {amount}) < {tol} AND {reg_pred}{prod_c}
  UNION ALL
  SELECT 'bitim summasi', CAST(d.deal_id AS TEXT), d.deal_date, d.product_name,
         ROUND(d.deal_sum, 2), c.currency, d.unit, d.deal_status,
         ROUND(ABS(d.deal_sum - {amount}), 2)
  FROM deals d JOIN contracts c ON c.contract_id = d.contract_id
  WHERE c.currency = '{currency}' AND ABS(d.deal_sum - {amount}) < {tol} AND {deal_pred}{prod_d}
)
SELECT * FROM exact
UNION ALL
SELECT * FROM (
  SELECT 'ANIQ EMAS — eng yaqin bitim', CAST(d.deal_id AS TEXT), d.deal_date,
         d.product_name, ROUND(d.deal_sum, 2), c.currency, d.unit, d.deal_status,
         ROUND(ABS(d.deal_sum - {amount}), 2)
  FROM deals d JOIN contracts c ON c.contract_id = d.contract_id
  WHERE c.currency = '{currency}' AND d.deal_sum > 0 AND {deal_pred}{prod_d}
    AND NOT EXISTS (SELECT 1 FROM exact)
  ORDER BY ABS(d.deal_sum - {amount})
  LIMIT 5
);
""".strip()
    exp = (f"Aniq {_amt(amount)} {unit_name} qidirildi ({deal_label or reg_label}). "
           f"«ANIQ EMAS» qatorlari — shu kundagi eng yaqin bitimlar, ular {_amt(amount)} {unit_name} emas."
           if lang == "uz" else
           f"Искалась точная сумма {_amt(amount)} {unit_name} ({deal_label or reg_label}). "
           f"Строки «ANIQ EMAS» — ближайшие сделки, это не точная сумма.")
    return _done(sql, exp, lang)


# ── Asosiy kirish ─────────────────────────────────────────────────
def heuristic_sql(question: str):
    q = fix_typos(question or "")
    lang = detect_lang(q)

    # 0) Ma'nosiz matn — bazaga aloqasi yo'q, SQL qurmaymiz (to'qib javob bermaymiz).
    if is_meaningless(q) and not looks_like_market(q):
        return _no_data(lang, "Savol tushunarsiz — bazaga aloqador savol bering")

    # 0) Sana + aniq summa
    dated = dated_money_sql(q)
    if dated:
        return dated

    # 1) Bitim / shartnoma raqami
    deal = deal_card(q, lang)
    if deal:
        return deal

    # 2) Broker kartasi
    broker = broker_card(q, lang)
    if broker:
        return broker

    # 3) STIR kartasi
    inn = inn_card(q, lang)
    if inn:
        return inn

    # 4) Tovar bo'yicha
    prod = product_queries(q, lang)
    if prod:
        return prod

    # 5) Hudud
    region = region_query(q, lang)
    if region:
        return region

    # 6) Umumiy ko'rsatkichlar (jami aylanma va h.k.)
    totals = totals_query(q, lang)
    if totals:
        return totals

    # 7) Umumiy bozor savollari
    overview = market_overview(q, lang)
    if overview:
        return overview

    # 7) Kompaniya nomi bo'yicha qidiruv (oxirgi urinish)
    company = company_search(q, lang)
    if company:
        return company

    # 8) Tushunilmadi
    return _no_data(lang, "Heuristic topa olmadi — LLM kerak")
