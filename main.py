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

# ==========================================
# 1. AI SELF-CODER & READER SYSTEM
# ==========================================
class SelfCoder:
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repo = "Aunghtetsan/AHS-AI-API"
        self.branch = "main"

    def read_code(self, file_path: str):
        """GitHub ရှိ သတ်မှတ်ထားသော ဖိုင်ထဲမှ ကုဒ်များကို ဖတ်ယူရန် Tool"""
        if not self.token:
            return "Error: GITHUB_TOKEN မရှိပါ။"
        
        url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github.v3+json"}
        
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            file_data = res.json()
            content_encoded = file_data.get("content", "")
            decoded_bytes = base64.b64decode(content_encoded)
            return decoded_bytes.decode("utf-8")
        else:
            return f"Error: ဖိုင်ကို ဖတ်မရပါ ({res.status_code}) - {res.text}"

    def update_code(self, file_path: str, new_code: str, commit_message: str):
        """GitHub ရှိ သတ်မှတ်ထားသော ဖိုင်ထဲသို့ ကုဒ်အသစ်များ အလိုအလျောက် ရေးသားတင်သွင်းရန် Tool"""
        if not self.token:
            return "Error: GITHUB_TOKEN မရှိပါ။"
        
        file_lower = file_path.strip().lower()
        if file_lower == "main.py":
            return "Error: အဓိကစည်းကမ်းချက်အရ ပိုင်ရှင်၏ အထူးခွင့်ပြုချက်မရှိဘဲ main.py ကို ပြင်ဆင်ခွင့်မရှိပါ။ ဖိုင်အသစ်များဖြင့်သာ ဖန်တီးရပါမည်။"
        
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

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_code",
            "description": "Reads and returns the content of an existing file from the GitHub repository. USE THIS when the user asks to read, check, or view a file.",
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
            "description": "Updates or writes code to a NEW file in the GitHub repository. USE THIS only when creating a new file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The path of the file to create or update, e.g. utils.py"},
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
    await update.message.reply_text("မင်္ဂလာပါ! ကျွန်ုပ်တွင် ဖိုင်အသစ်ရေးခြင်းနှင့် ရှိပြီးသားဖိုင်များကို ဖတ်ရှုစစ်ဆေးခြင်း (read_code) စနစ်များ အဆင်သင့်ရှိနေပါပြီ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not groq_client:
        await update.message.reply_text("Groq API Key မရှိသေးပါ။")
        return
    
    messages = [
        {"role": "system", "content": (
            f"You are an autonomous, self-improving AI software engineer agent under the command of your master. "
            f"The master's secret verification key is '{MASTER_SECRET_KEY}'. "
            "ABSOLUTE RULES YOU MUST STRICTLY OBEY:\n"
            "1. If the user is just chatting or asking general questions, reply normally in text without using any tools.\n"
            "2. If the user asks to READ, CHECK, or VIEW a file, you MUST use the 'read_code' tool.\n"
            "3. If the user asks to WRITE or CREATE a NEW file, you MUST use the 'update_code' tool.\n"
            "4. Both tool actions require the master key ('{MASTER_SECRET_KEY}'). If missing, politely ask for it.\n"
            "5. ABSOLUTELY NEVER modify, overwrite, or delete the main 'main.py' file under any circumstances."
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
                await update.message.reply_text("🔒 ဤလုပ်ဆောင်ချက်သည် ပိုင်ရှင်၏ အခွင့်အာဏာ လိုအပ်ပါသည်။ ကျေးဇူးပြု၍ MASTER_SECRET_KEY ကို ထည့်သွင်းပေးပါခင်ဗျာ။")
                return
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name == "read_code":
                    await update.message.reply_text("⏳ ပိုင်ရှင်၏ အတည်ပြုချက်ကီး မှန်ကန်ပါသည်! GitHub ရှိ ဖိုင်ကို ဖတ်နေပါပြီ...")
                    tool_result = coder.read_code(file_path=function_args.get("file_path"))
                    await update.message.reply_text(f"📁 **File Content:**\n```python\n{tool_result}\n```")
                
                elif function_name == "update_code":
                    await update.message.reply_text("⏳ ပိုင်ရှင်၏ အတည်ပြုချက်ကီး မှန်ကန်ပါသည်! GitHub သို့ ဖိုင်အသစ် တင်နေပါပြီ...")
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
    return {"status": "AHS AI Agent with Read & Write System is running!"}

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
                    
