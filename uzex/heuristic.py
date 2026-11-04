# -*- coding: utf-8 -*-
"""
Heuristic Text-to-SQL fallback when Gemini is not available (no API key or no internet).
Covers 80% of hackathon questions via regex patterns.
"""
import re

def detect_lang(text):
    has_cyr = bool(re.search(r"[а-яё]", text.lower()))
    # Uzbek markers
    uz_words = ["qancha", "qaysi", "broker", "bitim", "yilda", "sotuvchi", "xaridor", "narx", "eng", "ko'p", "kam"]
    ru_words = ["сколько", "какой", "брокер", "сделк", "году", "продавец", "покупатель", "цена", "самый"]
    uz_score = sum(1 for w in uz_words if w in text.lower())
    ru_score = sum(1 for w in ru_words if w in text.lower())
    if has_cyr and ru_score >= uz_score:
        return "ru"
    if uz_score > ru_score:
        return "uz"
    return "ru" if has_cyr else "uz"

def extract_inn(text):
    # INN is 9 digits
    m = re.search(r"\b\d{9}\b", text)
    return m.group(0) if m else None

def extract_broker(text):
    m = re.search(r"\bBK\d{3}\b", text, re.IGNORECASE)
    return m.group(0).upper() if m else None

def extract_year(text):
    m = re.search(r"\b(202[2-6])\b", text)
    return m.group(1) if m else None

def extract_product(text):
    # naive: known products list from DB
    products_keywords = {
        "sement": "цемент",
        "tsement": "цемент",
        "цемент": "цемент",
        "paxta": "хлопок",
        "хлопок": "хлопок",
        "yog": "масло",
        "масло": "масло",
        "benzin": "бензин",
        "бензин": "бензин",
        "karbamid": "карбамид",
        "полиэтилен": "полиэтилен",
        "полипропилен": "полипропилен",
        "shrot": "шрот",
        "шрот": "шрот",
        "soda": "сода",
        "qatron": "qatron",
        "mis": "медный",
        "мед": "медный",
        "truba": "труба",
        "quvur": "труба",
    }
    low = text.lower()
    for k, v in products_keywords.items():
        if k in low:
            return v
    return None

def heuristic_sql(question: str):
    """
    Returns dict with keys like generate_sql: sql, explanation, language, needs_data
    """
    lang = detect_lang(question)
    ql = question.lower()
    inn = extract_inn(question)
    broker = extract_broker(question)
    year = extract_year(question)
    product = extract_product(question)

    # Helper date filter
    def date_filter(y):
        if y:
            return f"deal_date BETWEEN '{y}-01-01' AND '{y}-12-31'"
        return "1=1"

    # Patterns

    # 1. Broker most deals
    if ("broker" in ql or "брокер" in ql) and ("eng ko" in ql or "больше" in ql or "ko'p" in ql or "топ" in ql or "лучший" in ql or "qaysi" in ql):
        if year:
            sql = f"SELECT seller_broker AS broker, COUNT(*) AS cnt FROM deals WHERE {date_filter(year)} GROUP BY seller_broker ORDER BY cnt DESC LIMIT 5;"
        else:
            sql = "SELECT seller_broker AS broker, COUNT(*) AS cnt FROM deals GROUP BY seller_broker ORDER BY cnt DESC LIMIT 5;"
        exp = f"Brokerlar bo'yicha bitimlar soni ({year or 'barcha yillar'})" if lang=="uz" else f"Количество сделок по брокерам ({year or 'все годы'})"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 2. Specific broker count
    if broker and ("nechta" in ql or "qancha" in ql or "сколько" in ql or "count" in ql or "bitim" in ql or "сдел" in ql):
        sql = f"SELECT COUNT(*) AS cnt FROM deals WHERE seller_broker='{broker}' OR buyer_broker='{broker}';"
        if year:
            sql = f"SELECT COUNT(*) AS cnt FROM deals WHERE (seller_broker='{broker}' OR buyer_broker='{broker}') AND {date_filter(year)};"
        exp = f"{broker} brokeri ishtirokidagi bitimlar soni" if lang=="uz" else f"Количество сделок с участием брокера {broker}"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 3. INN based queries (buyer or seller)
    if inn:
        # Determine if buyer or seller mention
        if any(w in ql for w in ["sotuvchi", "продавец", "sotgan", "продал"]):
            col = "seller_inn"
        elif any(w in ql for w in ["xaridor", "покупатель", "olgan", "купил", "xarid"]):
            col = "buyer_inn"
        else:
            # Check question contains "xarid" or "продаж" context? Default to buyer if ambiguous but try both via OR? Better ask LLM, but heuristic: try buyer
            # For generic "qancha bitim" we count both
            if "qancha" in ql or "сколько" in ql or "jami" in ql or "сумма" in ql or "summa" in ql:
                # total sum/count for this INN as either side
                if any(x in ql for x in ["summa", "сумма", "total", "jami", "общая"]):
                    # sum query
                    if year:
                        sql = f"SELECT SUM(deal_sum) AS total_sum, COUNT(*) AS cnt FROM deals WHERE (seller_inn='{inn}' OR buyer_inn='{inn}') AND {date_filter(year)} AND deal_status != 'Аннулирован(Не оплачен)';"
                    else:
                        sql = f"SELECT SUM(deal_sum) AS total_sum, COUNT(*) AS cnt FROM deals WHERE seller_inn='{inn}' OR buyer_inn='{inn}';"
                    exp = f"STIR {inn} bo'yicha jami summa va bitimlar soni" if lang=="uz" else f"Общая сумма и количество сделок по ИНН {inn}"
                    return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}
                else:
                    if year:
                        sql = f"SELECT COUNT(*) AS cnt FROM deals WHERE (seller_inn='{inn}' OR buyer_inn='{inn}') AND {date_filter(year)};"
                    else:
                        sql = f"SELECT COUNT(*) AS cnt FROM deals WHERE seller_inn='{inn}' OR buyer_inn='{inn}';"
                    exp = f"STIR {inn} bo'yicha bitimlar soni" if lang=="uz" else f"Количество сделок по ИНН {inn}"
                    return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}
            else:
                col = "buyer_inn"
        # Simple count/sum with year filter
        if any(w in ql for w in ["summa", "сумма", "total", "jami"]):
            if year:
                sql = f"SELECT SUM(deal_sum) AS total_sum FROM deals WHERE {col}='{inn}' AND {date_filter(year)} AND deal_status != 'Аннулирован(Не оплачен)';"
            else:
                sql = f"SELECT SUM(deal_sum) AS total_sum FROM deals WHERE {col}='{inn}';"
            exp = f"STIR {inn} bo'yicha jami summa ({col})" if lang=="uz" else f"Общая сумма по ИНН {inn} ({col})"
        else:
            if year:
                sql = f"SELECT COUNT(*) AS cnt, SUM(deal_sum) AS total FROM deals WHERE {col}='{inn}' AND {date_filter(year)};"
            else:
                sql = f"SELECT COUNT(*) AS cnt FROM deals WHERE {col}='{inn}';"
            exp = f"STIR {inn} bo'yicha ma'lumotlar" if lang=="uz" else f"Данные по ИНН {inn}"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 4. Product based most expensive/cheapest
    if product and any(w in ql for w in ["eng qimmat", "eng arzon", "самый дорогой", "самый дешевый", "дорог", "дешев", "qimmat", "arzon", "min", "max"]):
        is_max = any(w in ql for w in ["qimmat", "дорог", "max", "высокая", "юқори"])
        is_min = any(w in ql for w in ["arzon", "дешев", "дешёвый", "past", "низкая", "min"])
        order = "DESC" if is_max and not is_min else "ASC"
        if "arzon" in ql and "qimmat" in ql or "дорог" in ql and "дешев" in ql:
            # both cheapest and most expensive
            sql = f"SELECT deal_id, deal_date, product_name, (deal_sum/(quantity*lot)) AS unit_price, deal_sum, quantity, lot, unit FROM deals WHERE product_name LIKE '%{product}%' COLLATE NOCASE AND {date_filter(year)} ORDER BY unit_price ASC LIMIT 1;"
            exp = f"{product} bo'yicha eng arzon bitim" if lang=="uz" else f"Самая дешёвая сделка по {product}"
            return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}
        else:
            sql = f"SELECT deal_id, deal_date, product_name, (deal_sum/(quantity*lot)) AS unit_price, deal_sum, quantity, unit FROM deals WHERE product_name LIKE '%{product}%' COLLATE NOCASE AND {date_filter(year)} ORDER BY unit_price {order} LIMIT 5;"
            exp = f"{product} bo'yicha {'eng qimmat' if order=='DESC' else 'eng arzon'} bitimlar" if lang=="uz" else f"Самые {'дорогие' if order=='DESC' else 'дешёвые'} сделки по {product}"
            return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 5. Product count
    if product and any(w in ql for w in ["nechta", "qancha", "сколько", "count", "soni"]):
        sql = f"SELECT COUNT(*) AS cnt, SUM(deal_sum) AS total FROM deals WHERE product_name LIKE '%{product}%' COLLATE NOCASE AND {date_filter(year)};"
        exp = f"{product} mahsuloti bo'yicha bitimlar soni va summasi" if lang=="uz" else f"Количество и сумма сделок по {product}"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 6. Total deals per year
    if any(w in ql for w in ["jami bitim", "всего сделок", "общее количество", "nechta bitim"]):
        if year:
            sql = f"SELECT COUNT(*) AS cnt, SUM(deal_sum) AS total_sum FROM deals WHERE {date_filter(year)};"
        else:
            # by year
            sql = "SELECT strftime('%Y', deal_date) AS yil, COUNT(*) AS cnt, SUM(deal_sum) AS total FROM deals GROUP BY strftime('%Y', deal_date) ORDER BY yil;"
        exp = f"{year or 'Yillar'} bo'yicha jami bitimlar" if lang=="uz" else f"Всего сделок за {year or 'все годы'}"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 7. Export deals
    if "eksport" in ql or "экспорт" in ql:
        if year:
            sql = f"SELECT COUNT(*) AS cnt, SUM(deal_sum_uzs) AS total_uzs FROM deals_enriched WHERE contract_type='Экспортный' AND {date_filter(year)};"
        else:
            sql = "SELECT contract_type, COUNT(*) AS cnt, SUM(deal_sum_uzs) AS total_uzs FROM deals_enriched GROUP BY contract_type;"
        exp = "Eksport bitimlari soni va so'mdagi summasi" if lang=="uz" else "Количество и сумма экспортных сделок в сумах"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 8. Top products
    if any(w in ql for w in ["eng ko'p sotilgan", "популярный товар", "топ товар", "eng ko'p bitim"]):
        if year:
            sql = f"SELECT product_name, COUNT(*) AS cnt FROM deals WHERE {date_filter(year)} GROUP BY product_name ORDER BY cnt DESC LIMIT 10;"
        else:
            sql = "SELECT product_name, COUNT(*) AS cnt FROM deals GROUP BY product_name ORDER BY cnt DESC LIMIT 10;"
        exp = "Eng ko'p sotilgan tovarlar" if lang=="uz" else "Самые популярные товары"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 9. Region
    region_map = {
        "toshkent": "Toshkent",
        "ташкент": "Ташкент",
        "samarqand": "Samarqand",
        "самарканд": "Самарканд",
        "fergana": "Farg‘ona",
        "farg'ona": "Farg‘ona",
        "fargona": "Farg‘ona",
        "фергана": "Фергана",
        "namangan": "Namangan",
        "наманган": "Наманган",
        "buxoro": "Buxoro",
        "бухара": "Бухара",
        "andijon": "Andijon",
        "андижан": "Андижан",
    }
    region_found = None
    for k, v in region_map.items():
        if k in ql:
            region_found = v
            break
    if region_found and any(w in ql for w in ["region", "viloyat", "область", "hudud"]):
        sql = f"SELECT COUNT(*) AS cnt FROM deals WHERE region LIKE '%{region_found}%' AND {date_filter(year)};"
        exp = f"{region_found} bo'yicha bitimlar" if lang=="uz" else f"Сделки по региону {region_found}"
        return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # 10. General fallback: try product LIKE with first keyword
    # Extract first meaningful word (>3 chars)
    words = re.findall(r"\b\w{4,}\b", question)
    if words:
        kw = words[0]
        # avoid stopwords
        stop = {"qancha", "qaysi", "nechta", "qachon", "qayer", "uchun", "bo'yicha", "сколько", "какой", "какая"}
        if kw.lower() not in stop:
            sql = f"SELECT deal_id, deal_date, product_name, deal_sum, quantity, unit FROM deals WHERE product_name LIKE '%{kw}%' COLLATE NOCASE LIMIT 10;"
            exp = f"'{kw}' kalit so'zi bo'yicha qidiruv" if lang=="uz" else f"Поиск по ключевому слову '{kw}'"
            # Only if looks like product query
            if any(w in ql for w in ["tovar", "товар", "mahsulot", "produkt", "bitim", "сделк"]):
                return {"sql": sql, "explanation": exp, "language": lang, "needs_data": True}

    # Default: not understood as DB query -> greeting or help
    if any(w in ql for w in ["salom", "hello", "привет", "kim san", "кто ты"]):
        return {"sql": "", "explanation": "Greeting", "language": lang, "needs_data": False}

    # If nothing matched but question looks like data question (contains year, INN pattern, etc.) we already handled.
    # Otherwise, we can still try LLM? But heuristic says no SQL
    return {"sql": "", "explanation": "Heuristic topa olmadi — LLM kerak", "language": lang, "needs_data": False}

