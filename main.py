# ============================================================
# AHS AI — V2 FOUNDATION
# Telegram + Website + Myanmar/English + Memory
# Security + Main Code Protection + Improvement Proposals
# Stock/Paper Trading foundation
# ============================================================

import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

MODEL = os.getenv(
    "AHS_MODEL",
    "llama-3.3-70b-versatile",
)

APP_VERSION = "AHS V2"

MAIN_FILE = Path("main.py")

DATA_DIR = Path("ahs_data")
MEMORY_FILE = DATA_DIR / "memory.json"
IMPROVEMENT_FILE = DATA_DIR / "improvements.json"
PAPER_ACCOUNT_FILE = DATA_DIR / "paper_account.json"

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

app = FastAPI(
    title="AHS AI",
    version=APP_VERSION,
)


# ============================================================
# GROQ
# ============================================================

groq_client: Optional[Groq] = None

if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY
    )


# ============================================================
# JSON STORAGE
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
            "JSON load error: %s",
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


# ============================================================
# MEMORY
# ============================================================

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

    key = str(user_id)

    if key not in memory:
        memory[key] = []

    memory[key].append(
        {
            "role": role,
            "content": content,
            "time": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    memory[key] = memory[key][-20:]

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
# SECURITY
# ============================================================

PROTECTED_FILES = {
    "main.py",
    ".env",
    "credentials.json",
}

CRITICAL_KEYWORDS = {
    "delete",
    "destroy",
    "deploy",
    "production",
    "payment",
    "withdraw",
    "transfer",
    "api key",
    "token",
    "password",
    "secret",
    "permission",
    "main.py",
    "security",
}


def contains_critical_action(text: str) -> bool:

    text_lower = text.lower()

    return any(
        keyword in text_lower
        for keyword in CRITICAL_KEYWORDS
    )


def is_protected_file(path: str) -> bool:

    normalized = path.replace(
        "\\",
        "/",
    ).lower()

    if normalized in {
        item.lower()
        for item in PROTECTED_FILES
    }:
        return True

    if normalized.startswith(".env"):
        return True

    if "credential" in normalized:
        return True

    if "secret" in normalized:
        return True

    return False


# ============================================================
# PAPER TRADING
# ============================================================

DEFAULT_PAPER_ACCOUNT = {
    "cash": 100000.0,
    "positions": {},
    "orders": [],
}


def get_paper_account():

    return load_json(
        PAPER_ACCOUNT_FILE,
        DEFAULT_PAPER_ACCOUNT.copy(),
    )


def save_paper_account(account):

    save_json(
        PAPER_ACCOUNT_FILE,
        account,
    )


def paper_buy(
    symbol: str,
    quantity: int,
    price: float,
):

    if quantity <= 0 or price <= 0:
        raise ValueError(
            "Quantity and price must be positive."
        )

    account = get_paper_account()

    cost = quantity * price

    if account["cash"] < cost:
        raise ValueError(
            "Insufficient paper-trading cash."
        )

    account["cash"] -= cost

    positions = account.setdefault(
        "positions",
        {},
    )

    position = positions.setdefault(
        symbol.upper(),
        {
            "quantity": 0,
            "average_price": 0,
        },
    )

    old_quantity = position["quantity"]

    new_quantity = (
        old_quantity + quantity
    )

    if new_quantity > 0:

        position["average_price"] = (
            (
                old_quantity
                * position["average_price"]
            )
            + cost
        ) / new_quantity

    position["quantity"] = new_quantity

    account["orders"].append(
        {
            "side": "BUY",
            "symbol": symbol.upper(),
            "quantity": quantity,
            "price": price,
            "time": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    save_paper_account(account)

    return account


def paper_sell(
    symbol: str,
    quantity: int,
    price: float,
):

    if quantity <= 0 or price <= 0:
        raise ValueError(
            "Quantity and price must be positive."
        )

    account = get_paper_account()

    symbol = symbol.upper()

    positions = account.setdefault(
        "positions",
        {},
    )

    position = positions.get(symbol)

    if not position:
        raise ValueError(
            "No paper position exists."
        )

    if position["quantity"] < quantity:
        raise ValueError(
            "Not enough paper shares."
        )

    account["cash"] += (
        quantity * price
    )

    position["quantity"] -= quantity

    if position["quantity"] == 0:
        del positions[symbol]

    account["orders"].append(
        {
            "side": "SELL",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "time": datetime.now(
                timezone.utc
            ).isoformat(),
        }
    )

    save_paper_account(account)

    return account


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are AHS AI V2.

You are a Burmese/English AI assistant.

LANGUAGE:

- Understand Burmese naturally.
- Speak Burmese clearly and naturally.
- Understand English.
- Translate Burmese <-> English.
- Understand mixed Burmese and English.

GENERAL:

- Answer directly and accurately.
- Do not pretend to perform actions that were not performed.
- Never claim a file was changed unless a real file operation happened.
- Explain uncertainty when information is unavailable.

CODING:

You can:
- Write code.
- Explain code.
- Debug code.
- Review code.
- Design software.
- Suggest improvements.
- Analyze errors.

SECURITY:

The Main Code is protected.

Never automatically:
- Delete main.py.
- Replace main.py.
- Expose API keys.
- Expose passwords.
- Expose tokens.
- Expose secrets.
- Modify protected files.

Critical changes require Owner approval.

SELF-IMPROVEMENT:

You may:
- Analyze problems.
- Suggest improvements.
- Create improvement proposals.
- Design safer code.
- Test ideas in safe environments.

You must NOT automatically modify protected Main Code.

STOCKS:

You can explain:
- Stocks.
- Companies.
- Market concepts.
- Risk management.
- Technical-analysis concepts.
- Fundamental-analysis concepts.
- Paper trading.

Do not pretend to have live market data unless a real
market-data source has been connected.

Real-money trading must require explicit Owner confirmation.

PAPER TRADING:

Paper trading uses simulated money only.

Never describe paper trades as real trades.

The Owner remains in control of protected actions.
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
        "ကျွန်တော် AHS AI V2 ပါ။\n"
        "မြန်မာ / English နားလည်ပါတယ်။\n"
        "Coding၊ ဘာသာပြန်၊ AI အကူအညီနဲ့ "
        "Stock/Paper Trading အကြောင်းတွေ "
        "ကူညီပေးနိုင်ပါတယ်။\n\n"
        "Main Code နဲ့ ငွေအစစ်ဆိုင်ရာ "
        "လုပ်ဆောင်ချက်တွေကို Owner ခွင့်ပြုချက်မရှိဘဲ "
        "မလုပ်ပါ။"
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
        "AHS AI V2 started."
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown():

    if telegram_app:

        await telegram_app.stop()

        await telegram_app.shutdown()


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post("/webhook")
async def telegram_webhook(
    request: Request,
):

    if not telegram_app:

        return JSONResponse(
            status_code=503,
            content={
                "status":
                "telegram_not_configured"
            },
        )

    try:

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

    except Exception as error:

        logger.exception(
            "Webhook error: %s",
            error,
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Webhook failed",
            },
        )


# ============================================================
# WEBSITE / API
# ============================================================

@app.post("/api/chat")
async def website_chat(
    request: Request,
):

    try:

        data = await request.json()

    except Exception:

        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Invalid JSON",
            },
        )

    user_text = str(
        data.get(
            "message",
            "",
        )
    ).strip()

    if not user_text:

        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message":
                    "message is required",
            },
        )

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
            "version": APP_VERSION,
        }

    except Exception as error:

        logger.exception(
            "Website AI error: %s",
            error,
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "AI request failed",
            },
        )


# ============================================================
# PAPER TRADING API
# ============================================================

@app.get("/api/paper/account")
async def paper_account():

    return {
        "status": "ok",
        "mode": "paper",
        "account": get_paper_account(),
    }


@app.post("/api/paper/buy")
async def paper_buy_api(
    request: Request,
):

    try:

        data = await request.json()

        symbol = str(
            data.get(
                "symbol",
                "",
            )
        ).strip()

        quantity = int(
            data.get(
                "quantity",
                0,
            )
        )

        price = float(
            data.get(
                "price",
                0,
            )
        )

        account = paper_buy(
            symbol,
            quantity,
            price,
        )

        return {
            "status": "ok",
            "mode": "paper",
            "account": account,
        }

    except Exception as error:

        logger.exception(
            "Paper buy error: %s",
            error,
        )

        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": str(error),
            },
        )


@app.post("/api/paper/sell")
async def paper_sell_api(
    request: Request,
):

    try:

        data = await request.json()

        symbol = str(
            data.get(
                "symbol",
                "",
            )
        ).strip()

        quantity = int(
            data.get(
                "quantity",
                0,
            )
        )

        price = float(
            data.get(
                "price",
                0,
            )
        )

        account = paper_sell(
            symbol,
            quantity,
            price,
        )

        return {
            "status": "ok",
            "mode": "paper",
            "account": account,
        }

    except Exception as error:

        logger.exception(
            "Paper sell error: %s",
            error,
        )

        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": str(error),
            },
        )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "running",
        "version": APP_VERSION,
        "ai": bool(GROQ_API_KEY),
        "telegram": bool(TELEGRAM_TOKEN),
        "memory": True,
        "self_improvement": True,
        "main_code_protected": True,
        "stock_analysis": True,
        "paper_trading": True,
        "real_trading": False,
    }


# ============================================================
# HOME
# ============================================================

@app.get("/")
async def home():

    return {
        "name": "AHS AI",
        "status": "running",
        "version": APP_VERSION,
        "features": [
            "Burmese",
            "English",
            "Translation",
            "Coding",
            "Memory",
            "Security",
            "Self-improvement proposals",
            "Stock foundation",
            "Paper trading",
        ],
    } 
