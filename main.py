import os
import base64
import requests
from fastapi import FastAPI, Request
from pydantic import BaseModel
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# FastAPI App တည်ဆောက်ခြင်း
app = FastAPI()

# Environment Variables တွေ ခေါ်ယူခြင်း
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
# Render က သင့်ရဲ့ App URL (ဥပမာ - https://ahs-ai-api.onrender.com)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://ahs-ai-api.onrender.com/webhook")

# Groq AI Client သတ်မှတ်ခြင်း
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ==========================================
# 1. AI SELF-CODER SYSTEM (GitHub Integration)
# ==========================================
class SelfCoder:
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repo = "Aunghtetsan/AHS-AI-API"  # မင်းရဲ့ GitHub Repository နာမည်
        self.branch = "main"

    def update_code(self, file_path, new_code, commit_message):
        if not self.token:
            return "Error: GITHUB_TOKEN မရှိပါ။"
        
        url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3+json"}
        
        # 1. Get current file SHA
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return f"Error getting file: {res.text}"
        
        sha = res.json().get("sha")
        
        # 2. Encode new code to base64
        encoded_content = base64.b64encode(new_code.encode("utf-8")).decode("utf-8")
        
        # 3. Commit new code to GitHub
        data = {
            "message": commit_message,
            "content": encoded_content,
            "sha": sha,
            "branch": self.branch
        }
        
        put_res = requests.put(url, headers=headers, json=data)
        if put_res.status_code in [200, 201]:
            return "အောင်မြင်ပါပြီ! AI က ကုဒ်အသစ်ရေးပြီး GitHub ကို တင်လိုက်ပါပြီ။ Render က အလိုအလျောက် Deploy ဆက်လုပ်ပါမည်။"
        else:
            return f"Failed: {put_res.text}"

coder = SelfCoder()

# ==========================================
# 2. FASTAPI WEB ROUTES & TELEGRAM WEBHOOK
# =================-=========================

@app.get("/")
def home():
    return {"status": "AHS AI Agent is running successfully with Self-Coding capability!"}

# Telegram Bot Setup
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build() if TELEGRAM_TOKEN else None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! ငါက မင်းရဲ့ အမိန့်အောက်က အဆင့်မြင့် AI Agent ဖြစ်ပါတယ်။ ဘာကူညီရမလဲ?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not groq_client:
        await update.message.reply_text("Groq API Key မရှိသေးပါ။")
        return
    
    try:
        # Groq Llama 3 မော်ဒယ်ဖြင့် အဖြေထုတ်ခြင်း
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an advanced AI assistant under the user's direct command, capable of programming and self-improvement."},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if telegram_app:
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.on_event("startup")
async def startup_event():
    if telegram_app:
        await telegram_app.initialize()
        await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
        await telegram_app.start()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not telegram_app:
        return {"status": "Telegram app not configured"}
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}
    
