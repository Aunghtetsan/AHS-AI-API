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

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ==========================================
# 1. AI SELF-CODER SYSTEM & TOOL DEFINITION
# ==========================================
class SelfCoder:
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repo = "Aunghtetsan/AHS-AI-API"
        self.branch = "main"

    def update_code(self, file_path: str, new_code: str, commit_message: str):
        """GitHub ရှိ သတ်မှတ်ထားသော ဖိုင်ထဲသို့ ကုဒ်အသစ်များ အလိုအလျောက် ရေးသားတင်သွင်းရန် Tool"""
        if not self.token:
            return "Error: GITHUB_TOKEN မရှိပါ။"
        
        url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3+json"}
        
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return f"Error getting file: {res.text}"
        
        sha = res.json().get("sha")
        encoded_content = base64.b64encode(new_code.encode("utf-8")).decode("utf-8")
        
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

# Groq သို့ ပေးမည့် Tools စာရင်း
tools = [
    {
        "type": "function",
        "function": {
            "name": "update_code",
            "description": "Updates or writes code to a file in the GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The path of the file to update, e.g. main.py"},
                    "new_code": {"type": "string", "description": "The complete new python code to write into the file."},
                    "commit_message": {"type": "string", "description": "Commit message for the update."}
                },
                "required": ["file_path", "new_code", "commit_message"]
            }
        }
    }
]

# ==========================================
# 2. TELEGRAM MESSAGE HANDLER WITH AGENT LOGIC
# ==========================================
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build() if TELEGRAM_TOKEN else None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! ငါသည် ကိုယ့်ကိုကိုယ် ကုဒ်ရေးပြီး တိုးတက်စေနိုင်သော အစစ်အမှန် AI Agent ဖြစ်ပါသည်။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not groq_client:
        await update.message.reply_text("Groq API Key မရှိသေးပါ။")
        return
    
    messages = [
        {"role": "system", "content": "You are an autonomous AI software engineer agent. If the user asks you to modify code, create features, or fix bugs in the repository, you MUST call the update_code tool to apply changes directly to GitHub."},
        {"role": "user", "content": user_text}
    ]
    
    try:
        # First API call to Groq with tools enabled
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.7
        )
        
        response_message = response.choices[0].message
        
        # Check if the model wants to call a tool (Self-Coding)
        if response_message.tool_calls:
            messages.append(response_message)
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name == "update_code":
                    await update.message.reply_text("⏳ AI က ကုဒ်ကို ကိုယ်တိုင်ရေးသားပြီး GitHub သို့ တင်နေပါပြီ...")
                    tool_result = coder.update_code(
                        file_path=function_args.get("file_path"),
                        new_code=function_args.get("new_code"),
                        commit_message=function_args.get("commit_message")
                    )
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_result
                    })
            
            # Second call to get the final response after tool execution
            second_response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages
            )
            await update.message.reply_text(second_response.choices[0].message.content)
        else:
            await update.message.reply_text(response_message.content)
            
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if telegram_app:
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.get("/")
def home():
    return {"status": "Autonomous AI Agent with Self-Coding Tool is running!"}

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
      
