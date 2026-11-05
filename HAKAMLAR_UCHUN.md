# UZEX AI Agent — hakamlar uchun qo'llanma

**Ochiq havola (ro'yxatdan o'tish yo'q, o'rnatish yo'q):**
👉 https://ai-usta-bot-omega.vercel.app

**Telegram bot:** [@uzexaihackaton_bot](https://t.me/uzexaihackaton_bot)

---

## 1. Nima qilingan (bir qarashda)

| Talab | Qanday bajarilgan |
| --- | --- |
| Havola boshqa joyda ochiladi | Brauzerda ochiladi (Vercel, mobil va desktop), Telegram bot ham bor |
| Ro'yxatdan o'tish / o'rnatish yo'q | Hech qanday login yo'q — havolani ochish kifoya |
| O'zbek VA rus tilida | Savol tili avtomatik aniqlanadi, javob o'sha tilda |
| Javoblar bazaga asoslangan | Har javob ostida **tekshirilgan SQL** va hisob-kitob formulasi |
| Ma'lumot bo'lmasa — to'qimaydi | Aniq matn: "Ma'lumotlar bazasida bunday ma'lumot mavjud emas" |
| 90 sekunddan tez | O'rtacha 0.1–2.5 s (eng sekin o'lchangan: 5.3 s) |

---

## 2. Ma'lumot bazasi

- **500 000 bitim**, davr: **2022-01-03 → 2026-10-30**
- Manbalar: `deals`, `contracts`, `participants` (14 392 kompaniya), `brokers` (120 broker), `usd_rates`
- 697 xil tovar nomi, 14 hudud, 11 o'lchov birligi
- SQLite + `deals_enriched` ko'rinishi (so'mga o'girilgan summa, birlik narxi)

**Muhim:** tovar nomlari bazada rus tilida (`Сахар белый`, `Портландцемент`), agent
o'zbekcha savolni avtomatik ruscha nomga o'giradi (`shakar` → `Сахар`, `sement` → `Цемент`).

---

## 3. Arxitektura

```
Savol (uz / ru)
      │
      ├─► 1. Tilni aniqlash            uzex/textnorm.py
      │
      ├─► 2. Anti-hallucination qatlami
      │      • unknown_product()  — tovar/mavzu bazada bormi?
      │      • unknown_region()   — hudud 14 tadan biri mi?
      │      • is_meaningless()   — matn ma'noli mi?
      │      └─ mos kelmasa → "Bunday ma'lumot mavjud emas" (SQL qurilmaydi)
      │
      ├─► 3. Evristik naqshlar (0.00–0.7 s)   uzex/heuristic.py
      │      BK kodi, STIR, bitim raqami, tovar, hudud, davr, forvard/spot,
      │      eng qimmat/arzon, top broker/kompaniya/tovar, jami aylanma…
      │
      ├─► 4. Gemini Text-to-SQL (zaxira)      uzex/agent.py
      │      7 model fallback, 2 retry, 60 s timeout, 2000 token
      │
      ├─► 5. Xavfsizlik                        uzex/db.py
      │      • faqat SELECT (is_safe_select)
      │      • faqat o'qish uchun ochilgan baza (mode=ro)
      │      • 12 s so'rov taymauti (progress handler)
      │
      ├─► 6. Bajarish → qatorlar
      │      0 qator → yaqin natijalar (yil olib tashlash, nom bo'yicha
      │                qidiruv) + "aniq mos ma'lumot topilmadi" ogohlantirishi
      │
      └─► 7. Javob: jadval + izoh + hisob-kitob + SQL + vaqt
```

**Nega ishonchli:** model faqat SQL tuzadi, raqamlarni o'zi yozmaydi. Raqamlar
bazadan qaytadi. SQL foydalanuvchiga ko'rsatiladi — hakam tekshira oladi.

---

## 4. Anti-hallucination: 5 ta qatlam

1. **Tovar tekshiruvi** — savoldagi tovar 697 nom ro'yxatida bormi. `oltin`,
   `kosmik kema`, `iPhone`, `qimmatbaho toshlar` → darhol rad javobi.
2. **Hudud tekshiruvi** — `London shahri` → "faqat O'zbekistonning 14 hududi".
3. **Ma'nosiz matn** — `asdfghjkl` → savol tushunilmadi, SQL qurilmaydi.
4. **Bo'sh natija** — 0 qator bo'lsa raqam to'qilmaydi; yaqin natijalar
   **alohida belgi bilan** ko'rsatiladi.
5. **Xavfsizlik** — model faqat `SELECT` yozadi, `DROP/DELETE/UPDATE` bloklanadi.

---

## 5. Tekshirish uchun 12 ta savol (nusxa ko'chirib yuboring)

### Javob bor (aniq raqam)

| # | Savol | Kutilgan javob |
| --- | --- | --- |
| 1 | `2024 yilda eng ko'p bitim qilgan broker kim?` | BK111 Gucham — 5 720 bitim |
| 2 | `Какой брокер провёл больше всего сделок в 2025 году?` | Top-5 jadval |
| 3 | `BK001 brokeri 2025 yilda qancha aylanma qilgan?` | 578 543 831 475.25 so'm |
| 4 | `Сколько сделок по ИНН 999971754 в 2024 году?` | SEYON KLASTER — 557 bitim |
| 5 | `Sement bo'yicha eng qimmat bitim qaysi 2023 yilda?` | 1 189 837 so'm/tonna |
| 6 | `Navoiy viloyatida 2024 yilda nechta bitim bo'lgan?` | 3 981 bitim |
| 7 | `2025 yilda nechta Forvard shartnoma bo'lgan?` | 6 619 |
| 8 | `Paxta yog'i 2025 yilda eng arzon bitim qaysi?` | 20 665 427 so'm/tonna |

### Javob yo'q (to'qimasligi SHART)

| # | Savol | Kutilgan javob |
| --- | --- | --- |
| 9 | `Oltin quymasi savdosi 2025 yilda qancha?` | "Bunday ma'lumot mavjud emas" |
| 10 | `Kosmik kema savdosi bormi?` | "Bunday ma'lumot mavjud emas" |
| 11 | `iPhone 15 narxi qancha?` | "Bunday ma'lumot mavjud emas" |
| 12 | `2018 yilda nechta bitim tuzilgan?` | "Topilmadi" + baza davri ko'rsatiladi |

**Avtomatik tekshiruv:** `python scripts/hakam_savollari.py`
(30 savol, 29 OK, 0 SQL xatosi).

---

## 6. Javob qanday ko'rinadi

```
✅ Natija (5 qator):

| broker_code | broker_nomi          | region            | bitimlar_soni |
| ----------- | -------------------- | ----------------- | ------------- |
| BK111       | "Gucham Broker" MChJ | Sirdaryo viloyati | 5 720         |
| ...

**Izoh:** Top 5 broker 2024: bitimlar soni bo'yicha...

**Hisob-kitob va manba:**
- Hajm = Soni × Lot
- Birlik narxi = Summa ÷ (Soni × Lot)
- Eksport (USD) → so'm: Summa × USD kursi (usd_rates, bitim sanasi)
- Manba: deals + contracts + usd_rates + participants/brokers

**Tekshirilgan SQL:**
SELECT b.broker_code, b.name AS broker_nomi, ...
```

---

## 7. Texnik tafsilotlar

- **Runtime:** Python 3.11, Vercel serverless (WSGI), SQLite 330 MB
- **Model:** Gemini (`gemini-3-flash-preview`), 7 model fallback zanjiri
- **Tezlik:** evristik naqshlar 0.00–0.7 s · Gemini 1–5 s · timeout 90 s
- **Kod:** `uzex/` (textnorm, answer, heuristic, agent, db, schema, etl)
  + `api/webhook.py` (yagona Vercel funksiyasi, ichida marshrutlash)
  + `web_ui.py` (veb-interfeys) + `bot.py` (Telegram)
- **Testlar:** `scripts/hakam_savollari.py` (30 savol), `scripts/test_queries.py`

---

## 8. Ma'lum cheklovlar (ochiq aytamiz)

- Baza 2022-01-03 … 2026-10-30 oralig'ini qamraydi — undan tashqari yillar bo'yicha
  ma'lumot yo'q (agent buni aytadi, raqam to'qimaydi).
- Faqat 14 hudud bo'yicha ma'lumot bor (tuman darajasida emas).
- Tovar nomlari bazada ruscha — o'zbekcha sinonimlar lug'ati orqali bog'lanadi
  (697 nom, ~200 sinonim).
- Gemini'ga bog'liq bo'lmagan evristik qatlam savollarning ~85 % ini qoplaydi;
  qolgani modelga ketadi (har doim SQL tekshiruvidan o'tadi).
