# 🛠 AI Usta Bot

**AI Usta** — buzilgan elektronika va maishiy texnikani tuzatishda yordam beruvchi
sun'iy intellekt asosidagi **Telegram-bot**. Foydalanuvchi muammoni matn, ovoz,
rasm yoki video ko'rinishida yuboradi — bot **Google Gemini** modeli yordamida
tashxis qo'yadi va bosqichma-bosqich yechim beradi. Kerak bo'lsa, joylashuvga
qarab **ustaxona, do'kon va ehtiyot qism narxlarini** Google orqali qidirib topadi.

---

## ✨ Imkoniyatlar

- 💬 **Matn, ovoz, audio, rasm, video, video-note (dumaloq video) va hujjatlar**ni tahlil qilish
- 🧠 **Gemini AI** (`gemini-3-flash-preview`) asosida tashxis va amaliy ko'rsatmalar
- 🗂 **Suhbat konteksti** — har foydalanuvchi uchun oxirgi 10 xabar eslab qolinadi
- 🔍 **Google Search integratsiyasi** — "usta, ustaxona, narx, do'kon, ehtiyot qism…"
  kabi so'rovlarda jonli qidiruv natijalari (manzil, narx) bilan javob
- 📍 **Joylashuvni qabul qilish** — koordinatani manzilga aylantiradi va tashxisni
  shahar/tuman kontekstida aniqlashtiradi
- 📱 **Usta chaqirish / buyurtma** — telefon raqamni yuborish tugmasi orqali
  buyurtma rasmiylashtirish
- 🚨 **Xavfsizlik birinchi** — yonish, tutun, tok urishi kabi xavfli holatda avval
  ogohlantirish, keyingina qadamlar
- 📬 **Log-guruh** — barcha murojaatlar (matn/media) belgilangan guruhga hisobot
  bo'lib tushadi (admin nazorati uchun)
- 🧹 `/yangi` — suhbat tarixini tozalab, yangi muammoni boshlash

## ⚙️ Qanday ishlaydi

```
Telegram foydalanuvchisi
        │  (matn / ovoz / rasm / video / joylashuv / kontakt)
        ▼
   bot.py  —  handler'lar, klaviaturalar, log, buyurtma
        │
        ▼
 ai_engine.py  —  Gemini API, suhbat tarixi, qidiruv mantiqi
        │                │
        ▼                ▼
   Gemini modeli    Google Search tool (kerak bo'lganda)
        │
        ▼
  Qisqa, amaliy, raqamlangan yechim
```

## 🚀 O'rnatish

1. **Repo'ni klonlang:**

   ```bash
   git clone https://github.com/Behruz0803/ai-usta-bot.git
   cd ai-usta-bot
   ```

2. **Virtual muhit va bog'liqliklar** (Python 3.10+):

   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **`.env` faylini yarating** va kalitlarni kiriting:

   ```ini
   TELEGRAM_TOKEN=123456789:AA...bot_tokeningiz...
   GEMINI_API_KEY=AIza...gemini_kalitingiz...
   LOG_CHAT_ID=-1001234567890        # ixtiyoriy: log tushadigan guruh ID'si
   ```

4. **Ishga tushiring:**

   ```bash
   python bot.py
   ```

## 🎛 Buyruqlar va tugmalar

| Buyruq / Tugma | Vazifasi |
|----------------|----------|
| `/start` | Botni ishga tushirish va salomlashuv |
| `/yangi` | Suhbat tarixini tozalash, yangi muammoni boshlash |
| `/yordam` | Qo'llanma va misollar |
| 📍 *Joylashuvni yuborish* | Geolokatsiya orqali aniqroq tashxis va yaqin ustaxonalarni topish |
|  *Telefon raqamni yuborish* | Usta chaqirish buyurtmasini rasmiylashtirish |
| 🔄 *Yangi muammo* | `/yangi` ning tugma ko'rinishi |
| ❓ *Qanday ishlataman?* | `/yordam` ning tugma ko'rinishi |

## 📥 Qo'llab-quvvatlanadigan xabar turlari

| Tur | Maksimal hajm | Foydalanish |
|-----|---------------|-------------|
| Matn | — | Muammo tavsifi, savollar |
| Rasm | 20 MB | Buzilgan qism, ekran xatoligi, platа surati |
| Video / video-note | 20 MB | Nosozlik jarayonini ko'rsatish |
| Ovoz / audio | 20 MB | Shovqin, g'ichirlash, ishlash tovushi |
| Hujjat | 20 MB | Instruksiya, sxema fayllari |
| Joylashuv | — | Shahar/tuman aniqlash, yaqin xizmatlarni topish |
| Kontakt | — | Buyurtma uchun telefon raqam |

## 📂 Loyiha tuzilishi

```
ai-usta-bot/
├── bot.py          # Telegram handler'lar, klaviaturalar, log va buyurtma mantiqi
├── ai_engine.py    # Gemini API, suhbat tarixi, qidiruv va media tahlil
├── prompts.py      # Sistema prompti (AI Usta shaxsi va qoidalari)
├── requirements.txt
└── README.md
```

## 🧑‍🔧 AI Usta qoidalari (qisqacha)

1. Kirish so'zlarsiz, **darhol mohiyatga** o'tadi.
2. Ma'lumot yetishmasa — faqat **kerakli savolni** beradi.
3. Xavf belgilarida **birinchi qatorda ogohlantirish** (masalan: "Darhol elektrdan uzing").
4. Yechimlarni **raqamlangan qadamlar** ko'rinishida beradi.
5. Javoblar doim **qisqa, amaliy, to'g'ridan-to'g'ri**.

## 📄 Litsenziya

Loyiha ta'lim va shaxsiy foydalanish uchun ochiq. Muallif: [@Behruz0803](https://github.com/Behruz0803).
