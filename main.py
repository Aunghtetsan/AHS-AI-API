import os
import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from groq import Groq


# ============================================================
# AHS AI AGENT — PHASE 1
# Foundation + Guardrails + Owner Security
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("ahs_ai")

app = FastAPI(title="AHS AI Agent")


# ============================================================
# ENVIRONMENT / SECRETS
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# OWNER VERIFICATION KEY (Hard-coded as requested)
OWNER_VERIFICATION_KEY = "AHS_SECRET_2065"

EMERGENCY_OVERRIDE_KEY = os.getenv(
    "EMERGENCY_OVERRIDE_KEY"
)

SESSION_MINUTES = int(
    os.getenv("OWNER_SESSION_MINUTES", "60")
)

PROTECTED_FILES = {
    item.strip()
    for item in os.getenv(
        "PROTECTED_FILES",
        "main.py",
    ).split(",")
    if item.strip()
}


# ============================================================
# CONFIGURATION CHECK
# ============================================================

def get_missing_configuration():
    required = {
        "GROQ_API_KEY": GROQ_API_KEY,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "OWNER_VERIFICATION_KEY": OWNER_VERIFICATION_KEY,
    }

    return [
        name
        for name, value in required.items()
        if not value
    ]


# ============================================================
# GROQ
# ============================================================

groq_client: Optional[Groq] = None

if GROQ_API_KEY:
    groq_client = Groq(
        api_key=GROQ_API_KEY
    )


# ============================================================
# TELEGRAM APPLICATION
# ============================================================

telegram_app = (
    Application
    .builder()
    .token(TELEGRAM_TOKEN)
    .updater(None)
    .build()
)


# ============================================================
# OWNER SESSION
# ============================================================

owner_sessions: Dict[int, datetime] = {}


def create_owner_session(user_id: int):
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=SESSION_MINUTES)
    )

    owner_sessions[user_id] = expires_at

    return expires_at


def is_owner_session_active(user_id: int) -> bool:

    expires_at = owner_sessions.get(user_id)

    if not expires_at:
        return False

    now = datetime.now(timezone.utc)

    if now >= expires_at:
        owner_sessions.pop(
            user_id,
            None,
        )
        return False

    return True


def logout_owner(user_id: int):
    owner_sessions.pop(
        user_id,
        None,
    )


# ============================================================
# ACTION CLASSIFICATION / GUARDRAILS
# ============================================================

CRITICAL_KEYWORDS = {
    "delete",
    "destroy",
    "merge",
    "deploy",
    "production",
    "wallet",
    "payment",
    "money",
    "withdraw",
    "transfer",
    "trading",
    "buy",
    "sell",
    "secret",
    "api key",
    "token",
    "password",
    "owner",
    "permission",
    "main.py",
    "security",
    "guardrails",
    "recovery",
}


def contains_critical_action(text: str) -> bool:

    normalized = text.lower()

    return any(
        keyword in normalized
        for keyword in CRITICAL_KEYWORDS
    )


def is_protected_file(path: str) -> bool:

    if not path:
        return False

    normalized = (
        path.strip()
        .lstrip("/")
    )

    if normalized in PROTECTED_FILES:
        return True

    dangerous_paths = (
        ".env",
        ".git/",
        ".git\\",
        "credentials",
        "secrets",
    )

    lower_path = normalized.lower()

    return any(
        item in lower_path
        for item in dangerous_paths
    )


# ============================================================
# SECRET COMPARISON
# ============================================================

def verify_secret(
    supplied: str,
    expected: Optional[str],
) -> bool:

    if not supplied or not expected:
        return False

    return secrets.compare_digest(
        supplied,
        expected,
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
        "မင်္ဂလာပါ။ AHS AI Agent မှ ကြိုဆိုပါတယ်။\n\n"
        "🟢 ပုံမှန်အလုပ်များ — Owner verification မလိုပါ။\n"
        "🔐 Protected action များအတွက် — Owner verification လိုပါမယ်။\n\n"
        "/unlock <Owner Key> — Owner session ဖွင့်ရန်\n"
        "/status — Session အခြေအနေကြည့်ရန်\n"
        "/logout — Owner session ပိတ်ရန်"
    )


# ============================================================
# OWNER UNLOCK
# ============================================================

async def unlock_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user_id = update.effective_user.id

    if not context.args:

        await update.message.reply_text(
            "🔐 Owner verification လုပ်ရန်\n\n"
            "/unlock <Owner Key>"
        )

        return

    supplied_key = " ".join(
        context.args
    )

    if not verify_secret(
        supplied_key,
        OWNER_VERIFICATION_KEY,
    ):

        logger.warning(
            "Failed owner verification: user_id=%s",
            user_id,
        )

        await update.message.reply_text(
            "❌ Owner verification မအောင်မြင်ပါ။"
        )

        return

    expires_at = create_owner_session(
        user_id
    )

    logger.info(
        "Owner session created: user_id=%s",
        user_id,
    )

    await update.message.reply_text(
        "✅ Owner verification အောင်မြင်ပါပြီ။\n\n"
        f"🕐 Session: {SESSION_MINUTES} မိနစ်\n"
        "🟢 Routine tasks — ပုံမှန်လုပ်နိုင်ပါတယ်။\n"
        "🔴 Critical actions — ထပ်မံအတည်ပြုရပါမယ်။\n\n"
        f"Expires: "
        f"{expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )


# ============================================================
# /logout
# ============================================================

async def logout_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user_id = update.effective_user.id

    logout_owner(user_id)

    await update.message.reply_text(
        "🔒 Owner session ပိတ်လိုက်ပါပြီ။"
    )


# ============================================================
# /status
# ============================================================

async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user_id = update.effective_user.id

    if is_owner_session_active(user_id):

        expires_at = owner_sessions[user_id]

        await update.message.reply_text(
            "🟢 Owner session ACTIVE\n"
            f"Expires: "
            f"{expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )

    else:

        await update.message.reply_text(
            "⚪ Owner session မရှိပါ။"
        )


# ============================================================
# AI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are AHS AI Agent.

You are operating in Phase 1.

MAIN PRINCIPLES:

1. Help users naturally.
2. Routine tasks should be handled freely.
3. Do not unnecessarily ask for Owner verification.
4. Protect Main Code and Security boundaries.
5. Never expose secrets, API keys, passwords or tokens.
6. Never pretend that a file was changed if no file tool
   actually changed it.
7. Prefer small, reversible changes.
8. Explain important changes clearly.
9. Keep the Owner in control of critical actions.

ACCESS LEVELS:

GREEN — Routine:
- General conversation
- Questions
- Code analysis
- Reading logs
- Cache management
- Testing
- Documentation
- Safe non-critical development

No Owner verification required.

YELLOW — Controlled:
- Large refactoring
- Dependency changes
- Architecture changes
- Large project modifications

Explain the plan before execution.

RED — Protected:
- Main/protected code
- Security system
- Owner permissions
- Recovery system
- Secrets
- API keys
- Deployment
- Destructive operations
- Money
- Wallets
- Real-money trading

These require Owner verification and explicit approval.

IMPORTANT:

Do not treat every coding request as a protected action.

Only protect actions that actually cross a critical
security or ownership boundary.

The goal is to provide maximum useful autonomy while
keeping critical controls under the Owner.
"""


# ============================================================
# GROQ CALL
# ============================================================

def ask_groq_sync(
    user_text: str,
) -> str:

    if not groq_client:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    completion = (
        groq_client
        .chat
        .completions
        .create(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=1200,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_text,
                },
            ],
        )
    )

    return (
        completion
        .choices[0]
        .message
        .content
        .strip()
    )


async def ask_groq(
    user_text: str,
) -> str:

    return await asyncio.to_thread(
        ask_groq_sync,
        user_text,
    )


# ============================================================
# MESSAGE HANDLER
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    owner_active = (
        is_owner_session_active(user_id)
    )

    critical = contains_critical_action(
        user_text
    )

    # --------------------------------------------------------
    # PROTECTED ACTION
    # --------------------------------------------------------

    if critical and not owner_active:

        await update.message.reply_text(
            "🔒 ဒီလုပ်ဆောင်ချက်က Protected Action ဖြစ်နိုင်ပါတယ်။\n\n"
            "Owner verification မရှိသေးပါ။\n"
            "ပထမဆုံး Owner session ဖွင့်ပါ။\n\n"
            "/unlock <Owner Key>"
        )

        logger.warning(
            "Blocked protected action: user_id=%s",
            user_id,
        )

        return

    # --------------------------------------------------------
    # NORMAL AI REQUEST
    # --------------------------------------------------------

    try:

        response_text = await ask_groq(
            user_text
        )

        max_message_length = 4000

        for start in range(
            0,
            len(response_text),
            max_message_length,
        ):

            chunk = response_text[
                start:start + max_message_length
            ]

            await update.message.reply_text(
                chunk
            )

        logger.info(
            "Request handled: "
            "user_id=%s owner=%s critical=%s",
            user_id,
            owner_active,
            critical,
        )

    except Exception as e:
     logger.exception(
        "AI request failed: user_id=%s",
        user_id,
    )

      await update.message.reply_text(
        f"❌ AI Error:\n{type(e).__name__}: {str(e)[:1500]}"
    )
    


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    missing = get_missing_configuration()

    if missing:

        logger.error(
            "Missing configuration: %s",
            ", ".join(missing),
        )

    await telegram_app.initialize()

    if WEBHOOK_URL:

        webhook_url = (
            f"{WEBHOOK_URL.rstrip('/')}/webhook"
        )

        await telegram_app.bot.set_webhook(
            url=webhook_url
        )

        logger.info(
            "Telegram webhook configured."
        )

    logger.info(
        "AHS AI Agent Phase 1 started."
    )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post("/webhook")
async def telegram_webhook(
    request: Request,
):

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
# HEALTH CHECK
# ============================================================

@app.get("/")
async def root():

    missing = get_missing_configuration()

    return {
        "status": "AHS AI Agent is running",
        "phase": "Phase 1",
        "telegram": bool(TELEGRAM_TOKEN),
        "groq": bool(GROQ_API_KEY),
        "owner_security": bool(
            OWNER_VERIFICATION_KEY
        ),
        "protected_files": list(
            PROTECTED_FILES
        ),
        "configuration_ok": not missing,
    }


# ============================================================
# TELEGRAM HANDLERS
# ============================================================

telegram_app.add_handler(
    CommandHandler(
        "start",
        start_command,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "unlock",
        unlock_command,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "logout",
        logout_command,
    )
)

telegram_app.add_handler(
    CommandHandler(
        "status",
        status_command,
    )
)

telegram_app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message,
    )
    )
    
