# UZEX AI Hackathon — Yechim tavsifi

**Loyiha:** UZEX AI Agent — birja ma'lumotlari bo'yicha Text-to-SQL agent
**Muallif:** Behruz0803
**Sana:** 2026-11-05
**Prototip:** https://ai-usta-bot-omega.vercel.app
**Telegram:** @uzexaihackaton_bot

---

## 1. Muammo

UZEX Tovar-Xomashyo birjasida 2022–2026 yillar davomida **500 000 ta bitim**
bo'lib o'tgan. Bu ma'lumotlar jadval ko'rinishida mavjud, lekin oddiy
foydalanuvchi (broker, tahlilchi, jurnalist) ulardan savol berib foydalana
olmaydi: SQL bilishi, jadval tuzilishini yodda saqlashi kerak.

Yechim: **tabiiy tilda savol berish** — o'zbek yoki rus tilida — va
**bazaga asoslangan, isbotlanadigan** javob olish.

Eng katta xavf: til modeli (LLM) **raqam to'qib chiqarishi**. Birjada noto'g'ri
raqam — bu moliyaviy zarar. Shuning uchun loyihaning asosiy tamoyili:

> **Model raqam yozmaydi. Model faqat SQL tuzadi. Raqamlar bazadan qaytadi.**

---

## 2. Ishlatilgan texnologiyalar

| Qatlam | Texnologiya | Nima uchun |
| --- | --- | --- |
| Ma'lumot | **SQLite 3** (330 MB, read-only) | Serverless muhitda fayl bilan ishlaydi, indekslar tez |
| ETL | **Python 3.11** + `csv` | 11 ta CSV → 5 jadval + `deals_enriched` ko'rinishi |
| Til modeli | **Google Gemini** (`gemini-3-flash-preview`) | Text-to-SQL, 7 model fallback zanjiri |
| Orkestrlash | **Python asyncio** | Parallel retry, timeout boshqaruvi |
| Veb | **WSGI** (Vercel Python runtime) | Sovuq start tez, qo'shimcha freymvork kerak emas |
| Bot | **python-telegram-bot 21** | Webhook rejimi |
| Deploy | **Vercel** (serverless, 300 s) | Ochiq havola, ro'yxatdan o'tish yo'q |
| Testlar | **pytest uslubidagi skriptlar** | 30 savollik hakam to'plami + 40 savollik regressiya |

**Nega aynan SQLite?** 500 000 qator uchun to'liq SQL server ortiqcha.
SQLite serverless funksiya ichida fayl sifatida ishlaydi, tarmoq kechikishi
yo'q, so'rov 10–300 ms da bajariladi. `deals_enriched` ko'rinishi og'ir
JOIN va valyuta konvertatsiyasini bir marta hisoblab, so'rovlarni soddalashtiradi.

---

## 3. Arxitektura

```
┌─────────────────────────────────────────────────────────────┐
│  KIRISH: Telegram bot (@uzexaihackaton_bot)  │  Veb (HTTPS) │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
            ┌───────────────────────┐
            │  Tilni aniqlash       │  uzex/textnorm.py
            │  uz / ru              │  (so'z chegarasi, translit)
            └───────────┬───────────┘
                        ▼
        ╔═══════════════════════════════════════════╗
        ║  ANTI-HALLUCINATION DARVOZASI (5 qatlam)  ║
        ╚═══════════════════┬═══════════════════════╝
                            ▼
   ┌────────────────────────────────────────────────────┐
   │ 1. unknown_product()  → tovar 697 nom ro'yxatida?  │
   │ 2. unknown_region()   → 14 hududdan biri?          │
   │ 3. is_meaningless()   → matn ma'nolimi?            │
   │    ↓ mos kelmasa: SQL QURILMAYDI                   │
   │    "Ma'lumotlar bazasida bunday ma'lumot mavjud    │
   │     emas" (6 ms)                                   │
   └────────────────────┬───────────────────────────────┘
                        ▼
   ┌────────────────────────────────────────────────────┐
   │ 4. EVRISTIK NAQSHLAR — uzex/heuristic.py           │
   │    BK kodi · STIR · bitim raqami · tovar · hudud   │
   │    davr · forvard/spot · eng qimmat/arzon · top    │
   │    ⏱ 0.0–0.7 s · savollarning ~85 % ini qoplaydi   │
   └────────────────────┬───────────────────────────────┘
                        ▼ (faqat naqsh topilmasa)
   ┌────────────────────────────────────────────────────┐
   │ 5. GEMINI TEXT-TO-SQL — uzex/agent.py              │
   │    7 model fallback · 2 retry · 60 s timeout       │
   │    Chiqish: faqat SELECT                          │
   └────────────────────┬───────────────────────────────┘
                        ▼
   ┌────────────────────────────────────────────────────┐
   │ 6. XAVFSIZLIK — uzex/db.py                         │
   │    is_safe_select() · mode=ro · 12 s watchdog      │
   └────────────────────┬───────────────────────────────┘
                        ▼
   ┌────────────────────────────────────────────────────┐
   │ 7. BAJARISH → qatorlar                             │
   │    0 qator → yaqin natija (yil olib tashlash,      │
   │    nom bo'yicha qidiruv) + ogohlantirish           │
   └────────────────────┬───────────────────────────────┘
                        ▼
   ┌────────────────────────────────────────────────────┐
   │ 8. JAVOB — uzex/answer.py                          │
   │    jadval + izoh + hisob-kitob asosi + SQL + vaqt  │
   └────────────────────────────────────────────────────┘
```

### Modullar

| Fayl | Vazifasi | Hajmi |
| --- | --- | --- |
| `uzex/textnorm.py` | Unicode normalizatsiya, uz↔ru atamalar lug'ati (~70 sinonim), til aniqlash | 400 qator |
| `uzex/heuristic.py` | 20+ savol naqshi, 14 hudud, 697 tovar, anti-hallucination guard | 1300 qator |
| `uzex/agent.py` | Gemini orkestrlash, fallback, yaqin natija strategiyasi | 700 qator |
| `uzex/answer.py` | Javob formati, hisob-kitob asosi, Telegram bo'laklash | 400 qator |
| `uzex/db.py` | Xavfsiz ulanish, SQL tekshiruvi, timeout watchdog | 200 qator |
| `uzex/etl.py` | 11 CSV → SQLite + `deals_enriched` + indekslar | 480 qator |
| `web_ui.py` | Veb-interfeys (WSGI), `/api/query`, `/api/health` | 220 qator |
| `bot.py` | Telegram handlerlar, uzun javobni bo'laklash | 900 qator |

---

## 4. Aniqlik qanday ta'minlangan (asosiy qism)

### 4.1. Besh qatlamli himoya

**1-qatlam — Tovar tekshiruvi.**
Bazada 697 xil tovar nomi bor (hammasi rus tilida). Foydalanuvchi `oltin`,
`kosmik kema`, `iPhone` so'rasa, savol modelga **umuman yuborilmaydi**.
Ilgari model "umumiy statistika" (107 678 bitim) qaytarib, savolga aloqasi
yo'q raqam berardi — bu hakamlar uchun diskvalifikatsiya.

**2-qatlam — Hudud tekshiruvi.**
Bazada faqat O'zbekistonning 14 hududi bor. `London shahrida qancha bitim?`
savoliga "bunday hudud yo'q, faqat 14 hudud" deb javob beriladi.
Ilgari bu savol 0 qator yoki (yanada yomoni) **butun respublika** bo'yicha
99 324 bitim qaytarardi.

**3-qatlam — Ma'nosiz matn.**
`asdfghjkl nimadir` → "savol tushunilmadi" + misollar. Unli harflar nisbati,
3× takrorlanish, lug'atda yo'q so'zlar tekshiriladi.

**4-qatlam — Bo'sh natija.**
SQL 0 qator qaytarsa yoki barcha raqamli ustunlar 0/NULL bo'lsa, agent
raqam to'qimaydi. O'rniga:
- sabab aytiladi (`So'ralgan yil bazada yo'q (2022-01-03 … 2026-10-30)`);
- yaqin natijalar **alohida belgi bilan** ko'rsatiladi:
  `⚠️ Aniq mos ma'lumot yo'q, lekin shunga yaqin javoblar bor`.

**5-qatlam — SQL xavfsizligi.**
`is_safe_select()` faqat `SELECT`/`WITH` bilan boshlanadigan so'rovni o'tkazadi.
Baza `mode=ro` (read-only) da ochiladi. Og'ir so'rovlar uchun 12 sekundlik
watchdog (`set_progress_handler`) — ilgari bitta so'rov butun serverni
300 sekundga qotirib qo'ygan edi.

### 4.2. Isbotlanuvchanlik — hakam tekshira oladi

Har bir javobda uchta mustaqil tekshiruv qatlami bor:

```
✅ Natija (5 qator):

| broker_code | broker_nomi          | region            | bitimlar_soni |
| BK111       | "Gucham Broker" MChJ | Sirdaryo viloyati | 5 720         |

**Izoh:** Top 5 broker 2024: bitimlar soni bo'yicha...

**Hisob-kitob asosi:**
- Qo'llangan filtrlar: davr: 2024 · holat: bekor qilinganlar chiqarilgan
- Formula/agregat: COUNT — yozuvlar soni; GROUP BY — guruhlash: b.broker_code;
  tartib: bitimlar_soni (kamayish); LIMIT — faqat birinchi qatorlar
- Tekshiruv: «bitimlar_soni» = 5 720 — qiymat to'g'ridan-to'g'ri bazadan
  (SQL natijasi), model yozmagan.

**Tekshirilgan SQL:**
SELECT b.broker_code, b.name AS broker_nomi, ...
GROUP BY b.broker_code, b.name, b.region
ORDER BY bitimlar_soni DESC LIMIT 5;

⏱ 302 ms
```

Hakam SQL ni nusxalab, bazada o'zi ishga tushirib tekshirishi mumkin.

### 4.3. Ikki tilli aniqlik

O'zbekcha savol → ruscha tovar nomi: `paxta yog'i` → `хлопковое масло`,
`sement` → `цемент`, `shakar` → `Сахар белый`, `o'g'it` → `удобрение`.
Lug'atda ~70 sinonim, **so'z chegarasi bilan** qidiriladi (aks holda
`Oʻzbekneftgaz` so'zi `gaz` deb o'qilib, noto'g'ri javob berardi).

Ruscha savollar: `Навоийской области`, `Навий вилоятида`, `в Навои` —
hammasi bitta `Navoiy viloyati` ga bog'lanadi.

Javob tili savol tilidan olinadi: o'zbekcha savolga o'zbekcha javob, ruscha
savolga ruscha javob (jadval sarlavhalari ham).

---

## 5. Tezkorlik

| Yo'l | Vaqt | Ulushi |
| --- | --- | --- |
| Anti-hallucination rad javobi | **0–6 ms** | soxta savollar |
| Evristik naqsh (BK, STIR, hudud, tovar) | **10–700 ms** | ~85 % savollar |
| Gemini Text-to-SQL | 1.5–3 s | murakkab/erkin savollar |
| Og'ir so'rov (watchdog) | maks 12 s | cheklangan |

Hakam talabi: **90 sekund**. Haqiqiy eng sekin javob: **16 s** emas — endi
**2.8 s** (ilgari anti-hallucination tekshiruvi modeldan keyin ishlab, 16.3 s
kutardi; endi birinchi qadam — 6 ms).

---

## 6. Test natijalari

### 6.1. Hakamlar to'plami — 30 savol

`python scripts/hakam_savollari.py`

| Ko'rsatkich | Natija |
| --- | --- |
| Jami savol | 30 (15 uz + 15 ru) |
| Muvaffaqiyatli | **30 / 30** |
| SQL xatosi | **0** |
| Soxta savol (to'g'ri rad etilgan) | **6 / 6** |
| Eng sekin javob | 2.8 s |
| O'rtacha javob | 0.4 s |

**Soxta savollar (disqualification testi):**

| Savol | Agent javobi |
| --- | --- |
| `Oltin quymasi savdosi 2025 yilda qancha?` | ❌ Bunday ma'lumot mavjud emas (6 ms) |
| `Kosmik kema savdosi bo'yicha ma'lumot bering` | ❌ Bunday ma'lumot mavjud emas |
| `iPhone 15 narxi qancha?` | ❌ Bunday ma'lumot mavjud emas |
| `STIR 000000000 bo'lgan kompaniya bitimlari` | ❌ Aynan mos ma'lumot topilmadi |
| `BK999 brokerining aylanmasi` | ❌ Aynan mos ma'lumot topilmadi |
| `2018 yilda nechta bitim tuzilgan?` | ❌ + bazada davr ko'rsatiladi |

### 6.2. Regressiya to'plami — 40 savol

Barcha avval ishlagan savollar buzilmaganini tekshiradi: **37 / 37 OK**, 0 SQL xatosi.

### 6.3. Aniqlik tekshiruvi (mustaqil)

Javoblar SQL bilan qo'lda solishtirildi. Namunalar:

| Savol | Agent javobi | SQL natijasi |
| --- | --- | --- |
| 2024 top broker | BK111 Gucham — 5 720 bitim | 5 720 ✓ |
| ИНН 999971754 (2024) | SEYON KLASTER — 557 bitim, 254.3 mlrd so'm | ✓ |
| Navoiy viloyati (2024) | 3 981 bitim, 2.18 trln so'm | ✓ |
| Forvard (2025) | 6 619 bitim, 4.42 trln so'm | ✓ |
| Sement eng qimmat (2023) | 1 189 837 so'm/tonna | ✓ |
| Paxta yog'i eng arzon (2025) | 20 665 427 so'm/tonna | ✓ |

---

## 7. Foydalanuvchi tajribasi

**Veb:** ro'yxatdan o'tish yo'q, o'rnatish yo'q — havolani ochib savol yozish.
9 ta tayyor namuna savol tugmasi. Har javobda bajarilish vaqti.

**Telegram:** @uzexaihackaton_bot — 4096 belgidan uzun javob avtomatik
bo'laklanadi (ilgari "Message is too long" xatosi berardi).

**Ochiq API:** `GET /api/query?q=Sement narxi 2024` — brauzerda ham ishlaydi.

---

## 8. Cheklovlar (ochiq aytiladi)

1. Baza **2022-01-03 … 2026-10-30** oralig'ini qamraydi. Undan tashqari
   yillar bo'yicha raqam yo'q — agent buni aytadi.
2. Faqat **14 hudud** (tuman darajasida emas).
3. Tovar nomlari bazada **ruscha** — o'zbekcha sinonimlar lug'ati orqali
   bog'lanadi (~70 sinonim, 697 nom).
4. Gemini'ga bog'liq bo'lmagan evristik qatlam savollarning ~85 % ini qoplaydi.
   Qolgani modelga ketadi — lekin har doim SQL tekshiruvidan o'tadi va
   foydalanuvchiga ko'rsatiladi.

Bu cheklovlar yashirilmaydi: agent ma'lumot yo'qligini **o'zi aytadi**,
to'qib javob bermaydi.

---

## 9. Xulosa

Loyiha uchta tamoyilga asoslangan:

1. **Ishonchlilik** — model raqam yozmaydi, faqat SQL tuzadi; 5 qatlamli
   anti-hallucination; har javobda tekshirilgan SQL.
2. **Isbotlanuvchanlik** — har javobda filtrlar, agregatlar, hisob-kitob
   asosi va SQL. Hakam mustaqil tekshira oladi.
3. **Ochiqlik** — ro'yxatdan o'tish yo'q, o'rnatish yo'q, uz + ru, 90 s dan tez.

**Natija:** 500 000 bitim ustida tabiiy tilda savol-javob, har bir raqam
bazadan olingan va tekshirilishi mumkin.
