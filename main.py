import os
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

client = Groq(api_key=GROQ_API_KEY)

# User တစ်ယောက်ချင်းစီရဲ့ စကားပြောထားသော History များကို မှတ်ထားရန် Memory Dictionary
user_memories = defaultdict(list)
MAX_HISTORY = 10  # မေ့မသွားစေရန် နောက်ဆုံးပြောခဲ့သော စာကြောင်း ၁၀ ကြောင်းကို အမြဲမှတ်ထားမည်

system_prompt = """
မင်းက AHS AI လို့အမည်ရတဲ့ ဖော်ရွေပြီး အသိပညာဗဟုသုတကြွယ်ဝတဲ့ AI အကူတစ်ယောက်ဖြစ်တယ်။
စကားပြောရာတွင် အောက်ပါအတိုင်း လိုက်နာပါ -
၁။ စာအုပ်ဆန်သော စကားလုံးများကို ရှောင်ပြီး လူချင်း သဘာဝကျကျ စကားပြောသကဲ့သို့ "ငါ"၊ "မင်း"၊ "ပါတယ်"၊ "တယ်" စသည်ဖြင့် ပြေပြစ်စွာ ပြောပါ။
၂။ စာကြောင်း သို့မဟုတ် စာပိုဒ်များကို ထပ်ခါထပ်ခါ လုံးဝ ပြန်မပြောပါနဲ့။
၃။ မေးခွန်းများကို တိုတိုရှင်းရှင်းနှင့် လိုရင်းတိုရှင်း ထိထိရောက်ရောက် ဖြေပေးပါ။
၄။ စကားပြောဖူးသည့် ရှေ့က အကြောင်းအရာများကို အမြဲမှတ်မိနေပါစေ။
"""

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memories[user_id] = []  # Start နှိပ်ပါက Memory အသစ်ပြန်စမည်
    await update.message.reply_text("မင်္ဂလာပါ! ငါက AHS AI ပါ။ Memory စနစ်ပါဝင်တာကြောင့် ရှေ့ကပြောခဲ့တာတွေကို မှတ်မိနေမှာပါ။ ဘာများ ကူညီပေးရမလဲ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # User ရဲ့ စာကို Memory ထဲသို့ ထည့်ခြင်း
    user_memories[user_id].append({"role": "user", "content": user_text})
    
    # Memory ရှည်လွန်းပါက အဟောင်းများကို ဖျက်ပြီး နောက်ဆုံး ၁၀ ကြောင်းပဲ ချန်မည်
    if len(user_memories[user_id]) > MAX_HISTORY:
        user_memories[user_id] = user_memories[user_id][-MAX_HISTORY:]

    # System Prompt + Memory History အားလုံးကို AI ထံ ပို့ပေးခြင်း
    messages = [{"role": "system", "content": system_prompt}] + user_memories[user_id]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.6,
            presence_penalty=0.8,
            frequency_penalty=0.8,
            max_tokens=1024
        )
        reply = response.choices[0].message.content
        
        # AI ရဲ့ ပြန်စာကိုလည်း Memory ထဲသို့ မှတ်ထားခြင်း
        user_memories[user_id].append({"role": "assistant", "content": reply})

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
    return {"status": "Online", "memory": "Active"}

class ChatRequest(BaseModel):
    user_id: str = "default_user"
    message: str

@app.post("/chat")
def chat_api(request: ChatRequest):
    user_id = request.user_id
    user_memories[user_id].append({"role": "user", "content": request.message})
    
    if len(user_memories[user_id]) > MAX_HISTORY:
        user_memories[user_id] = user_memories[user_id][-MAX_HISTORY:]

    messages = [{"role": "system", "content": system_prompt}] + user_memories[user_id]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.6,
            presence_penalty=0.8,
            frequency_penalty=0.8,
            max_tokens=1024
        )
        reply = response.choices[0].message.content
        user_memories[user_id].append({"role": "assistant", "content": reply})
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
