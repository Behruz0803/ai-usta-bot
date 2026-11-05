# -*- coding: utf-8 -*-
"""Javobni formatlash: aniq natija, yaqin natija, yoki "ma'lumot yo'q".

Auditdagi muammolar:
- 4096 belgi limitidan oshib Telegram xatosi berishi (endi bo'laklab yuboriladi).
- 0 qator holatida "yo'q" deyishi, lekin foydalanuvchi nima so'ragani ko'rsatilmasligi.
- "Aynan mos topilmadi" holatida hech narsa ko'rsatmasligi.
Shu modul ikkalasini ham hal qiladi.
"""
import re

# ── Matnlar (uz/ru) ────────────────────────────────────────────────
T = {
    "no_data": {
        "uz": "Ma'lumotlar bazasida sizning shartlaringizga aynan mos ma'lumot topilmadi.",
        "ru": "В базе данных нет информации, точно соответствующей вашим условиям.",
    },
    "near_data": {
        "uz": "Aniq mos ma'lumot yo'q, lekin shunga yaqin javoblar bor:",
        "ru": "Точного совпадения нет, но есть близкие по смыслу данные:",
    },
    "near_note": {
        "uz": "Quyidagi qatorlar siz so'ragan shartga to'liq mos kelmaydi — ularni \"yaqin\" deb ko'rsatdim, aniq javob sifatida qabul qilmang.",
        "ru": "Строки ниже не полностью соответствуют вашему условию — они показаны как близкие, не как точный ответ.",
    },
    "result": {"uz": "Natija", "ru": "Результат"},
    "rows": {"uz": "qator", "ru": "строк"},
    "checked_sql": {"uz": "Tekshirilgan SQL", "ru": "Проверенный SQL"},
    "calc": {
        "uz": (
            "Hisob-kitob va manba:\n"
            "- Hajm = Soni × Lot\n"
            "- Birlik narxi = Summa ÷ (Soni × Lot)\n"
            "- Eksport (USD) → so'm: Summa × USD kursi (usd_rates, bitim sanasi)\n"
            "- Manba: deals + contracts + usd_rates + participants/brokers"
        ),
        "ru": (
            "Расчёт и источник:\n"
            "- Объём = Количество × Лот\n"
            "- Цена за единицу = Сумма ÷ (Количество × Лот)\n"
            "- Экспорт (USD) → сум: Сумма × курс USD (usd_rates на дату сделки)\n"
            "- Источник: deals + contracts + usd_rates + participants/brokers"
        ),
    },
    "zero_note": {
        "uz": "Bu 0 — bazada bunday yozuv yo'q. Raqam to'qib chiqarilmaydi.",
        "ru": "Это 0: в базе такой записи нет. Число не выдумывается.",
    },
    "note": {"uz": "Izoh", "ru": "Пояснение"},
    "truncated": {"uz": "qator ko'rsatildi", "ru": "строк показано"},
}


def _t(key, lang):
    val = T.get(key, "")
    if isinstance(val, dict):
        return val.get(lang) or val.get("uz")
    return val


# ── Raqam formatlash ───────────────────────────────────────────────
def fmt_num(v):
    """1 234 567,89 uslubida (bo'shliq — minglik ajratgich)."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "ha" if v else "yo'q"
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ")
    if isinstance(v, float):
        if v != v:  # NaN
            return "—"
        if abs(v - round(v)) < 1e-9 and abs(v) < 1e15:
            return f"{int(round(v)):,}".replace(",", " ")
        return f"{v:,.2f}".replace(",", " ")
    return str(v)


def fmt_cell(v):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return fmt_num(v)
    s = str(v).replace("|", "\\|").replace("\n", " ")
    return s


# ── Natijani "ma'lumot bormi?" deb baholash ────────────────────────
def is_no_data(rows, columns, rowcount):
    """0 qator, COUNT=0, SUM/MIN/MAX=NULL — hammasi "ma'lumot yo'q"."""
    if rowcount == 0 or not rows:
        return True
    row = rows[0]
    cols = list(columns or [])
    low = [c.lower() for c in cols]

    # Bitta qator, barcha ustunlar NULL
    if len(rows) == 1 and all(row[c] is None for c in cols):
        return True

    # Bitta qator: barcha raqamli qiymatlar 0 yoki NULL -> ma'lumot yo'q.
    # (masalan 2018-yil: bitimlar_soni=0, summa=NULL, tovar_turlari=0)
    if len(rows) == 1:
        nums = [row[c] for c in cols if isinstance(row[c], (int, float))]
        if nums and all((v == 0) for v in nums):
            return True

    # COUNT ustuni 0, qolganlari ham bo'sh
    count_idx = [i for i, c in enumerate(low) if "cnt" in c or c in ("count", "count(*)")]
    if count_idx:
        try:
            if int(row[cols[count_idx[0]]]) == 0:
                others = [row[c] for c in cols if c not in {cols[i] for i in count_idx}]
                if all(v is None or v == 0 for v in others):
                    return True
        except (TypeError, ValueError):
            pass

    # SUM NULL va COUNT 0
    if any(("sum" in c or "total" in c) for c in low) and any("cnt" in c for c in low):
        sum_cols = [c for c in cols if "sum" in c.lower() or "total" in c.lower()]
        cnt_cols = [c for c in cols if "cnt" in c.lower()]
        if sum_cols and cnt_cols:
            try:
                if all(row[c] is None for c in sum_cols) and int(row[cnt_cols[0]]) == 0:
                    return True
            except (TypeError, ValueError):
                pass
    return False


# ── Jadval ─────────────────────────────────────────────────────────
def render_table(rows, columns, max_rows=20):
    if not rows or not columns:
        return ""
    shown = rows[:max_rows]
    out = ["| " + " | ".join(str(c) for c in columns) + " |"]
    out.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for r in shown:
        out.append("| " + " | ".join(fmt_cell(r[c]) for c in columns) + " |")
    return "\n".join(out)


def uz_label(text, lang):
    """Javobda tovar nomini foydalanuvchi tilida ko'rsatish (baza ruscha).

    Faqat izoh (explanation) uchun — jadvaldagi haqiqiy nom o'zgarmaydi,
    shunda foydalanuvchi bazadagi yozuvni ham ko'radi.
    """
    if lang != "uz" or not text:
        return text
    try:
        from .textnorm import RU_UZ_LABEL, ufold
        low = ufold(text)
        for ru, uz in RU_UZ_LABEL.items():
            if ru in low:
                return f"{uz} ({text})"
    except Exception:
        pass
    return text


def _product_label(sql):
    """SQL dan qidirilgan tovar nomini ajratib oladi (izoh uchun)."""
    m = re.search(r"ufold\([\w.]+product_name\)\s+LIKE\s+ufold\('%([^%']+)%'\)", sql or "", re.I)
    return m.group(1) if m else None


def _sql_block(sql, lang):
    if not sql:
        return ""
    return f"\n\n**{_t('checked_sql', lang)}:**\n```sql\n{sql}\n```"


def _footer(explanation, lang, product=None):
    parts = []
    if product:
        explanation = uz_label(explanation, lang)
    if explanation:
        parts.append(f"**{_t('note', lang)}:** {explanation}")
    calc_lines = _t("calc", lang).split("\n")
    head = calc_lines[0].rstrip(":") + ":"
    body = "\n".join(calc_lines[1:])
    parts.append(f"**{head}**\n{body}")
    return "\n\n" + "\n\n".join(parts)


# ── Asosiy formatlash ──────────────────────────────────────────────
def format_no_data(sql, explanation, lang, elapsed_ms, table_count=None, hint=None):
    """Aniq mos ma'lumot yo'q. Yaqin natijalar bo'lsa, ular alohida ko'rsatiladi."""
    head = f"❌ {_t('no_data', lang)}"
    body = _sql_block(sql, lang)
    if explanation:
        body += f"\n\n**{_t('note', lang)}:** {explanation}"
    if hint:
        body += f"\n\n{hint}"
    timing = f"\n\n⏱ {elapsed_ms} ms | 0 {_t('rows', lang)}"
    return head + body + timing


def format_near_and_empty(sql, explanation, lang, elapsed_ms, near_rows=None,
                          near_columns=None, near_label="", near_error=None, hint=None):
    """Yaqin natijalar bor, lekin ular so'ralgan shartga mos emas."""
    head = f"⚠️ {_t('no_data', lang)}"
    parts = [head]
    if near_rows:
        parts.append(f"\n🔎 **{_t('near_data', lang)}**")
        parts.append(_t("near_note", lang))
        if near_label:
            parts.append(f"\n_{near_label}_")
        parts.append("\n" + render_table(near_rows, near_columns, max_rows=10))
    body = _sql_block(sql, lang)
    if explanation:
        body += f"\n\n**{_t('note', lang)}:** {explanation}"
    if near_error:
        body += f"\n\n⚠️ {near_error}"
    if hint:
        body += f"\n\n{hint}"
    timing = f"\n\n⏱ {elapsed_ms} ms | 0 {_t('rows', lang)}"
    return "\n".join(parts) + body + timing


def format_result(sql, rows, columns, rowcount, explanation, lang, elapsed_ms,
                  truncated=None, hint=None):
    """Aniq natija: jadval + SQL + hisob-kitob."""
    head = f"✅ **{_t('result', lang)} ({rowcount} {_t('rows', lang)}):**"
    table = render_table(rows, columns)
    if len(rows) > 20:
        table += f"\n_… {len(rows)} / {rowcount} {_t('truncated', lang)}_"

    zero_note = ""
    nums = [r[c] for r in rows for c in columns if isinstance(r[c], (int, float))]
    if nums and all(v == 0 for v in nums):
        zero_note = f"\n\n{_t('zero_note', lang)}"

    out = f"{head}\n\n{table}"
    if hint:
        out += f"\n\n{hint}"
    out += _footer(explanation, lang)
    out += zero_note
    out += _sql_block(sql, lang)
    if truncated:
        out += f"\n\n⚠️ _{truncated}_"
    out += f"\n\n⏱ {elapsed_ms} ms"
    return out


def format_error(sql, error, explanation, lang, elapsed_ms, hint=None):
    title = "⚠️ So'rovni bajarishda xato:" if lang == "uz" else "⚠️ Ошибка выполнения запроса:"
    out = f"{title} {error}"
    if explanation:
        out += f"\n\n**{_t('note', lang)}:** {explanation}"
    if hint:
        out += f"\n\n{hint}"
    out += _sql_block(sql, lang)
    out += f"\n\n⏱ {elapsed_ms} ms"
    return out


def split_message(text, limit=3900):
    """Telegram 4096 belgi limiti uchun xavfsiz bo'laklash.

    Avval bo'sh qatorlar, keyin satrlar, eng oxirida majburiy kesish.
    Markdown/HTML teglari buzilmasligi uchun <pre> bloklari ichida kesmaymiz —
    javob allaqachon <pre> ichiga o'raladi, shuning uchun chaqiruvchi tomonda
    bo'laklash amalga oshiriladi.
    """
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]
    parts = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut < limit * 0.5:
            cut = rest.rfind("\n", 0, limit)
        if cut < limit * 0.5:
            cut = rest.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        parts.append(rest)
    return parts
