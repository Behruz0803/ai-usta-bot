# ☀️❄️ «To'rt fasl» — animatsion PowerPoint prezentatsiya

9 slaydli, to'liq animatsion prezentatsiya (o'zbek tilida):
zamonaviy **slide transition**'lar (Prism, Honeycomb, Glitter, Vortex, Shred,
Flip, Pan, Fragment, Ripple) va har slaydda **avtomatik kirib keluvchi obyekt
animatsiyalari** (fade / wipe / grow, staggered delay).

## Fayllar

| Fayl | Tavsif |
|------|--------|
| `yil_fasllari.pptx` | Tayyor prezentatsiya (PowerPoint 2016 / Microsoft 365 tavsiya etiladi) |
| `build_pptx.py` | Prezentatsiyani noldan yasovchi generator skript (python-pptx + OOXML timing/transition XML) |
| `assets_seasons/` | Slayd fonlari uchun 5 ta flat-vector rasm (title, spring, summer, autumn, winter) |

## Ishlatish

1. `yil_fasllari.pptx` ni yuklab oling va PowerPoint'da oching.
2. **F5** — slayd-shou; o'tishlar va animatsiyalar avtomatik ijro etiladi.

## Qayta generatsiya qilish

```bash
pip install python-pptx pillow
python3 build_pptx.py   # natija: yil_fasllari.pptx
```

Skript matn, rang va effektlarni `ANIMS` / `TRANS` lug'atlaridan boshqaradi —
osongina moslashtirish mumkin.
