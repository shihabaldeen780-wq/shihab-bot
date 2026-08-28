
import os
SERVICE_ID = os.getenv("SERVICE_ID", "29418")
COMMIT_HASH = os.getenv("COMMIT_HASH", "21606b7")
"""
شاخوف711 - الملف الكامل النهائي
سورس شاخوف العسكري + كل خدمات وعد كاملة 100%
الإصدار النهائي ULTIMATE FINAL
يجمع:
🪖 شاخوف: ردود عسكرية + رتب + 6 العاب قتالية + حماية
💖 وعد: كل خدمات وعد الـ 15 + كل الألعاب + كل الإعدادات + كل الأوامر بالرد
🌙 سديم: قرآن + أذكار + أدعية
يعمل على Alwaysdata
@s_kf711_bot
"""
import os, random, sqlite3, re, logging, threading, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ChatMemberHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN") or "8980736848:AAGp8DD3CC9bCoqVpNdhAYFutni3uwxwxtk"
DB = "shakhoof711.db"
PORT = int(os.getenv("PORT", "8101"))
IP = os.getenv("IP", "::")

# ================= رتب شاخوف العسكرية =================
RANKS = [
    (0, "مجند مستجد 🪖"), (25, "جندي مقاتل 🔰"), (60, "جندي أول ⚔️"),
    (110, "عريف ميدان 🎖️"), (180, "رقيب قناص 🎯"), (270, "رقيب أول 711 🦅"),
    (380, "مساعد ثكنة 🛡️"), (520, "ملازم هيبة 🥈"), (680, "ملازم أول صاعقة ⚡"),
    (880, "نقيب عمليات 🥉"), (1120, "رائد أركان 🏅"), (1400, "مقدم ثكنة 🎖️🎖️"),
    (1750, "عقيد ركن 🦅🦅"), (2200, "عميد 711 🇾🇪"), (2800, "لواء درع اليمن 🛡️"),
    (3600, "فريق أول 👑"), (5000, "مشير شاخوف711 👑🔥"),
]
def get_rank(p):
    r=RANKS[0][1]
    for pts,rn in RANKS:
        if p>=pts: r=rn
        else: break
    return r
def next_rank(p):
    for pts,rn in RANKS:
        if p<pts: return rn, pts-p
    return "القمة!", 0

# ================= قاعدة البيانات =================
def init_db():
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS points (user_id INTEGER, chat_id INTEGER, points INTEGER, PRIMARY KEY(user_id, chat_id))")
    c.execute("CREATE TABLE IF NOT EXISTS settings (chat_id INTEGER PRIMARY KEY, lock_link INTEGER DEFAULT 1, lock_photo INTEGER DEFAULT 0, lock_sticker INTEGER DEFAULT 0, lock_forward INTEGER DEFAULT 1, lock_spam INTEGER DEFAULT 1, lock_voice INTEGER DEFAULT 0, welcome INTEGER DEFAULT 1, rules TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS replies (chat_id INTEGER, trigger TEXT, reply TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS muted (chat_id INTEGER, user_id INTEGER, PRIMARY KEY(chat_id,user_id))")
    c.execute("CREATE TABLE IF NOT EXISTS banned (chat_id INTEGER, user_id INTEGER, PRIMARY KEY(chat_id,user_id))")
    conn.commit(); conn.close()

def get_settings(cid):
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("SELECT lock_link, lock_photo, lock_sticker, lock_forward, lock_spam, lock_voice, welcome, rules FROM settings WHERE chat_id=?",(cid,))
    row=c.fetchone()
    if not row:
        c.execute("INSERT INTO settings (chat_id) VALUES (?)",(cid,)); conn.commit(); row=(1,0,0,1,1,0,1,'')
    conn.close()
    return {"lock_link":row[0],"lock_photo":row[1],"lock_sticker":row[2],"lock_forward":row[3],"lock_spam":row[4],"lock_voice":row[5],"welcome":row[6],"rules":row[7]}

def toggle(cid,k):
    s=get_settings(cid); nv=0 if s[k] else 1
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute(f"UPDATE settings SET {k}=? WHERE chat_id=?",(nv,cid)); conn.commit(); conn.close()
    return nv

def add_points(uid,cid,pts):
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("INSERT INTO points VALUES (?,?,?) ON CONFLICT(user_id,chat_id) DO UPDATE SET points=points+?",(uid,cid,pts,pts))
    conn.commit(); conn.close()
def get_points(uid,cid):
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("SELECT points FROM points WHERE user_id=? AND chat_id=?",(uid,cid)); r=c.fetchone(); conn.close()
    return r[0] if r else 0
def top_points(cid,lim=10):
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("SELECT user_id,points FROM points WHERE chat_id=? ORDER BY points DESC LIMIT ?",(cid,lim)); rows=c.fetchall(); conn.close(); return rows

# ================= بيانات شاخوف العسكرية =================
MILITARY_REPLIES = {
    "السلام عليكم": "وعليكم السلام يا بطل 🫡\nشاخوف711 يرحب بك في ثكنة 711 🇾🇪",
    "سلام": "سلام يا نشمي، الثكنة مؤمنة 🛡️",
    "هلا": "هلا بالذيب 🐺 جاهز للمهمة يا مقاتل؟ ⚔️",
    "هلا والله": "هلا وغلا يا فندم، شاخوف711 تحت أمرك 🫡",
    "كيف حالك": "في أتم الجاهزية القتالية يا قائد! 💪",
    "شاخوف": "نعم يا قائد؟ شاخوف711 يصغي 🫡",
    "شاخوف711": "شاخوف711 حاضر يا فندم! 🇾🇪🔥",
    "تحية": "🫡 تحية عسكرية لمعاليك يا فندم!",
    "تمام": "تمام يا فندم 🫡 تم التنفيذ!",
    "تم": "تم يا قائد ✅ العملية ناجحة",
    "طابور": "📢 طابور الصباح - الكل استعداد! 🫡",
    "استعداد": "استعداد .. اثبت! 🫡 كتيبة 711 جاهزة",
    "اليمن": "اليمن فوق الجميع 🇾🇪🔥",
    "الله اكبر": "الله أكبر 🇾🇪✊",
    "تجنيد": "🪖 تم تجنيدك في كتيبة 711 - رتبتك مجند مستجد",
}

# ================= كل بيانات وعد الكاملة =================
WAAD_SARAHA = [
"لو خيروك ترجع للماضي ولا تروح للمستقبل؟",
"أكثر شخص مشتاق له الآن؟",
"لو تقدر تغير شيء واحد في حياتك إيش بيكون؟",
"متى آخر مرة بكيت من قلب؟",
"هل تؤمن بالحب من أول نظرة؟",
"أكثر كذبة كذبتها وصدقوها؟",
"من الشخص اللي ما تقدر تعيش بدونه؟",
"لو معك مليون ايش تسوي؟",
"هل انت راضي عن نفسك؟",
"أصعب قرار اتخذته؟",
"من قدوتك في الحياة؟",
"إيش أكثر شيء تخاف منه؟",
"لو تقدر ترجع شخص ميت للحياة مين؟",
"هل سبق وحبيت من طرف واحد؟",
"أكثر موقف محرج صار لك؟",
"إيش سرك اللي ما حد يعرفه؟",
"تحب أحد الآن؟ صارح شاخوف",
"لو تقدر تسافر وين؟",
"أكثر شي يزعجك في الناس؟",
"هل انت كيوت؟ جاوب بصراحة شاخوف",
"لو خيروك بين الحب والكرامة؟",
"متى آخر مرة قلت أحبك؟",
"هل تندم على شيء؟",
"من أكثر شخص تكرهه؟",
"لو معك قوة خارقة إيش بتسوي؟"
]

WAAD_KHAYROK = [
("الفلوس ولا الحب؟","💰 الفلوس","❤️ الحب"),
("الذكاء ولا الجمال؟","🧠 الذكاء","💃 الجمال"),
("تكون مشهور ولا غني؟","🌟 مشهور","💎 غني"),
("تعيش في الماضي ولا المستقبل؟","⏪ ماضي","⏩ مستقبل"),
("تطير ولا تختفي؟","🕊️ تطير","👻 تختفي"),
("تعرف متى تموت ولا كيف تموت؟","⏰ متى","🤔 كيف"),
("بلا انترنت ولا بلا أصدقاء؟","📵 بلا نت","👥 بلا أصدقاء"),
("قوة خارقة ولا فلوس لا نهائية؟","⚡ قوة","💸 فلوس"),
("تعيش بلا حب ولا بلا فلوس؟","💔 بلا حب","💸 بلا فلوس"),
("تكون قوي ولا ذكي؟","💪 قوي","🧠 ذكي"),
("حب حياتك ولا صديق عمرك؟","❤️ حب","🤝 صديق"),
]

WAAD_GHAZAL = [
"أنتِ مثل القمر كل ما أشوفك أنسى كل همومي 🌙❤️",
"عيونك مثل النجوم تضوي ليلي 🌟",
"يا زينك كلامك عسل 🍯",
"حبك في قلبي مثل النار ما ينطفي 🔥❤️",
"أنتي أجمل وردة في بستان حياتي 🌹",
"لو الحب كلام كتبت لك كتاب 📖❤️",
"يا شاخوف قلبي عليك 😍 - بدل وعد",
"جمالك قتلني 💘 شاخوف يقول",
"أنت الحب كله 💖 يا شاخوف",
"عيونك دواء لقلبي 🌹 شاخوف",
"يا حلو يا شاخوف 😍",
"حبك في قلبي نار 🔥",
]

WAAD_NOKAT = [
"محشش قال لصاحبه تصدق أنا ذكي؟ قاله كيف؟ قال أنا أفكر قبل ما أنام 😂",
"واحد بخيل مات كتبوا على قبره هذا قبر البخيل ادفع للدخول 😂",
"طالب قال للمدرس أنت تشرح واحنا نفهم؟ قال إيه قال طيب ليش ما تشرح لنفسك؟ 😂",
"واحد راح للدكتور قاله دكتور أنا أنسى كثير قاله متى بدت معك الحالة؟ قاله أي حالة؟ 😂",
"محشش سألوه ايش اصعب شي؟ قال أني أكون صادق وأنا كذاب 😂",
"واحد قال لزوجته بدي أشوف أجمل وحدة قالت له روح شوف المراية 😂",
"محشش دخل سوبرماركت قال عندكم ثلج؟ قالوا إيه قال بارد ولا حار؟ 😂 شاخوف",
]

WAAD_HOKM = [
"لا تثق بمن لا تعرفه حتى لو كان قريب 🧠 شاخوف",
"الصمت أحياناً أبلغ من الكلام 🤫",
"من جد وجد ومن زرع حصد 🌱",
"الوقت كالسيف إن لم تقطعه قطعك ⏰",
"لا تؤجل عمل اليوم إلى الغد 📅",
"الحياة قصيرة عشها بحب ❤️ شاخوف",
"لا تحزن إن الله معنا 🌙",
"اللي ما يعرفك يجهلك 🤷‍♂️",
]

SADEEM_QURAN = [
"﴿ وَمَن يَتَّقِ اللَّهَ يَجْعَل لَّهُ مَخْرَجًا ﴾ - الطلاق",
"﴿ إِنَّ مَعَ الْعُسْرِ يُسْرًا ﴾ - الشرح",
"﴿ أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ ﴾ - الرعد",
"﴿ وَاصْبِرْ فَإِنَّ اللَّهَ لَا يُضِيعُ أَجْرَ الْمُحْسِنِينَ ﴾",
"﴿ لَا تَحْزَنْ إِنَّ اللَّهَ مَعَنَا ﴾ - التوبة",
"﴿ وَقُل رَّبِّ زِدْنِي عِلْمًا ﴾ - طه",
"﴿ فَاذْكُرُونِي أَذْكُرْكُمْ ﴾ - البقرة",
"﴿ وَاللَّهُ يُحِبُّ الصَّابِرِينَ ﴾",
"﴿ وَمَا تَوْفِيقِي إِلَّا بِاللَّهِ ﴾",
]
SADEEM_DUA = [
"اللهم إني أسألك العفو والعافية في الدنيا والآخرة 🤲",
"اللهم اغفر لي وارحمني واهدني وعافني وارزقني 🌙",
"ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
"اللهم يا مقلب القلوب ثبت قلبي على دينك ❤️",
"اللهم إني أسألك الجنة وما قرب إليها من قول أو عمل 🌹",
"اللهم ارزقني حبك وحب من يحبك 💖 شاخوف",
"استغفر الله العظيم وأتوب إليه 🌙",
]

# ================= الكيبوردات =================
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ حماية شاخوف711",callback_data="menu_protection"),InlineKeyboardButton("⚔️ ميدان شاخوف",callback_data="menu_games")],
        [InlineKeyboardButton("💖 ألعاب وعد - شاخوف",callback_data="menu_waad"),InlineKeyboardButton("🌙 خدمات وعد+سديم",callback_data="menu_sadeem")],
        [InlineKeyboardButton("👑 إدارة وعد - شاخوف",callback_data="menu_admin"),InlineKeyboardButton("🎖️ رتبتي شاخوف",callback_data="menu_rank")],
        [InlineKeyboardButton("🏆 لوحة الشرف",callback_data="menu_top"),InlineKeyboardButton("📢 كل أوامر شاخوف+وعد",callback_data="menu_cmds")],
    ])

def protection_kb(cid):
    s=get_settings(cid)
    def ic(v): return "🟢 مفعّل" if v else "🔴 معطّل"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{ic(s['lock_link'])} روابط",callback_data="toggle_lock_link"),InlineKeyboardButton(f"{ic(s['lock_forward'])} توجيه",callback_data="toggle_lock_forward")],
        [InlineKeyboardButton(f"{ic(s['lock_spam'])} سبام",callback_data="toggle_lock_spam"),InlineKeyboardButton(f"{ic(s['lock_photo'])} صور",callback_data="toggle_lock_photo")],
        [InlineKeyboardButton(f"{ic(s['lock_sticker'])} ملصقات",callback_data="toggle_lock_sticker"),InlineKeyboardButton(f"{ic(s['lock_voice'])} صوتيات",callback_data="toggle_lock_voice")],
        [InlineKeyboardButton("🔙 رجوع شاخوف",callback_data="menu_main")]
    ])

def games_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 قناص شاخوف711",callback_data="game_sniper"),InlineKeyboardButton("💣 تفكيك C4",callback_data="game_bomb")],
        [InlineKeyboardButton("💥 حقل ألغام شاخوف",callback_data="game_mine"),InlineKeyboardButton("🕵️ كشف جاسوس 711",callback_data="game_spy")],
        [InlineKeyboardButton("🏜️ اقتحام جبل 711",callback_data="game_mountain"),InlineKeyboardButton("🧠 اختبار أركان",callback_data="game_quiz")],
        [InlineKeyboardButton("🔙 رجوع شاخوف",callback_data="menu_main")]
    ])

def waad_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 صراحة شاخوف",callback_data="waad_saraha"),InlineKeyboardButton("🤔 لو خيروك شاخوف",callback_data="waad_khayrok")],
        [InlineKeyboardButton("❤️ حب شاخوف",callback_data="waad_love"),InlineKeyboardButton("😍 كيوت شاخوف",callback_data="waad_cute")],
        [InlineKeyboardButton("💃 جمال شاخوف",callback_data="waad_jamal"),InlineKeyboardButton("💪 رجولة شاخوف",callback_data="waad_rojola")],
        [InlineKeyboardButton("🌹 غزل شاخوف",callback_data="waad_ghazal"),InlineKeyboardButton("😂 نكت شاخوف",callback_data="waad_nokta")],
        [InlineKeyboardButton("🧠 حكمة شاخوف",callback_data="waad_hokm"),InlineKeyboardButton("🔮 كشف كذب شاخوف",callback_data="waad_kashf")],
        [InlineKeyboardButton("🎲 توأم روحي شاخوف",callback_data="waad_tawam"),InlineKeyboardButton("🔍 بحث شاخوف",callback_data="waad_search")],
        [InlineKeyboardButton("✨ زخرفة شاخوف",callback_data="waad_zakhrafa"),InlineKeyboardButton("🆔 ايدي شاخوف",callback_data="waad_id")],
        [InlineKeyboardButton("🔙 رجوع شاخوف",callback_data="menu_main")]
    ])

def sadeem_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 قرآن شاخوف",callback_data="sadeem_quran"),InlineKeyboardButton("🌅 أذكار صباح",callback_data="sadeem_sabah")],
        [InlineKeyboardButton("🌙 أذكار مساء",callback_data="sadeem_masa"),InlineKeyboardButton("🤲 دعاء شاخوف",callback_data="sadeem_dua")],
        [InlineKeyboardButton("📿 تسبيح شاخوف",callback_data="sadeem_tasbeh"),InlineKeyboardButton("🔍 بحث",callback_data="sadeem_search")],
        [InlineKeyboardButton("🔙 رجوع",callback_data="menu_main")]
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 رفع ادمن شاخوف",callback_data="admin_info"),InlineKeyboardButton("🔻 تنزيل ادمن",callback_data="admin_info")],
        [InlineKeyboardButton("🔇 كتم شاخوف",callback_data="admin_info"),InlineKeyboardButton("🔊 فك كتم",callback_data="admin_info")],
        [InlineKeyboardButton("🚫 حظر شاخوف",callback_data="admin_info"),InlineKeyboardButton("👢 طرد شاخوف",callback_data="admin_info")],
        [InlineKeyboardButton("📌 تثبيت شاخوف",callback_data="admin_info"),InlineKeyboardButton("🗑️ مسح شاخوف",callback_data="admin_info")],
        [InlineKeyboardButton("➕ اضف رد شاخوف",callback_data="admin_info"),InlineKeyboardButton("📋 الردود شاخوف",callback_data="show_replies")],
        [InlineKeyboardButton("📜 قوانين شاخوف",callback_data="show_rules"),InlineKeyboardButton("👋 ترحيب شاخوف",callback_data="toggle_welcome")],
        [InlineKeyboardButton("🔙 رجوع شاخوف",callback_data="menu_main")]
    ])

WELCOME_FINAL = """
🦅 **شاخوف711 - البوت الكامل النهائي** 🇾🇪
🪖 **شاخوف العسكري + 💖 وعد الكامل**

╔═══════════════════════════╗
║  🪖 شاخوف711 FINAL 🪖     ║
║  💖 كل خدمات وعد داخل شاخوف ║
║  🌙 + سديم                ║
╚═══════════════════════════╝

يا {name}... رتبتك: **{rank}** | نقاطك: {pts} ⭐

🪖 **شاخوف العسكري:**
• ردود عسكرية: تحية - طابور - اليمن
• 6 ألعاب قتالية: قناص - C4 - ألغام - جاسوس - اقتحام - اختبار
• نظام رتب من مجند إلى مشير
• حماية: روابط - صور - ملصقات - توجيه - سبام

💖 **كل خدمات وعد داخل شاخوف:**
• ألعاب وعد: صراحة - لو خيروك - حب - كيوت - جمال - رجولة
• ترفيه وعد: غزل - نكت - حكم - كشف كذب - توأم روحي
• خدمات وعد: ايدي - زخرفة - بحث - تسبيح
• إدارة وعد: رفع ادمن - كتم - طرد - حظر - تثبيت - اضف رد

🌙 **سديم:**
• قرآن - أذكار - أدعية

📢 **أوامر شاخوف+وعد:** /start /رتبتي /ايدي /كيوت /حب /قران /بحث /طابور

**طريقة الإدارة مثل وعد:** رد على رسالة الشخص واكتب:
`رفع ادمن` `كتم` `طرد` `حظر` `تثبيت` `كيوت`

الثكنة الكاملة تحت أمرك يا فندم 🫡💖🌙
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pts=get_points(update.effective_user.id, update.effective_chat.id)
    await update.message.reply_text(WELCOME_FINAL.format(name=update.effective_user.first_name, rank=get_rank(pts), pts=pts), reply_markup=main_kb(), parse_mode="Markdown")

async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pts=get_points(update.effective_user.id, update.effective_chat.id); r=get_rank(pts); nxt,need=next_rank(pts)
    await update.message.reply_text(f"🎖 **شاخوف711 FINAL**\n👤 {update.effective_user.first_name}\n{r}\n⭐ {pts}\n🎯 القادمة: {nxt} ({need})\n\n💖 كل خدمات وعد داخل شاخوف", parse_mode="Markdown")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; c=update.effective_chat; pts=get_points(u.id,c.id)
    txt=f"🆔 **ايدي شاخوف - مثل وعد**\n\n🆔 ID: `{u.id}`\n👤 الاسم: {u.first_name}\n🏠 الشات: {c.title or 'خاص'}\n🎖 رتبة شاخوف: {get_rank(pts)}\n⭐ نقاط شاخوف: {pts}\n💬 يوزر: @{u.username or 'لا يوجد'}\n\n💖 شاخوف + وعد"
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_kb())

async def cute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target=update.effective_user.first_name
    if update.message.reply_to_message: target=update.message.reply_to_message.from_user.first_name
    elif context.args: target=" ".join(context.args)
    key=f"{target}{update.effective_chat.id}cute".encode(); h=int(hashlib.md5(key).hexdigest(),16)%101
    msg="كيوت بزيادة 😍💖 شاخوف" if h>80 else "كيوت 😊 شاخوف" if h>60 else "نص نص 🙂"
    add_points(update.effective_user.id, update.effective_chat.id, 2)
    await update.message.reply_text(f"😍 **كيوت شاخوف - مثل وعد**\n\n{target} : {h}% - {msg}\n+2 💖", reply_markup=waad_kb())

async def jamal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target=update.effective_user.first_name
    if update.message.reply_to_message: target=update.message.reply_to_message.from_user.first_name
    elif context.args: target=" ".join(context.args)
    h=random.randint(30,100)
    await update.message.reply_text(f"💃 **جمال شاخوف - مثل وعد**\n\n{target} : {h}%\n{'ملكة جمال شاخوف 👑💖' if h>85 else 'جميلة 🌹 شاخوف' if h>70 else 'حلوة 😊'}", reply_markup=waad_kb())

async def rojola_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target=update.effective_user.first_name
    if update.message.reply_to_message: target=update.message.reply_to_message.from_user.first_name
    elif context.args: target=" ".join(context.args)
    h=random.randint(40,100)
    await update.message.reply_text(f"💪 **رجولة شاخوف - مثل وعد**\n\n{target} : {h}%\n{'أسد شاخوف 🦁🔥' if h>80 else 'رجال شاخوف 💪'}", reply_markup=waad_kb())

async def quran_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📖 **قرآن شاخوف - مثل سديم ووعد**\n\n{random.choice(SADEEM_QURAN)}\n\nصدق الله العظيم 🌙 شاخوف", reply_markup=sadeem_kb())

async def saraha_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 **صراحة شاخوف - مثل وعد**\n\n{random.choice(WAAD_SARAHA)}\n\nشاخوف ينتظر صراحتك 💖", reply_markup=waad_kb())

async def love_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<2:
        await update.message.reply_text("❤️ **حب شاخوف - مثل وعد**\nاستخدم: /حب اسم1 اسم2\nمثال: /حب شاخوف وعد\n\nكل خدمات وعد داخل شاخوف 💖"); return
    n1,n2=context.args[0],context.args[1]; key=f"{n1}{n2}".encode(); h=int(hashlib.md5(key).hexdigest(),16)%101
    msg="حب أسطوري 🔥💖 شاخوف مبارك" if h>80 else "حب قوي ❤️ شاخوف" if h>60 else "حب متوسط 💛" if h>40 else "يلزمكم وقت 😅 شاخوف"
    await update.message.reply_text(f"❤️ **نسبة الحب شاخوف - مثل وعد**\n\n{n1} + {n2} = {h}% \n{msg}", reply_markup=waad_kb())

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🔍 **بحث شاخوف - مثل وعد**\nاستخدم: /بحث كلمة\nمثال: /بحث شاخوف\n\nيبحث قوقل ويوتيوب"); return
    query=" ".join(context.args)
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 قوقل شاخوف", url=f"https://www.google.com/search?q={query}"), InlineKeyboardButton("▶️ يوتيوب شاخوف", url=f"https://www.youtube.com/results?search_query={query}")],
        [InlineKeyboardButton("📖 قرآن شاخوف", url=f"https://quran.com/search?q={query}")]
    ])
    await update.message.reply_text(f"🔍 **بحث شاخوف (مثل وعد) عن: {query}**", reply_markup=kb)

async def add_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg=" ".join(context.args); trig,rep=msg.split("|",1)
        conn=sqlite3.connect(DB); c=conn.cursor()
        c.execute("INSERT INTO replies VALUES (?,?,?)",(update.effective_chat.id,trig.strip(),rep.strip())); conn.commit(); conn.close()
        await update.message.reply_text(f"✅ شاخوف حفظ رد وعد: {trig.strip()} -> {rep.strip()} 💖")
    except:
        await update.message.reply_text("❌ استخدم: /اضف_رد الكلمة | الرد\nمثال: /اضف_رد هلا | هلا والله يا شاخوف 💖🪖")

async def del_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدم: /حذف_رد الكلمة - مثل وعد"); return
    trig=" ".join(context.args)
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("DELETE FROM replies WHERE chat_id=? AND trigger=?",(update.effective_chat.id,trig)); conn.commit(); conn.close()
    await update.message.reply_text(f"🗑️ شاخوف حذف رد وعد: {trig}")

async def list_replies_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("SELECT trigger,reply FROM replies WHERE chat_id=?",(update.effective_chat.id,)); rows=c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("لا يوجد ردود - مثل وعد شاخوف"); return
    txt="📋 **ردود شاخوف (مثل وعد):**\n\n"
    for t,r in rows[:25]: txt+=f"• {t} -> {r}\n"
    await update.message.reply_text(txt)

async def promote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("👑 شاخوف: رد على رسالة الشخص واكتب /رفع_ادمن - مثل وعد"); return
    try:
        await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, can_delete_messages=True, can_pin_messages=True, can_invite_users=True)
        await update.message.reply_text(f"👑 شاخوف رفع {update.message.reply_to_message.from_user.first_name} ادمن (مثل وعد) 🫡")
    except Exception as e:
        await update.message.reply_text(f"❌ شاخوف ما قدر: {e}")

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("🔇 شاخوف: رد على الشخص واكتب /كتم - مثل وعد"); return
    uid=update.message.reply_to_message.from_user.id; cid=update.effective_chat.id
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("INSERT OR IGNORE INTO muted VALUES (?,?)",(cid,uid)); conn.commit(); conn.close()
    await update.message.reply_text(f"🔇 شاخوف كتم {update.message.reply_to_message.from_user.first_name} (مثل وعد)")

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("🔊 رد واكتب /الغاء_كتم - مثل وعد"); return
    uid=update.message.reply_to_message.from_user.id; cid=update.effective_chat.id
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?",(cid,uid)); conn.commit(); conn.close()
    await update.message.reply_text(f"🔊 شاخوف فك كتم {update.message.reply_to_message.from_user.first_name}")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("🚫 رد واكتب /حظر - مثل وعد شاخوف"); return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text(f"🚫 شاخوف حظر {update.message.reply_to_message.from_user.first_name} (مثل وعد)")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def kick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("👢 رد واكتب /طرد - مثل وعد شاخوف"); return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text(f"👢 شاخوف طرد {update.message.reply_to_message.from_user.first_name} (مثل وعد)")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("📌 رد على الرسالة واكتب /تثبيت - مثل وعد"); return
    try:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 شاخوف ثبت الرسالة (مثل وعد)")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def zakhrafa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("✨ **زخرفة شاخوف - مثل وعد**\n/زخرفة اسمك\nمثال: /زخرفة شاخوف"); return
    name=" ".join(context.args)
    fonts=[f"⸙{name}⸙",f"✨{name}✨",f"💖{name}💖",f"『{name}』",f"꧁{name}꧂",f"༺{name}༻",f"◥{name}◤",f"░{name}░",f"★彡{name}彡★",f"☆{name}☆"]
    txt="✨ **زخرفة شاخوف (مثل وعد):**\n\n"+"\n".join(fonts)
    await update.message.reply_text(txt, reply_markup=waad_kb())

async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s=get_settings(update.effective_chat.id)
    if s["rules"]:
        await update.message.reply_text(f"📜 **قوانين شاخوف (مثل وعد):**\n\n{s['rules']}")
    else:
        await update.message.reply_text("📜 لا يوجد قوانين - شاخوف\nضع قوانين بـ /ضع_قوانين النص")

async def set_rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدم: /ضع_قوانين النص"); return
    rules=" ".join(context.args)
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("UPDATE settings SET rules=? WHERE chat_id=?",(rules, update.effective_chat.id)); conn.commit(); conn.close()
    await update.message.reply_text(f"📜 تم حفظ قوانين شاخوف (مثل وعد):\n{rules}")

# ================= إدارة وعد بالرد =================
async def is_admin(cid, uid, bot):
    try:
        m=await bot.get_chat_member(cid,uid)
        return m.status in ["administrator","creator"]
    except: return False

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return False
    text=update.message.text.strip(); low=text.lower()
    if not update.message.reply_to_message: return False
    target = update.message.reply_to_message.from_user
    cid=update.effective_chat.id; uid=update.effective_user.id
    if not await is_admin(cid, uid, context.bot): return False

    if low in ["رفع ادمن","رفع مشرف","رفع اداره","رفع ادمين"]:
        try:
            await context.bot.promote_chat_member(cid, target.id, can_delete_messages=True, can_pin_messages=True, can_invite_users=True, can_promote_members=False)
            await update.message.reply_text(f"👑 شاخوف رفع {target.first_name} ادمن (مثل وعد تماما) 🫡")
            return True
        except Exception as e:
            await update.message.reply_text(f"❌ شاخوف ما قدر: {e}"); return True
    if low in ["تنزيل ادمن","تنزيل مشرف","تنزيل ادمين"]:
        try:
            await context.bot.promote_chat_member(cid, target.id, can_delete_messages=False, can_pin_messages=False, can_invite_users=False, can_promote_members=False)
            await update.message.reply_text(f"🔻 شاخوف نزل {target.first_name} (مثل وعد)")
            return True
        except: return True
    if low in ["كتم","اسكت","كتمه","اكتم"]:
        conn=sqlite3.connect(DB); c=conn.cursor()
        c.execute("INSERT OR IGNORE INTO muted VALUES (?,?)",(cid,target.id)); conn.commit(); conn.close()
        await update.message.reply_text(f"🔇 شاخوف كتم {target.first_name} (مثل وعد)"); return True
    if low in ["الغاء كتم","الغاء الكتم","فك كتم","احجي","الغاء كتمه"]:
        conn=sqlite3.connect(DB); c=conn.cursor()
        c.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?",(cid,target.id)); conn.commit(); conn.close()
        await update.message.reply_text(f"🔊 شاخوف فك كتم {target.first_name} (مثل وعد)"); return True
    if low in ["حظر","باند","احظر"]:
        try:
            await context.bot.ban_chat_member(cid, target.id)
            await update.message.reply_text(f"🚫 شاخوف حظر {target.first_name} (مثل وعد)")
        except: pass
        return True
    if low in ["الغاء حظر","فك حظر","الغاء باند","فك باند"]:
        try:
            await context.bot.unban_chat_member(cid, target.id)
            await update.message.reply_text(f"✅ شاخوف فك حظر {target.first_name} (مثل وعد)")
        except: pass
        return True
    if low in ["طرد","اطرد","طلع","طرده"]:
        try:
            await context.bot.ban_chat_member(cid, target.id)
            await context.bot.unban_chat_member(cid, target.id)
            await update.message.reply_text(f"👢 شاخوف طرد {target.first_name} (مثل وعد)")
        except: pass
        return True
    if low in ["تثبيت","ثبت","ثبتي"]:
        try:
            await context.bot.pin_chat_message(cid, update.message.reply_to_message.message_id)
            await update.message.reply_text("📌 شاخوف ثبت الرسالة (مثل وعد)")
        except: pass
        return True
    if low in ["كيوت","نسبة كيوت","كياته","جمال","نسبة جمال","رجولة","نسبة رجولة"]:
        key=f"{target.first_name}{cid}cute".encode(); h=int(hashlib.md5(key).hexdigest(),16)%101
        await update.message.reply_text(f"😍 شاخوف - {target.first_name} {low} {h}% (مثل وعد)"); return True
    return False

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); data=q.data; cid=update.effective_chat.id; uid=update.effective_user.id
    if data=="menu_main":
        pts=get_points(uid,cid)
        await q.edit_message_text(WELCOME_FINAL.format(name=q.from_user.first_name, rank=get_rank(pts), pts=pts), reply_markup=main_kb(), parse_mode="Markdown")
    elif data=="menu_protection":
        await q.edit_message_text("🛡️ **حماية شاخوف711 - مثل وعد + حماية عسكرية**", reply_markup=protection_kb(cid), parse_mode="Markdown")
    elif data.startswith("toggle_"):
        k=data.replace("toggle_",""); nv=toggle(cid,k)
        await q.edit_message_text(f"{'✅ شاخوف فعل' if nv else '❌ شاخوف عطل'} - {k} (مثل وعد)", reply_markup=protection_kb(cid))
    elif data=="menu_games":
        await q.edit_message_text("⚔️ **ميدان شاخوف711 - 6 ألعاب عسكرية شاخوف**", reply_markup=games_kb(), parse_mode="Markdown")
    elif data=="menu_waad":
        await q.edit_message_text("💖 **كل ألعاب وعد داخل شاخوف**\nصراحة - خيروك - حب - كيوت - جمال - رجولة - غزل - نكت - حكمة", reply_markup=waad_kb(), parse_mode="Markdown")
    elif data=="menu_sadeem":
        await q.edit_message_text("🌙 **خدمات سديم ووعد داخل شاخوف**\nقرآن - أذكار - دعاء - تسبيح - بحث", reply_markup=sadeem_kb(), parse_mode="Markdown")
    elif data=="menu_admin":
        await q.edit_message_text("👑 **إدارة شاخوف مثل وعد تماما**\n\nرد على رسالة الشخص واكتب:\nرفع ادمن - تنزيل ادمن\nكتم - الغاء كتم\nحظر - الغاء حظر\nطرد - تثبيت\nاضف رد - حذف رد - الردود\nقوانين - ترحيب\n\nمثل بوت وعد بالضبط لكن باسم شاخوف", reply_markup=admin_kb(), parse_mode="Markdown")
    elif data=="menu_rank":
        pts=get_points(uid,cid); r=get_rank(pts); nxt,need=next_rank(pts)
        await q.edit_message_text(f"🎖️ **ملف شاخوف العسكري**\n\n{r}\nالنقاط: {pts}\nالقادمة: {nxt} ({need})\n\n💖 + كل خدمات وعد", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 شاخوف", callback_data="menu_main")]]))
    elif data=="menu_top":
        top=top_points(cid); txt="🏆 **لوحة شرف شاخوف711 + وعد**\n\n" if top else "لا يوجد أبطال شاخوف!"
        for i,(u,p) in enumerate(top,1): txt+=f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else f'{i}.'} {get_rank(p)} - {p} نقطة\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 شاخوف", callback_data="menu_main")]]))
    elif data=="menu_cmds":
        await q.edit_message_text("📢 **أوامر شاخوف الكامل - شاخوف + وعد**\n\n🪖 شاخوف: /start /رتبتي /طابور /تحية /حماية /ايدي /قوانين\n💖 وعد داخل شاخوف: /صراحه /حب /كيوت /جمال /رجولة /نكتة /غزل /حكمه /زخرفة /بحث\n🌙 سديم: /قران /اذكار /دعاء\n👑 إدارة وعد: /رفع_ادمن /كتم /حظر /طرد /تثبيت /اضف_رد /حذف_رد /الردود /ضع_قوانين\n\n**بالرد مثل وعد:**\nرفع ادمن - كتم - طرد - حظر - تثبيت - كيوت - جمال\n\nكلها باسم شاخوف 💖🪖", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 شاخوف", callback_data="menu_main")]]))
    elif data=="admin_info":
        await q.edit_message_text("👑 **أوامر إدارة شاخوف مثل وعد**\n\nرد على رسالة الشخص واكتب:\n`رفع ادمن` - يرفع ادمن شاخوف\n`كتم` - يكتم مثل وعد\n`طرد` - يطرد مثل وعد\n`حظر` - يحظر مثل وعد\n`تثبيت` - يثبت مثل وعد\n`كيوت` - نسبة كيوت\n`جمال` - نسبة جمال\n\nأو بالأوامر:\n/رفع_ادمن بالرد\n/كتم بالرد\n/طرد بالرد\n/حظر بالرد\n/تثبيت بالرد\n/اضف_رد كلمة | رد\n\nالبوت لازم ادمن شاخوف!", reply_markup=admin_kb())
    elif data=="show_replies":
        conn=sqlite3.connect(DB); c=conn.cursor()
        c.execute("SELECT trigger,reply FROM replies WHERE chat_id=?",(cid,)); rows=c.fetchall(); conn.close()
        txt="📋 **ردود شاخوف (مثل وعد):**\n\n"+"\n".join([f"{t}->{r}" for t,r in rows[:20]]) if rows else "لا يوجد ردود شاخوف"
        await q.edit_message_text(txt, reply_markup=admin_kb())
    elif data=="show_rules":
        s=get_settings(cid)
        txt=s["rules"] if s["rules"] else "لا يوجد قوانين شاخوف"
        await q.edit_message_text(f"📜 **قوانين شاخوف (مثل وعد):**\n\n{txt}", reply_markup=admin_kb())
    elif data=="toggle_welcome":
        nv=toggle(cid,"welcome")
        await q.edit_message_text(f"{'✅ شاخوف فعل الترحيب' if nv else '❌ شاخوف عطل الترحيب'} (مثل وعد)", reply_markup=admin_kb())
    elif data=="game_sniper":
        num=random.randint(1,150); context.chat_data["sniper"]=num
        await q.edit_message_text(f"🎯 **قناص شاخوف711**\nالهدف {num}م (1-150)\nخمن! شاخوف", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء شاخوف", callback_data="menu_games")]]))
    elif data=="game_bomb":
        wire=random.choice(["أحمر","أزرق","أخضر","أصفر"]); context.chat_data["bomb"]=wire
        await q.edit_message_text(f"💣 **تفكيك C4 - شاخوف711**\n4 أسلاك! شاخوف", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔴 أحمر",callback_data="bomb_أحمر"),InlineKeyboardButton("🔵 أزرق",callback_data="bomb_أزرق")],[InlineKeyboardButton("🟢 أخضر",callback_data="bomb_أخضر"),InlineKeyboardButton("🟡 أصفر",callback_data="bomb_أصفر")]]))
    elif data.startswith("bomb_"):
        ch=data.replace("bomb_",""); real=context.chat_data.get("bomb")
        if ch==real: add_points(uid,cid,15); await q.edit_message_text(f"✅ شاخوف فك القنبلة! +15 - {get_rank(get_points(uid,cid))}", reply_markup=games_kb())
        else: await q.edit_message_text(f"💥 شاخوف انفجرت! الصحيح {real}", reply_markup=games_kb())
        context.chat_data.pop("bomb",None)
    elif data=="game_mine":
        mines=set(random.sample([(r,c) for r in range(4) for c in range(4)],3)); context.chat_data["mines"]=mines; context.chat_data["opened"]=set()
        kb=[[InlineKeyboardButton("⬜",callback_data=f"mine_{r}_{c}") for c in range(4)] for r in range(4)]
        await q.edit_message_text("💥 **حقل ألغام شاخوف711**\n3 ألغام - افتح 8 آمن! شاخوف", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("mine_"):
        if "mines" not in context.chat_data: return
        _,r,c=data.split("_"); pos=(int(r),int(c)); mines=context.chat_data["mines"]; opened=context.chat_data["opened"]
        if pos in mines:
            await q.edit_message_text(f"💥 شاخوف لغم! الألغام: {mines}", reply_markup=games_kb()); context.chat_data.pop("mines",None); return
        opened.add(pos)
        if len(opened)>=8: add_points(uid,cid,20); await q.edit_message_text("🏆 شاخوف طهر الحقل! +20 🇾🇪", reply_markup=games_kb()); context.chat_data.pop("mines",None)
        else:
            kb=[]
            for rr in range(4):
                row=[]
                for cc in range(4):
                    if (rr,cc) in opened: row.append(InlineKeyboardButton("✅",callback_data="ignore"))
                    else: row.append(InlineKeyboardButton("⬜",callback_data=f"mine_{rr}_{cc}"))
                kb.append(row)
            await q.edit_message_reply_markup(InlineKeyboardMarkup(kb))
    elif data=="game_spy":
        missions=[("جاسوس طلب إحداثيات 711 شاخوف", "جاسوس"), ("رسالة: شاخوف711 خطر", "شفرة"), ("واحد يصور السلاح شاخوف", "خائن")]
        qq,aa=random.choice(missions); context.chat_data["spy"]=aa
        await q.edit_message_text(f"🕵️ **كشف عميل شاخوف711**\n\n{qq}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("تخطي شاخوف",callback_data="menu_games")]]))
    elif data=="game_mountain":
        steps=random.randint(3,6); context.chat_data["mount"]=steps; context.chat_data["cur"]=0
        await q.edit_message_text(f"🏜️ **اقتحام جبل شاخوف711**\n{steps} مراحل شاخوف", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"🧗 تسلق (0/{steps})",callback_data="climb")]]))
    elif data=="climb":
        if "mount" not in context.chat_data: return
        context.chat_data["cur"]+=1; cur=context.chat_data["cur"]; total=context.chat_data["mount"]
        if cur>=total: add_points(uid,cid,12); await q.edit_message_text(f"🏔️ شاخوف اقتحم الجبل +12 🇾🇪", reply_markup=games_kb()); context.chat_data.pop("mount",None)
        else: await q.edit_message_reply_markup(InlineKeyboardMarkup([[InlineKeyboardButton(f"🧗 تسلق ({cur}/{total})",callback_data="climb")]]))
    elif data=="game_quiz":
        qs=[("كم لون علم اليمن؟","3"),("اسم كتيبتنا؟","711"),("شعار القناص شاخوف؟","طلقة"),("اسم البوت؟","شاخوف711"),("بدل وعد؟","شاخوف")]
        qq,aa=random.choice(qs); context.chat_data["quiz"]=aa
        await q.edit_message_text(f"🧠 **اختبار أركان شاخوف711**\n\n{qq}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("تخطي شاخوف",callback_data="menu_games")]]))
    elif data=="waad_saraha":
        add_points(uid,cid,2)
        await q.edit_message_text(f"💬 **صراحة شاخوف - مثل وعد**\n\n{random.choice(WAAD_SARAHA)}\n\n+2 شاخوف 💖", reply_markup=waad_kb())
    elif data=="waad_khayrok":
        qq,a1,a2=random.choice(WAAD_KHAYROK)
        await q.edit_message_text(f"🤔 **لو خيروك شاخوف - مثل وعد**\n\n{qq}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(a1,callback_data="khayrok_1"),InlineKeyboardButton(a2,callback_data="khayrok_2")],[InlineKeyboardButton("🔙 شاخوف",callback_data="menu_waad")]]))
    elif data.startswith("khayrok_"):
        add_points(uid,cid,3)
        await q.edit_message_text(f"✅ شاخوف سجل اختيارك +3 (مثل وعد) 💖", reply_markup=waad_kb())
    elif data=="waad_love":
        await q.edit_message_text("❤️ **حب شاخوف - مثل وعد**\n\nارسل: /حب اسم1 اسم2\nمثال: /حب شاخوف وعد", reply_markup=waad_kb())
    elif data=="waad_cute":
        h=random.randint(30,100)
        await q.edit_message_text(f"😍 **كيوت شاخوف - مثل وعد**\n\n{h}% {'كيوت بزيادة 😍💖 شاخوف' if h>80 else 'كيوت شاخوف 😊'}", reply_markup=waad_kb())
    elif data=="waad_jamal":
        h=random.randint(30,100)
        await q.edit_message_text(f"💃 **جمال شاخوف - مثل وعد**\n\n{h}% {'ملكة جمال شاخوف 👑' if h>85 else 'جميلة شاخوف 🌹'}", reply_markup=waad_kb())
    elif data=="waad_rojola":
        h=random.randint(40,100)
        await q.edit_message_text(f"💪 **رجولة شاخوف - مثل وعد**\n\n{h}% {'أسد شاخوف 🦁' if h>80 else 'رجال شاخوف 💪'}", reply_markup=waad_kb())
    elif data=="waad_ghazal":
        await q.edit_message_text(f"🌹 **غزل شاخوف - مثل وعد**\n\n{random.choice(WAAD_GHAZAL)}", reply_markup=waad_kb())
    elif data=="waad_nokta":
        await q.edit_message_text(f"😂 **نكتة شاخوف - مثل وعد**\n\n{random.choice(WAAD_NOKAT)}", reply_markup=waad_kb())
    elif data=="waad_hokm":
        await q.edit_message_text(f"🧠 **حكمة شاخوف - مثل وعد**\n\n{random.choice(WAAD_HOKM)}", reply_markup=waad_kb())
    elif data=="waad_kashf":
        res=random.choice(["يكذب 😏 شاخوف كشفه مثل وعد","صادق ✅ شاخوف يصدقه","نص نص 🤔"])
        await q.edit_message_text(f"🔮 **كشف كذب شاخوف - مثل وعد**\n\n{res}", reply_markup=waad_kb())
    elif data=="waad_tawam":
        tawam=random.choice(["شخص يحبك بصمت ❤️ شاخوف يقول","صديق مخلص 🤝 شاخوف","توأمك قريب 🌟 شاخوف"])
        await q.edit_message_text(f"🎲 **توأم روحك شاخوف - مثل وعد**\n\n{tawam}", reply_markup=waad_kb())
    elif data=="waad_search":
        await q.edit_message_text("🔍 **بحث شاخوف - مثل وعد**\n\nاكتب: /بحث كلمة\nمثال: /بحث شاخوف", reply_markup=waad_kb())
    elif data=="waad_zakhrafa":
        await q.edit_message_text("✨ **زخرفة شاخوف - مثل وعد**\n\nاكتب: /زخرفة اسمك", reply_markup=waad_kb())
    elif data=="waad_id":
        pts=get_points(uid,cid)
        await q.edit_message_text(f"🆔 **ايدي شاخوف - مثل وعد**\nID: {uid}\nنقاط شاخوف: {pts}\nرتبة شاخوف: {get_rank(pts)}", reply_markup=waad_kb())
    elif data=="sadeem_quran":
        add_points(uid,cid,10)
        await q.edit_message_text(f"📖 **قرآن شاخوف - مثل وعد وسديم**\n\n{random.choice(SADEEM_QURAN)}\n\n+10 حسنات شاخوف 🌙", reply_markup=sadeem_kb())
    elif data=="sadeem_sabah":
        await q.edit_message_text("🌅 **أذكار الصباح شاخوف**\n\nأصبحنا وأصبح الملك لله\nسبحان الله وبحمده\nلا إله إلا الله\n\nشاخوف 🌙", reply_markup=sadeem_kb())
    elif data=="sadeem_masa":
        await q.edit_message_text("🌙 **أذكار المساء شاخوف**\n\nأمسينا وأمسى الملك لله\nآية الكرسي\nالمعوذات\n\nشاخوف 🌙", reply_markup=sadeem_kb())
    elif data=="sadeem_dua":
        await q.edit_message_text(f"🤲 **دعاء شاخوف - مثل وعد**\n\n{random.choice(SADEEM_DUA)}\n\nآمين شاخوف 🌙", reply_markup=sadeem_kb())
    elif data=="sadeem_tasbeh":
        cnt=context.chat_data.get("tasbeh",0)+1; context.chat_data["tasbeh"]=cnt
        await q.edit_message_text(f"📿 **تسبيح شاخوف - مثل وعد**\n\nسبحان الله وبحمده\n\nالعدد: {cnt}\n\nشاخوف", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"📿 سبح شاخوف ({cnt})",callback_data="sadeem_tasbeh")],[InlineKeyboardButton("🔄 تصفير",callback_data="tasbeh_reset"),InlineKeyboardButton("🔙 شاخوف",callback_data="menu_sadeem")]]))
        if cnt % 33 == 0: add_points(uid,cid,5)
    elif data=="tasbeh_reset":
        context.chat_data["tasbeh"]=0
        await q.edit_message_text("📿 شاخوف صفر التسبيح (مثل وعد)", reply_markup=sadeem_kb())
    elif data=="sadeem_search":
        await q.edit_message_text("🔍 **بحث شاخوف**\n\n/بحث كلمة - مثل وعد", reply_markup=sadeem_kb())

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text=update.message.text.strip(); cid=update.effective_chat.id; uid=update.effective_user.id; low=text.lower()
    if await handle_admin_text(update, context): return
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("SELECT 1 FROM muted WHERE chat_id=? AND user_id=?",(cid,uid)); muted=c.fetchone()
    if muted:
        try: await update.message.delete()
        except: pass
        conn.close(); return
    conn.close()
    s=get_settings(cid)
    if s["lock_link"] and re.search(r"https?://|t\.me|telegram\.me", text):
        try:
            m=await context.bot.get_chat_member(cid,uid)
            if m.status not in ["administrator","creator"]:
                await update.message.delete()
                await context.bot.send_message(cid,f"🚨 شاخوف حذف رابط من {update.effective_user.first_name} 🛡️ (مثل وعد)")
                return
        except: pass
    for trig,rep in MILITARY_REPLIES.items():
        if trig in text or trig.lower() in low:
            await update.message.reply_text(rep); return
    if "بحبك" in low or "احبك" in low or "وعد" in low:
        await update.message.reply_text(random.choice(WAAD_GHAZAL)+" 💖 شاخوف مثل وعد"); return
    if "سديم" in text or "استغفر" in low:
        await update.message.reply_text(f"🌙 شاخوف مثل سديم: {random.choice(SADEEM_DUA)}"); return
    if "sniper" in context.chat_data:
        try:
            g=int(text); real=context.chat_data["sniper"]
            if g==real: add_points(uid,cid,15); await update.message.reply_text(f"🎯 شاخوف إصابة {real}م +15 - {get_rank(get_points(uid,cid))} 🔥"); del context.chat_data["sniper"]
            elif abs(g-real)<=3: await update.message.reply_text("🔥 شاخوف على الشعرة!")
            elif g<real: await update.message.reply_text("⬆️ شاخوف أبعد!")
            else: await update.message.reply_text("⬇️ شاخوف أقرب!")
        except: pass
        return
    if "spy" in context.chat_data or "quiz" in context.chat_data:
        k="spy" if "spy" in context.chat_data else "quiz"; real=context.chat_data[k].lower()
        if real in low: add_points(uid,cid,10); await update.message.reply_text(f"✅ شاخوف عقلية +10 مثل وعد"); del context.chat_data[k]
        return
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.execute("SELECT reply FROM replies WHERE chat_id=? AND trigger=?",(cid,text))
    r=c.fetchone(); conn.close()
    if r: await update.message.reply_text(r[0])

async def auto_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.my_chat_member.new_chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.MEMBER]:
        if update.my_chat_member.old_chat_member.status in [ChatMember.LEFT, ChatMember.MEMBER, ChatMember.KICKED]:
            cid=update.effective_chat.id; get_settings(cid)
            s=get_settings(cid)
            if s["welcome"]:
                await context.bot.send_message(cid,"🦅 **شاخوف711 FINAL استلم القيادة** 🇾🇪\n🪖 شاخوف العسكري + 💖 كل خدمات وعد + 🌙 سديم\n🛡️ حماية + 🎯 6 ألعاب شاخوف + 💖 15 لعبة وعد\nأرسل /start - شاخوف مثل وعد كامل", reply_markup=main_kb(), parse_mode="Markdown")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"Shakhoof FINAL + Waad FULL Running")
    def log_message(self,*a): pass
def run_http():
    server=HTTPServer((IP,PORT), Handler); print(f"HTTP on {IP}:{PORT} - Shakhoof FINAL"); server.serve_forever()

def main():
    init_db()
    threading.Thread(target=run_http, daemon=True).start()
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("رتبتي", rank_cmd))
    app.add_handler(CommandHandler("ايدي", id_cmd))
    app.add_handler(CommandHandler("كيوت", cute_cmd))
    app.add_handler(CommandHandler("جمال", jamal_cmd))
    app.add_handler(CommandHandler("رجولة", rojola_cmd))
    app.add_handler(CommandHandler("قران", quran_cmd))
    app.add_handler(CommandHandler("قرآن", quran_cmd))
    app.add_handler(CommandHandler("اذكار", lambda u,c: u.message.reply_text("🌅 أذكار شاخوف مثل وعد وسديم", reply_markup=sadeem_kb())))
    app.add_handler(CommandHandler("صراحه", saraha_cmd))
    app.add_handler(CommandHandler("حب", love_cmd))
    app.add_handler(CommandHandler("بحث", search_cmd))
    app.add_handler(CommandHandler("اضف_رد", add_reply_cmd))
    app.add_handler(CommandHandler("حذف_رد", del_reply_cmd))
    app.add_handler(CommandHandler("الردود", list_replies_cmd))
    app.add_handler(CommandHandler("رفع_ادمن", promote_cmd))
    app.add_handler(CommandHandler("كتم", mute_cmd))
    app.add_handler(CommandHandler("الغاء_كتم", unmute_cmd))
    app.add_handler(CommandHandler("حظر", ban_cmd))
    app.add_handler(CommandHandler("طرد", kick_cmd))
    app.add_handler(CommandHandler("تثبيت", pin_cmd))
    app.add_handler(CommandHandler("زخرفة", zakhrafa_cmd))
    app.add_handler(CommandHandler("قوانين", rules_cmd))
    app.add_handler(CommandHandler("ضع_قوانين", set_rules_cmd))
    app.add_handler(CommandHandler("طابور", lambda u,c: u.message.reply_text("📢 طابور الصباح شاخوف 🫡 - مثل وعد", reply_markup=main_kb())))
    app.add_handler(CommandHandler("تحية", lambda u,c: u.message.reply_text("🫡 تحية عسكرية شاخوف لمعاليك يا فندم! 🇾🇪 مثل وعد"))))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(ChatMemberHandler(auto_activate, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    print("شاخوف711 FINAL شغال - شاخوف عسكري + وعد كامل 100% 🔥💖🪖")
    app.run_polling()

if __name__=="__main__": main()
