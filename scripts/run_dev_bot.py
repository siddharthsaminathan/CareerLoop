#!/usr/bin/env python
import os
import sys
import time
import logging
from pathlib import Path

# Force UTF-8 logging/output
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Setup paths to ensure careerloop is importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from careerloop.transport.telegram import TelegramAdapter
from careerloop.session.session_store import SessionStore
from careerloop.session.user_registry import UserRegistry
from careerloop.session.message_router import MessageRouter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("careerloop.dev_bot")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN is not defined in your .env file!")
        logger.info("Please create a bot via Telegram's @BotFather, get the token, and add it to your .env file.")
        sys.exit(1)

    logger.info("🔌 Initializing CareerLoop State Routing System...")
    
    # Instantiate modules
    transport = TelegramAdapter(token=token)
    session_store = SessionStore()
    registry = UserRegistry()
    router = MessageRouter(transport, session_store, registry)

    logger.info("🤖 CareerLoop Dev Bot is ready!")
    logger.info("👉 Open your Telegram app, search for your Bot, and send /start to begin onboarding.")
    logger.info("Press Ctrl+C to terminate this process.")
    
    # Active Polling logic
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            payload = {"timeout": 30, "limit": 100}
            if offset:
                payload["offset"] = offset

            # Poll update payload from Telegram
            res = requests_post_updates(url, payload)
            if not res or "result" not in res:
                time.sleep(2)
                continue

            updates = res["result"]
            for update in updates:
                update_id = update["update_id"]
                offset = update_id + 1
                
                # Parse and Route message
                logger.info(f"📥 Received Update ID {update_id}")
                incoming = transport.parse_webhook(update)
                if incoming:
                    # Log state before routing
                    sess_before = session_store.get_session(incoming.user_id)
                    logger.info(f"👤 User: {incoming.user_id} | State Before: {sess_before.state.value}")
                    
                    # Dispatch to State router
                    router.route(incoming)
                    
                    # Log state after routing
                    sess_after = session_store.get_session(incoming.user_id)
                    logger.info(f"👤 User: {incoming.user_id} | State After: {sess_after.state.value}")

        except KeyboardInterrupt:
            logger.info("\n🛑 Dev Bot process terminated by user. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in polling loop: {e}")
            time.sleep(5)

def requests_post_updates(url: str, payload: dict) -> Optional[dict]:
    import requests
    try:
        response = requests.post(url, json=payload, timeout=35)
        if response.status_code == 200:
            return response.json()
        logger.error(f"Telegram API getUpdates error: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        logger.error(f"Failed to poll getUpdates: {e}")
        return None

if __name__ == "__main__":
    main()
