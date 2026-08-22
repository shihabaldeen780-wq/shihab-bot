# نشر بوت شهاب على AlwaysData

## البنية المعتمدة

يعمل البوت عبر **AlwaysData Service** وليس عبر موقع ويب؛ لأن بوت Telegram يحتاج عملية خلفية مستمرة تستقبل التحديثات. توثيق AlwaysData يذكر أن Python متاح بإصدارات متعددة، كما أن Services مخصصة لتشغيل البرامج headless ومراقبتها وإعادة تشغيلها عند توقفها. راجع [توثيق Python الرسمي](https://help.alwaysdata.com/en/docs/web-hosting/languages/python/) و[شرح Services الرسمي](https://blog.alwaysdata.com/2021/04/08/services-kill-the-daemons/).

## رفع الملفات

ارفع الملفات التالية إلى مجلد خاص داخل حساب AlwaysData، ويفضل عبر Git أو SFTP:

```text
bot.py
run_alwaysdata.sh
requirements-alwaysdata.txt
.env
```

لا ترفع `data/shihab.db` القديمة إذا أردت قاعدة بيانات جديدة، أو ارفعها إذا أردت الاحتفاظ بالبيانات الحالية. يجب أن يكون ملف `.env` خاصاً بالحساب ولا يوضع في مستودع عام.

## إعداد البيئة

من SSH أو من الطرفية المتاحة في الحساب:

```bash
cd /path/to/shihab-bot
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-alwaysdata.txt
chmod +x run_alwaysdata.sh
```

يمكن استخدام Python 3.11 أو إصدار مستقر متاح في الحساب. لا تستخدم نسخ Python التجريبية إذا ظهرت مشكلة في مكتبات asyncio.

## إنشاء الخدمة

من لوحة AlwaysData افتح قسم **Services** ثم أنشئ خدمة جديدة بالقيم التالية:

```text
Name: shihab-bot
Command: /path/to/shihab-bot/.venv/bin/python -u /path/to/shihab-bot/bot.py
Working directory: /path/to/shihab-bot
```

إذا كانت اللوحة تقبل سكربتاً واحداً، استخدم:

```text
/path/to/shihab-bot/run_alwaysdata.sh
```

لا تضف منفذاً ولا تعرض الخدمة للعامة؛ Polling لا يحتاج عنواناً عاماً. يجب أن تكون نسخة واحدة فقط من البوت متصلة بالتوكن في الوقت نفسه، لذلك أوقف نسخة Windows ونسخة Termux قبل بدء خدمة AlwaysData.

## متغيرات البيئة

يمكن حفظ الإعدادات في `.env` داخل مجلد الخدمة أو إضافتها من إعدادات الخدمة:

```text
BOT_TOKEN=التوكن الحالي
OWNER_ID=8201835611
DB_PATH=data/shihab.db
LOG_LEVEL=INFO
MAX_BROADCAST_DELAY=0.05
```

## الاختبار

بعد تشغيل الخدمة، راقب سجلها حتى يظهر:

```text
بوت شهاب جاهز للعمل
Application started
```

ثم أرسل `/start` إلى `@Gh_317_bot`. إذا لم يرد، تحقق أولاً من عدم وجود نسخة أخرى تعمل بالتوكن نفسه، ثم راجع سجل الخدمة.

## النسخ الاحتياطي

ينشئ الأمر المخصص للمالك `/backup` نسخة محلية من قاعدة SQLite داخل مجلد `data/backups`. كما أن AlwaysData يعلن عن توفر النسخ الاحتياطية ضمن خدمات الاستضافة؛ يجب تفعيلها أو مراجعة إعداداتها من لوحة الحساب.

## ملاحظة الحساب

إتمام النشر يحتاج حساب AlwaysData مسجلاً ومتاحاً عبر لوحة الإدارة. إذا ظهرت شاشة تسجيل دخول أو طلبت كلمة مرور/رمز تحقق، يجب أن تدخلها أنت في المتصفح؛ لا ترسل بيانات الدخول داخل المحادثة.
