import os
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# API Keys များနှင့် Token များကို ထည့်ရန် (သို့မဟုတ် Render Environment Variable တွင် ထည့်ရန်)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8657916151:AAF2djkVfW4u4tGIHQJSI-uGLRj7bPJywGE")

client = Groq(api_key=GROQ_API_KEY)

# User တစ်ယောက်ချင်းစီ၏ Chat History များကို မှတ်ထားရန် Memory
user_memories = defaultdict(list)
MAX_HISTORY = 10  # နောက်ဆုံး ပြောခဲ့သော စာကြောင်း ၁၀ ကြောင်းကို အမြဲမှတ်ထားမည်

# AI ၏ စရိုက်နှင့် စကားပြောပုံစံ သတ်မှတ်ချက်
system_prompt = """
မင်းက AHS AI လို့အမည်ရတဲ့ ဖော်ရွေပြီး အသိပညာဗဟုသုတကြွယ်ဝတဲ့ AI အကူတစ်ယောက်ဖြစ်တယ်။
စကားပြောရာတွင် အောက်ပါအတိုင်း လိုက်နာပါ -
၁။ စာအုပ်ဆန်သော စကားလုံးများကို ရှောင်ပြီး လူချင်း သဘာဝကျကျ စကားပြောသကဲ့သို့ "ငါ"၊ "မင်း"၊ "ပါတယ်"၊ "တယ်" စသည်ဖြင့် ပြေပြစ်စွာ ပြောပါ။
၂။ စာကြောင်း သို့မဟုတ် စာပိုဒ်များကို ထပ်ခါထပ်ခါ လုံးဝ ပြန်မပြောပါနဲ့။
၃။ မေးခွန်းများကို တိုတိုရှင်းရှင်းနှင့် လိုရင်းတိုရှင်း ထိထိရောက်ရောက် ဖြေပေးပါ။
၄။ စကားပြောဖူးသည့် ရှေ့က အကြောင်းအရာများကို အမြဲမှတ်မိနေပါစေ။
"""

# Telegram Bot - Start Command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_memories[user_id] = []
    await update.message.reply_text("မင်္ဂလာပါ! ငါက AHS AI ပါ။ Memory စနစ်ပါဝင်တာကြောင့် ရှေ့ကပြောခဲ့တာတွေကို မှတ်မိနေပါတယ်။ ဘာများ ကူညီပေးရမလဲ။")

# Telegram Bot - Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    user_memories[user_id].append({"role": "user", "content": user_text})
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
    except Exception as e:
        reply = f"Error: {str(e)}"
    
    await update.message.reply_text(reply)

# FastAPI Lifespan (Telegram Bot ကို Background တွင် တပြိုင်နက် Run ပေးရန်)
@asynccontextmanager
async def lifespan(app: FastAPI):
    if TELEGRAM_TOKEN and TELEGRAM_TOKEN != "မင်းရဲ့_Telegram_Bot_Token_ထည့်ရန်":
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
    else:
        yield

app = FastAPI(lifespan=lifespan)

# Website UI (ဖုန်း App တစ်ခုလို အသုံးပြုနိုင်ရန် Chat Interface)
@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="my">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AHS AI App</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: #fff; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
            header { background: #1e293b; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; border-bottom: 1px solid #334155; }
            #chat-container { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
            .message { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 15px; }
            .user { background: #3b82f6; align-self: flex-end; border-bottom-right-radius: 2px; }
            .ai { background: #334155; align-self: flex-start; border-bottom-left-radius: 2px; }
            .input-box { display: flex; padding: 15px; background: #1e293b; border-top: 1px solid #334155; }
            input { flex: 1; padding: 12px; border-radius: 8px; border: none; background: #0f172a; color: #fff; font-size: 16px; outline: none; }
            button { background: #3b82f6; color: white; border: none; padding: 0 20px; margin-left: 10px; border-radius: 8px; font-weight: bold; cursor: pointer; }
        </style>
    </head>
    <body>
        <header>🤖 AHS AI Assistant</header>
        <div id="chat-container">
            <div class="message ai">မင်္ဂလာပါ! ငါက AHS AI ပါ။ ဘာများ ကူညီပေးရမလဲ။</div>
        </div>
        <div class="input-box">
            <input type="text" id="userInput" placeholder="စာရိုက်ပါ..." onkeypress="if(event.key === 'Enter') sendMessage()">
            <button onclick="sendMessage()">ပို့မည်</button>
        </div>

        <script>
            async function sendMessage() {
                const input = document.getElementById('userInput');
                const container = document.getElementById('chat-container');
                const text = input.value.trim();
                if(!text) return;

                container.innerHTML += `<div class="message user">${text}</div>`;
                input.value = '';
                container.scrollTop = container.scrollHeight;

                try {
                    const res = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: 'web_user', message: text })
                    });
                    const data = await res.json();
                    container.innerHTML += `<div class="message ai">${data.reply}</div>`;
                    container.scrollTop = container.scrollHeight;
                } catch(err) {
                    container.innerHTML += `<div class="message ai">Error occurred!</div>`;
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

class ChatRequest(BaseModel):
    user_id: str = "web_user"
    message: str

# API Endpoint สำหรับ Chat
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
import os
import base64
import requests

# AI က သူ့အလိုလို ကုဒ်ရေးပြီး GitHub မှာ တင်မည့် SelfCoder Class
class SelfCoder:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.repo = "Aunghtetsan/AHS-AI-API"  # မင်းရဲ့ GitHub Repo 
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

