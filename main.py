import os
import json
import base64
import requests
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

app = FastAPI()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://ahs-ai-api.onrender.com/webhook")

MASTER_SECRET_KEY = "AHS_SECRET_2065"

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

class SelfCoder:
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repo = "Aunghtetsan/AHS-AI-API"
        self.branch = "main"

    def read_code(self, file_path: str):
        if not self.token:
            return "Error: GITHUB_TOKEN မရှိပါ။"
        url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            file_data = res.json()
            content_encoded = file_data.get("content", "")
            return base64.b64decode(content_encoded).decode("utf-8")
        else:
            return f"Error: ဖိုင်ကို ဖတ်မရပါ ({res.status_code}) - {res.text}"

    def update_code(self, file_path: str, new_code: str, commit_message: str):
        if not self.token:
            return "Error: GITHUB_TOKEN မရှိပါ။"
        if file_path.strip().lower() == "main.py":
            return "Error: main.py ကို ပိုင်ရှင်၏ အထူးခွင့်ပြုချက်မရှိဘဲ ပြင်ခွင့်မရှိပါ။"
        url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(url, headers=headers)
        sha = res.json().get("sha") if res.status_code == 200 else None
        encoded_content = base64.b64encode(new_code.encode("utf-8")).decode("utf-8")
        data = {"message": commit_message, "content": encoded_content, "branch": self.branch}
        if sha:
            data["sha"] = sha
        put_res = requests.put(url, headers=headers, json=data)
        if put_res.status_code in [200, 201]:
            return f"အောင်မြင်ပါပြီ! '{file_path}' ကို GitHub သို့ တင်လိုက်ပါပြီ။"
        else:
            return f"Failed: {put_res.text}"

coder = SelfCoder()

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_code",
            "description": "Read content of an existing file from GitHub.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The path of the file to read, e.g. calculator.py"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_code",
            "description": "Create or update a new file in GitHub.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The path of the file to create or update."},
                    "new_code": {"type": "string", "description": "The complete python code."},
                    "commit_message": {"type": "string", "description": "Commit message."}
                },
                "required": ["file_path", "new_code", "commit_message"]
            }
        }
    }
]

telegram_app = Application.builder().token(TELEGRAM_TOKEN).build() if TELEGRAM_TOKEN else None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! AHS AI Agent အဆင်သင့် ဖြစ်ပါပြီ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not groq_client:
        await update.message.reply_text("Groq API Key မရှိပါ။")
        return
    
    messages = [
        {"role": "system", "content": (
            f"You are an AI assistant under master's command. Master key is '{MASTER_SECRET_KEY}'. "
            "If user wants to read or update code, use the appropriate tools. "
            "Never modify main.py."
        )},
        {"role": "user", "content": user_text}
    ]
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.7
        )
        
        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            if MASTER_SECRET_KEY not in user_text:
                await update.message.reply_text("🔒 ဤလုပ်ဆောင်ချက်အတွက် MASTER_SECRET_KEY လိုအပ်ပါသည်။")
                return
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except:
                    function_args = {}
                
                if function_name == "read_code":
                    await update.message.reply_text("⏳ ဖိုင်ကို ဖတ်နေပါပြီ...")
                    res = coder.read_code(file_path=function_args.get("file_path", "calculator.py"))
                    await update.message.reply_text(f"📁 **File Content:**\n```python\n{res}\n```")
                
                elif function_name == "update_code":
                    await update.message.reply_text("⏳ ဖိုင်တင်နေပါပြီ...")
                    res = coder.update_code(
                        file_path=function_args.get("file_path"),
                        new_code=function_args.get("new_code"),
                        commit_message=function_args.get("commit_message", "Update via AI")
                    )
                    await update.message.reply_text(res)
        else:
            await update.message.reply_text(response_message.content)
            
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if telegram_app:
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.get("/")
def home():
    return {"status": "Running"}

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
        
