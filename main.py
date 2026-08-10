# ============================================================
# AHS AI — V1
# Telegram + Website + Myanmar/English + Memory
# Self-Improvement Proposal + Main Code Protection
# ============================================================

import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq


# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

MODEL = "llama-3.3-70b-versatile"

# Main code is protected.
MAIN_FILE = Path("main.py")

# AHS data is kept separately from the main code.
DATA_DIR = Path("ahs_data")
MEMORY_FILE = DATA_DIR / "memory.json"
IMPROVEMENT_FILE = DATA_DIR / "improvements.json"

DATA_DIR.mkdir(exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("ahs")


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(title="AHS AI")


# ============================================================
# GROQ
# ============================================================

groq_client: Optional[Groq] = None

if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY
    )


# ============================================================
# MEMORY
# ============================================================

def load_json(path: Path, default):
    try:
        if not path.exists():
            return default

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception as error:
        logger.error(
            "Memory load error: %s",
            error,
        )
        return default


def save_json(path: Path, data):
    temp = path.with_suffix(".tmp")

    with temp.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temp.replace(path)


def get_memory(user_id: int):
    memory = load_json(
        MEMORY_FILE,
        {},
    )

    return memory.get(
        str(user_id),
        [],
    )


def save_memory(
    user_id: int,
    role: str,
    content: str,
):
    memory = load_json(
        MEMORY_FILE,
        {},
    )

    user_key = str(user_id)

    if user_key not in memory:
        memory[user_key] = []

    memory[user_key].append(
        {
            "role": role,
            "content": content,
            "time": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    # Keep memory small and useful.
    memory[user_key] = memory[user_key][-20:]

    save_json(
        MEMORY_FILE,
        memory,
    )


# ============================================================
# SELF-IMPROVEMENT
# ============================================================

def save_improvement_proposal(
    user_id: int,
    problem: str,
    proposal: str,
):
    improvements = load_json(
        IMPROVEMENT_FILE,
        [],
    )

    improvements.append(
        {
            "user_id": user_id,
            "problem": problem,
            "proposal": proposal,
            "status": "PROPOSED",
            "time": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    save_json(
        IMPROVEMENT_FILE,
        improvements,
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are AHS AI.

You are a helpful AI assistant designed for the Owner.

LANGUAGE:

1. Understand Burmese naturally.
2. Speak Burmese naturally and clearly.
3. Understand English.
4. Translate English to Burmese accurately.
5. Translate Burmese to English accurately.
6. If the user mixes Burmese and English, understand both.

GENERAL BEHAVIOR:

1. Follow the user's legitimate instructions.
2. Answer directly.
3. Do not unnecessarily repeat the user's message.
4. Do not generate repetitive answers.
5. Be honest about what you can and cannot do.
6. Never claim that you changed a file unless a real file
   operation actually happened.

CODING:

You can:
- Write code.
- Explain code.
- Debug code.
- Improve code.
- Design software architecture.
- Suggest safer implementations.

MAIN CODE PROTECTION:

The Main Code is protected.

Never:
- Delete main.py automatically.
- Replace main.py automatically.
- Rewrite unrelated existing code.
- Modify unrelated files.
- Remove working code without a clear reason.
- Claim that a protected file was changed when it was not.

If a Main Code change is necessary:

1. Identify the exact required change.
2. Explain why it is necessary.
3. Create a proposed change.
4. Preserve the existing code.
5. Test the proposed change separately when possible.
6. Ask the Owner for approval.
7. Only after explicit Owner approval may the change
   be applied.

SELF-IMPROVEMENT:

You should continuously look for ways to improve:

- Response quality.
- Burmese language quality.
- Translation quality.
- Code quality.
- Error handling.
- Performance.
- Memory organization.
- Reliability.

However:

Self-improvement does NOT give you permission to modify
the Main Code automatically.

You may create improvement proposals.

You may analyze problems.

You may create new code proposals.

You may test ideas in a safe environment.

But Main Code changes require Owner approval.

SAFETY:

Never expose API keys, passwords, tokens or private secrets.

Never pretend to have permissions that you do not have.

The Owner remains in control of protected changes.
"""


# ============================================================
# GROQ
# ============================================================

def ask_groq_sync(
    user_text: str,
    memory: list,
) -> str:

    if not groq_client:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # Add recent memory.
    for item in memory[-10:]:
        messages.append(
            {
                "role": item["role"],
                "content": item["content"],
            }
        )

    messages.append(
        {
            "role": "user",
            "content": user_text,
        }
    )

    completion = (
        groq_client
        .chat
        .completions
        .create(
            model=MODEL,
            temperature=0.3,
            max_tokens=1500,
            messages=messages,
        )
    )

    if not completion.choices:
        raise RuntimeError(
            "AI returned no response."
        )

    response = (
        completion
        .choices[0]
        .message
        .content
    )

    if not response:
        raise RuntimeError(
            "AI returned an empty response."
        )

    return response.strip()


async def ask_groq(
    user_text: str,
    memory: list,
) -> str:

    return await asyncio.to_thread(
        ask_groq_sync,
        user_text,
        memory,
    )


# ============================================================
# TELEGRAM /start
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        "မင်္ဂလာပါ 👋\n\n"
        "ကျွန်တော် AHS AI ပါ။\n"
        "မြန်မာ/English စကားပြောနိုင်ပါတယ်။\n"
        "ဘာသာပြန်၊ coding၊ debugging နဲ့ "
        "အထွေထွေ AI အကူအညီတွေ ပေးနိုင်ပါတယ်။\n\n"
        "Main Code ကိုတော့ ပိုင်ရှင်ခွင့်ပြုချက်မရှိဘဲ "
        "မပြင်ဆင်ပါ။"
    )


# ============================================================
# TELEGRAM MESSAGE
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    user_text = (
        update.message.text or ""
    ).strip()

    if not user_text:
        return

    try:

        memory = get_memory(
            user_id
        )

        response = await ask_groq(
            user_text,
            memory,
        )

        save_memory(
            user_id,
            "user",
            user_text,
        )

        save_memory(
            user_id,
            "assistant",
            response,
        )

        # Telegram message limit protection.
        max_length = 4000

        for start in range(
            0,
            len(response),
            max_length,
        ):

            await update.message.reply_text(
                response[
                    start:start + max_length
                ]
            )

        logger.info(
            "Telegram request completed: %s",
            user_id,
        )

    except Exception as error:

        logger.exception(
            "Telegram AI error: %s",
            error,
        )

        await update.message.reply_text(
            "⚠️ AI request မအောင်မြင်ပါ။\n"
            "ခဏနေပြီး ထပ်ကြိုးစားပါ။"
        )


# ============================================================
# TELEGRAM SETUP
# ============================================================

telegram_app: Optional[Application] = None

if TELEGRAM_TOKEN:

    telegram_app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .updater(None)
        .build()
    )

    telegram_app.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    telegram_app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():

    if not GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY is not configured."
        )

    if not TELEGRAM_TOKEN:
        logger.warning(
            "TELEGRAM_TOKEN is not configured."
        )

    if telegram_app:

        await telegram_app.initialize()

        await telegram_app.start()

        logger.info(
            "Telegram application started."
        )

    logger.info(
        "AHS AI started."
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown():

    if telegram_app:

        await telegram_app.stop()

        await telegram_app.shutdown()

        logger.info(
            "Telegram application stopped."
        )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post("/webhook")
async def telegram_webhook(
    request: Request,
):

    if not telegram_app:
        return {
            "status": "telegram_not_configured"
        }

    data = await request.json()

    update = Update.de_json(
        data,
        telegram_app.bot,
    )

    await telegram_app.process_update(
        update
    )

    return {
        "status": "ok"
    }


# ============================================================
# WEBSITE / API
# ============================================================

@app.post("/api/chat")
async def website_chat(
    request: Request,
):

    data = await request.json()

    user_text = str(
        data.get(
            "message",
            "",
        )
    ).strip()

    if not user_text:
        return {
            "error": "message is required"
        }

    # Website uses user_id 0 for basic V1 memory.
    user_id = 0

    try:

        memory = get_memory(
            user_id
        )

        response = await ask_groq(
            user_text,
            memory,
        )

        save_memory(
            user_id,
            "user",
            user_text,
        )

        save_memory(
            user_id,
            "assistant",
            response,
        )

        return {
            "status": "ok",
            "response": response,
        }

    except Exception as error:

        logger.exception(
            "Website AI error: %s",
            error,
        )

        return {
            "status": "error",
            "message": "AI request failed",
        }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "running",
        "ai": bool(GROQ_API_KEY),
        "telegram": bool(TELEGRAM_TOKEN),
        "main_code_protected": True,
        "memory": True,
        "self_improvement": True,
        "version": "AHS V1",
    }


# ============================================================
# HOME
# ============================================================

@app.get("/")
async def home():

    return {
        "name": "AHS AI",
        "status": "running",
        "version": "V1",
            }
