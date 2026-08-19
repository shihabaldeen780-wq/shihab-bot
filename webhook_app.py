from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update

from bot import build_app

logger = logging.getLogger("shihab.webhook")
PORT = int(os.getenv("PORT", "8000"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
WEBHOOK_PATH = f"/telegram/{WEBHOOK_SECRET}" if WEBHOOK_SECRET else "/telegram/webhook"
application = build_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await application.initialize()
    await application.start()
    if not PUBLIC_URL:
        logger.warning("PUBLIC_URL is empty; webhook registration is skipped")
    else:
        await application.bot.set_webhook(
            url=f"{PUBLIC_URL}{WEBHOOK_PATH}",
            secret_token=WEBHOOK_SECRET or None,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )
        logger.info("Webhook registered at %s", f"{PUBLIC_URL}{WEBHOOK_PATH}")
    yield
    if PUBLIC_URL:
        try:
            await application.bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            logger.exception("Could not remove webhook during shutdown")
    await application.stop()
    await application.shutdown()


app = FastAPI(title="Shihab Telegram Webhook", lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "shihab", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> dict[str, bool]:
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="invalid webhook secret")
    try:
        payload = await request.json()
        update = Update.de_json(payload, application.bot)
        await application.process_update(update)
        return {"ok": True}
    except Exception as exc:
        logger.exception("Webhook update failed: %s", exc)
        raise HTTPException(status_code=500, detail="update processing failed") from exc
