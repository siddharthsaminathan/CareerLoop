import os
import logging
import requests
from typing import List, Dict, Any, Optional
from careerloop.transport.base import TransportAdapter, IncomingMessage

logger = logging.getLogger("careerloop.transport.telegram")

class TelegramAdapter(TransportAdapter):
    def __init__(self, token: Optional[str] = None):
        # Fall back to environment variable if token is not passed explicitly
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN is not configured in the environment variables.")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_text(self, user_id: str, text: str) -> bool:
        if not self.token:
            logger.error("Cannot send text: telegram token is missing.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram text: {e}")
            return False

    def send_buttons(self, user_id: str, text: str, buttons: List[Dict[str, str]]) -> bool:
        if not self.token:
            logger.error("Cannot send buttons: telegram token is missing.")
            return False

        url = f"{self.base_url}/sendMessage"
        
        # Build the inline keyboard markup
        # Inline buttons format: [[{"text": "Btn 1", "callback_data": "1"}, {"text": "Btn 2", "callback_data": "2"}]]
        keyboard = []
        for btn in buttons:
            keyboard.append({
                "text": btn["text"],
                "callback_data": btn["callback_data"]
            })
            
        payload = {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [keyboard]
            }
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            logger.error(f"Telegram API button error: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram buttons: {e}")
            return False

    def send_document(self, user_id: str, file_path: str, caption: Optional[str] = None) -> bool:
        if not self.token:
            logger.error("Cannot send document: telegram token is missing.")
            return False

        if not os.path.exists(file_path):
            logger.error(f"Cannot send document: file not found at {file_path}")
            return False

        url = f"{self.base_url}/sendDocument"
        data = {
            "chat_id": user_id
        }
        if caption:
            data["caption"] = caption
            data["parse_mode"] = "Markdown"

        try:
            with open(file_path, "rb") as doc_file:
                files = {
                    "document": (os.path.basename(file_path), doc_file)
                }
                response = requests.post(url, data=data, files=files, timeout=30)
                if response.status_code == 200:
                    return True
                logger.error(f"Telegram API document error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Telegram document: {e}")
            return False

    def parse_webhook(self, payload: Dict[str, Any]) -> Optional[IncomingMessage]:
        """
        Parses raw Telegram updates.
        Supports standard text messages, document uploads, and inline keyboard callbacks.
        """
        try:
            # 1. Handle Inline Button Callbacks
            if "callback_query" in payload:
                cb = payload["callback_query"]
                user_id = str(cb["from"]["id"])
                callback_data = cb.get("data")
                return IncomingMessage(
                    user_id=user_id,
                    callback_data=callback_data
                )

            # 2. Handle Direct Messages
            if "message" in payload:
                msg = payload["message"]
                user_id = str(msg["chat"]["id"])
                
                # Case A: Document upload (e.g. CV PDF)
                if "document" in msg:
                    doc = msg["document"]
                    file_id = doc["file_id"]
                    file_name = doc.get("file_name", "document")
                    mime_type = doc.get("mime_type")
                    
                    # Fetch file path from Telegram to download it locally
                    local_path = self._download_telegram_file(file_id, file_name)
                    return IncomingMessage(
                        user_id=user_id,
                        document_path=local_path,
                        document_mime=mime_type,
                        text=msg.get("caption") # Sometimes user adds text caption with document
                    )

                # Case B: Standard text message
                text = msg.get("text")
                return IncomingMessage(
                    user_id=user_id,
                    text=text
                )

            return None
        except Exception as e:
            logger.error(f"Failed to parse Telegram webhook payload: {e}")
            return None

    def _download_telegram_file(self, file_id: str, file_name: str) -> Optional[str]:
        """Downloads a file uploaded by the user via Telegram Bot and returns its local path."""
        try:
            # Step 1: Get the file path via getFile method
            get_file_url = f"{self.base_url}/getFile"
            res = requests.post(get_file_url, json={"file_id": file_id}, timeout=10)
            if res.status_code != 200:
                logger.error(f"Telegram getFile failed: {res.text}")
                return None
            
            file_path = res.json()["result"]["file_path"]
            
            # Step 2: Download the file
            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            file_res = requests.get(download_url, timeout=30)
            if file_res.status_code != 200:
                logger.error(f"Telegram file download failed: {file_res.status_code}")
                return None

            # Save in workspace-local directory: data/raw_cvs/
            save_dir = "/Users/siddharthsaminathan/projects/CareerLoop/data/raw_cvs"
            os.makedirs(save_dir, exist_ok=True)
            
            # Sanitise file name and save
            local_file_path = os.path.join(save_dir, file_name)
            with open(local_file_path, "wb") as f:
                f.write(file_res.content)
            
            logger.info(f"Successfully downloaded file to: {local_file_path}")
            return local_file_path
        except Exception as e:
            logger.error(f"Failed to download Telegram file: {e}")
            return None
