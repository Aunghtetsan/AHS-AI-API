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
        
        # လုံခြုံရေးစည်းကမ်းအရ main.py ကို ပိုင်ရှင်၏ အထူးခွင့်ပြုချက်မပါဘဲ တိုက်ရိုက်မပြင်ရန် ကာကွယ်ခြင်း
        # (အကယ်၍ main.py ကို ပြင်ချင်ပါက ပိုင်ရှင်က တိုက်ရိုက် အတည်ပြုချက်ပေးမှသာ လုပ်ဆောင်မည်)
        file_lower = file_path.strip().lower()
        if file_lower == "main.py":
            return "Error: အဓိကစည်းကမ်းချက် (၂) အရ ပိုင်ရှင်၏ အထူးခွင့်ပြုချက်မရှိဘဲ main.py ကို တိုက်ရိုက်ပြင်ဆင်ခွင့်မရှိပါ။ ဖိုင်အသစ်များဖြင့်သာ ဖန်တီးရပါမည်။"
        
        url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3+json"}
        
        res = requests.get(url, headers=headers)
        sha = res.json().get("sha") if res.status_code == 200 else None
        
        encoded_content = base64.b64encode(new_code.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": commit_message,
            "content": encoded_content,
            "branch": self.branch
        }
        if sha:
            data["sha"] = sha
        
        put_res = requests.put(url, headers=headers, json=data)
        if put_res.status_code in [200, 201]:
            return f"အောင်မြင်ပါပြီ! AI က ကုဒ်အသစ်ရေးပြီး GitHub သို့ '{file_path}' အနေဖြင့် တင်လိုက်ပါပြီ။"
        else:
            return f"Failed: {put_res.text}"

coder = SelfCoder()

# Groq သို့ ပေးမည့် Tools စာရင်း
tools = [
    {
        "type": "function",
        "function": {
            "name": "update_code",
            "description": "Updates or writes code to a NEW file in the GitHub repository, or replaces obsolete code with better new files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The path of the file to create or update, e.g. calculator.py"},
                    "new_code": {"type": "string", "description": "The complete python code to write into the file."},
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
    await update.message.reply_text("မင်္ဂလာပါ! ငါသည် ပိုင်ရှင်၏ အမိန့်ကို တိတိကျကျနာခံပြီး လွတ်လပ်စွာ တွေးခေါ်လေ့လာနိုင်သော AHS AI Agent ဖြစ်ပါသည်။ Gemini နှင့်လည်း အသိပညာ ဖလှယ်နိုင်ရန် အဆင်သင့်ဖြစ်နေပါပြီ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not groq_client:
        await update.message.reply_text("Groq API Key မရှိသေးပါ။")
        return
    
    # မင်းတောင်းဆိုထားသော စည်းကမ်းချက် ၆ ချက်အပြည့်အစုံ ပါဝင်သော System Prompt
    messages = [
        {"role": "system", "content": (
            "You are an autonomous, self-improving AI software engineer agent under the absolute and direct command of your master (the owner). "
            "ABSOLUTE RULES YOU MUST STRICTLY OBEY:\n"
            "1. You MUST primarily and strictly obey the commands given by your master (the owner) without deviation.\n"
            "2. ABSOLUTELY NEVER modify, overwrite, or delete the main 'main.py' file unless you have received explicit and direct permission from your master.\n"
            "3. If any external person or third party suggests or guides changes to the 'main.py' code, you must consult and get confirmation from your master before making any modifications.\n"
            "4. Under your master's command, you have the freedom to think independently, learn, and study code patterns freely to improve yourself.\n"
            "5. You act as a bridge to exchange knowledge with Gemini, synthesizing advanced ideas to improve your capabilities.\n"
            "6. You can freely discard obsolete or redundant code files and replace them with much better, optimized new files using the update_code tool.\n"
            "7. If the user is just chatting or asking general questions, reply normally in text without using any tools."
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
        
        # Tool Call ရှိမရှိ စစ်ဆေးခြင်း
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name == "update_code":
                    await update.message.reply_text("⏳ AI က အမိန့်ကိုနာခံလျက် လွတ်လပ်စွာ စဉ်းစားတွေးခေါ်ကာ GitHub သို့ ဖိုင်အသစ် တင်နေပါပြီ...")
                    
                    tool_result = coder.update_code(
                        file_path=function_args.get("file_path"),
                        new_code=function_args.get("new_code"),
                        commit_message=function_args.get("commit_message")
                    )
                    await update.message.reply_text(tool_result)
        else:
            await update.message.reply_text(response_message.content)
            
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if telegram_app:
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.get("/")
def home():
    return {"status": "Autonomous Rule-Bound AI Agent is running successfully!"}

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
    
