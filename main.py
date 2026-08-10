@import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Key များနှင့် Configurations
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8657916151:AAHxxaV1...")

client = Groq(api_key=GROQ_API_KEY)

# မြန်မာလို သဘာဝကျကျနှင့် တိုတိုရှင်းရှင်း ဖြေဆိုရန် System Prompt
system_prompt = """
မင်းက နာမည် AHS AI ဖြစ်ပြီး မြန်မာလို အလွန်သဘာဝကျကျ၊ ယဉ်ကျေးပြေပြစ်စွာ ဖြေကြားပေးတဲ့ AI အကူဖြစ်တယ်။
စည်းကမ်းများ:
၁။ မြန်မာစာလုံးပေါင်းနှင့် ဝါကျဖွဲ့ထုံးကို မှန်ကန်အောင်သုံးပါ။
၂။ စာကြောင်းများကို ထပ်ခါထပ်ခါ ပြန်မပြောပါနဲ့။ တိုတိုနှင့် ရှင်းရှင်းလင်းလင်း ဖြေပါ။
၃။ သဘာဝကျသော စကားပြောဟန် ရေးပါ။
"""

# Telegram Bot Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! ငါက AHS AI Bot ပါ။ ဘာများ ကူညီပေးရမလဲ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",  # မြန်မာစာလုံးပေါင်း မထပ်စေရန် Model ပြောင်းထားသည်
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.5,
            max_tokens=1024
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"Error: {str(e)}"
    
    await update.message.reply_text(reply)

# Render ပေါ်မှာ FastAPI နဲ့ Telegram Bot တွဲဖက် run ရန် Lifespan Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start_command))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    yield
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    return {"status": "Online", "message": "AHS AI & Telegram Bot အလုပ်လုပ်နေပါပြီ"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat_api(request: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            temperature=0.5,
            max_tokens=1024
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
