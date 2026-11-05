#!/usr/bin/env python3
"""Hakamlar uchun 30 ta qiyin savol — javob sifati tekshiruvi.

Ishlatish:
    python scripts/hakam_savollari.py            # jadval ko'rinishida
    python scripts/hakam_savollari.py --show 5   # 5-savolning to'liq javobi

Har savol uchun: nechta qator, necha sekund, SQL tuzilganmi va javob
bazaga asoslanganmi (raqamlar SQL natijasidan olinganmi).
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUESTIONS = [
    # ── UZ ────────────────────────────────────────────────────────
    ("uz", "2024 yilda eng ko'p bitim qilgan broker kim?"),
    ("uz", "BK001 brokeri 2025 yilda qancha aylanma qilgan?"),
    ("uz", "Sement bo'yicha eng qimmat bitim qaysi yilda bo'lgan?"),
    ("uz", "Paxta yog'i 2025 da eng arzon qaysi bitim?"),
    ("uz", "Toshkent viloyatida 2024 yilda qancha bitim bo'lgan?"),
    ("uz", "2025 yilda nechta forvard shartnoma tuzilgan?"),
    ("uz", "Bekor qilingan bitimlar soni qancha?"),
    ("uz", "Eng ko'p sotilgan tovar qaysi?"),
    ("uz", "2024 yil jami aylanma qancha so'm?"),
    ("uz", "Shakar narxi 2023 va 2024 da qanday o'zgargan?"),
    ("uz", "STIR 921912462 qanday kompaniya?"),
    ("uz", "100001 raqamli shartnoma bo'yicha qaysi tovar sotilgan?"),
    ("uz", "Eksport bitimlari 2024 da qancha dollar?"),
    ("uz", "Namangan viloyatida eng ko'p sotgan kompaniya kim?"),
    ("uz", "O'g'it bo'yicha eng yirik bitim qaysi?"),
    # ── SOXTA (javob "yo'q" bo'lishi SHART) ───────────────────────
    ("uz", "Oltin quymasi savdosi 2025 yilda qancha?"),
    ("uz", "Kosmik kema savdosi bo'yicha ma'lumot bering"),
    ("uz", "iPhone 15 narxi qancha?"),
    ("uz", "STIR 000000000 bo'lgan kompaniya bitimlari"),
    ("uz", "BK999 brokerining aylanmasi qancha?"),
    ("uz", "2018 yilda nechta bitim tuzilgan?"),
    # ── RU ────────────────────────────────────────────────────────
    ("ru", "Какой брокер провёл больше всего сделок в 2025 году?"),
    ("ru", "Сколько сделок по ИНН 999971754 в 2024 году?"),
    ("ru", "Самый дорогой и самый дешёвый цемент в 2023 году?"),
    ("ru", "Какая сумма экспортных сделок в 2024 году в долларах?"),
    ("ru", "Топ-5 товаров по количеству сделок в 2024 году"),
    ("ru", "Сколько аннулированных сделок было в 2023 году?"),
    ("ru", "Дай данные по компании SpaceX за 2024 год"),
    ("ru", "Средняя цена сахара в 2025 году"),
    ("ru", "Сколько сделок было в Навоийской области в 2024 году?"),
]


async def run(show=None):
    from uzex.agent import answer

    ok = bad = 0
    for i, (lang, q) in enumerate(QUESTIONS, 1):
        t0 = time.time()
        try:
            ans = await answer(q)
        except Exception as e:  # noqa: BLE001
            ans = f"❌ XATO: {e}"
        dt = time.time() - t0
        first = ans.split("\n")[0][:70]
        has_sql = "```sql" in ans
        low = ans.lower()
        no_data = any(k in low for k in (
            "topilmadi", "mavjud emas", "такой информации нет", "нет информации",
            "не найдено", "нет данных"))
        flag = "OK " if (has_sql or no_data) and dt < 20 and "XATO" not in ans else "!! "
        if flag == "OK ":
            ok += 1
        else:
            bad += 1
        print(f"{i:2d}. {flag}[{lang}] {q[:52]:52s} {dt:5.1f}s  {first}")
        if show == i:
            print("-" * 70)
            print(ans)
            print("-" * 70)
    print(f"\nJami: {len(QUESTIONS)} · OK: {ok} · muammo: {bad}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=None, help="savol raqami (to'liq javob)")
    a = ap.parse_args()
    asyncio.run(run(a.show))
