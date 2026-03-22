import sys
import os
from loguru import logger

# Create logs directory
os.makedirs("data/logs", exist_ok=True)

# Remove default logger
logger.remove()

# Add console logger
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Add file logger (rotating)
logger.add(
    "data/logs/trading_bot_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

# Telegram alerting (optional via interceptor or direct function call)
def send_telegram_alert(message: str):
    import httpx
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        httpx.post(url, json=payload, timeout=5.0)
    except Exception as e:
        logger.error(f"Failed to send telegram alert: {e}")

# Helper to send critical alerts
def alert(message: str):
    logger.critical(message)
    send_telegram_alert(f"🚨 ALERT: {message}")
