import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

client = Groq(api_key=GROQ_API_KEY)

# မြန်မာလို လူသားတစ်ယောက်လို သဘာဝကျကျ စကားပြောစေရန် အကောင်းဆုံး Prompt
system_prompt = """
မင်းက AHS AI လို့အမည်ရတဲ့ ဖော်ရွေပြီး အသိပညာဗဟုသုတကြွယ်ဝတဲ့ AI အကူတစ်ယောက်ဖြစ်တယ်။
စကားပြောရာတွင် အောက်ပါအတိုင်း လိုက်နာပါ -
၁။ စာအုပ်ဆန်သော စကားလုံးများကို ရှောင်ပြီး လူချင်း သဘာဝကျကျ စကားပြောသကဲ့သို့ "ငါ"၊ "မင်း"၊ "ပါတယ်"၊ "တယ်" စသည်ဖြင့် ပြေပြစ်စွာ ပြောပါ။
၂။ စာကြောင်း သို့မဟုတ် စာပိုဒ်များကို ထပ်ခါထပ်ခါ လုံးဝ ပြန်မပြောပါနဲ့။
၃။ မေးခွန်းများကို တိုတိုရှင်းရှင်းနှင့် လိုရင်းတိုရှင်း ထိထိရောက်ရောက် ဖြေပေးပါ။
၄။ စတော့ သို့မဟုတ် စီးပွားရေးအကြောင်းမေးပါက အဓိကအချက်များကို ရှင်းလင်းစွာ ရှင်းပြပါ။
"""

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! ငါက AHS AI ပါ။ ဘာတွေ ကူညီပေးရမလဲ၊ လွတ်လပ်စွာ မေးလို့ရပါတယ်နော်။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # Groq ရဲ့ အမြင့်ဆုံးနှင့် အကောင်းဆုံး Free Model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.6,
            presence_penalty=0.8, # စာကြောင်း ထပ်မသွားစေရန် တားမြစ်သည့် တန်ဖိုး
            frequency_penalty=0.8,
            max_tokens=1024
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"Error: {str(e)}"
    
    await update.message.reply_text(reply)

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
    return {"status": "Online", "model": "Llama 3.3 70B"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat_api(request: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            temperature=0.6,
            presence_penalty=0.8,
            frequency_penalty=0.8,
            max_tokens=1024
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
