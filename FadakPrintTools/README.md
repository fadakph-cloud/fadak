# ابزار چاپ فدک

مبدل فرمت فایل‌ها (تصویر، PDF، صوت، ویدیو، اسناد آفیس) — کاملاً فارسی و آفلاین.
سازنده: محمدرضا جباری — چاپ و تبلیغات فدک — https://eitaa.com/fadakph

## گرفتن فایل نصبی (سه راه)

### راه ۱ — بدون نصب هیچ‌چیز (پیشنهادی): GitHub Actions
1. در github.com یک مخزن (Repository) خصوصی بسازید و کل این پوشه را آپلود کنید.
2. تب **Actions** ← **Build Windows installer** ← **Run workflow**.
3. بعد از چند دقیقه، فایل `FadakPrintTools-Setup.exe` را از بخش Artifacts دانلود کنید.
   (ffmpeg و فونت وزیرمتن هم خودکار داخلش قرار می‌گیرند.)

### راه ۲ — روی کامپیوتر خودتان
1. Python 3.12 را از python.org نصب کنید (تیک Add to PATH).
2. (اختیاری) Inno Setup 6 را از jrsoftware.org نصب کنید.
3. اگر صوت/ویدیو می‌خواهید: `ffmpeg.exe` را در پوشهٔ `bin` بگذارید.
   اگر فونت وزیرمتن می‌خواهید: فایل‌های `.ttf` را در پوشهٔ `fonts` بگذارید.
4. روی `build.bat` دوبار کلیک کنید.
   - فایل نصبی: `installer_output\FadakPrintTools-Setup.exe`
   - نسخهٔ پرتابل: `dist\FadakPrintTools\`

### راه ۳ — اجرای مستقیم برای تست
```
pip install -r requirements.txt
python main.py
```

## نکات
- مسیرهای فارسی کاملاً پشتیبانی می‌شوند (فایل‌ها از روی بایت خوانده می‌شوند و برای موتورهای بیرونی با نام موقت انگلیسی کپی می‌شوند).
- تبدیل Word/Excel/PowerPoint به PDF نیاز به نصب بودن LibreOffice روی کامپیوتر دارد.
- ویزارد فارسی نصب: فایل `Farsi.isl` را از صفحهٔ Unofficial Translations سایت Inno Setup بگیرید و کنار `installer.iss` بگذارید.
