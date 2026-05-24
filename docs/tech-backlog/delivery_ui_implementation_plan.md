# CareerLoop — Delivery & UI Implementation Plan
## Central Telegram Bot & Weekly Momentum Dashboard

> [!NOTE]
> **Product Thesis:** *The CLI is for debugging. The Telegram Bot is for conversation. The Dashboard is for conversion.*  
> This delivery plan maps the user-facing interfaces to our weekly momentum metrics, replacing complex terminal screens with an intuitive, chat-driven pipeline.

---

## 📡 The Conversational Shift (CLI to Telegram)

The current CLI transport is highly functional for testing but has high user friction. We will transition to a **Telegram Bot** as the central user interface:

*   **Painless Onboarding:** Instead of typing long texts in bash, the user drops their PDF resume in the Telegram chat. The bot triggers `DocumentExtractor` and parses their master profile instantly.
*   **Voice Notes & Venting:** The user can send voice notes to the bot (e.g. after a hard interview). The bot automatically transcribes the note, extracts feedback, and logs their emotional state.
*   **Instant Document Delivery:** Once an application pack is compiled, the bot delivers the PDFs (`classic-ats.pdf` and `product-engineer.pdf`) and the outreach MD file directly as downloadable attachments in the chat window.

---

## ⏰ The 7 AM IST Morning Action Brief

Every morning, the system runs the `DailyRunner` cron job, Triages crawled postings against the India Fit Engine, and sends a single **Morning Brief** at 7 AM IST:

```
☕ GOOD MORNING, SIDDHARTH!
Here is your daily strategic triage card for May 24, 2026:

──────────────────────────────────────────
🔍 Scoped: 114 jobs | 📋 Triaged: 5 active matching roles
──────────────────────────────────────────

🔥 TOP PICKS TO APPLY TODAY:

1. 🚀 AI Productivity Engineer @ Sarvam AI (Score: 73)
   • Why: Focuses on LLM optimization and multi-agent deployment.
   • Path: Route C (Hiring Manager found: Prasanth Nair).
   • Action: [Apply & Get Pack] | [Skip]

2. 📈 AI Product Engineer @ BukuWarung (Score: 68)
   • Why: Replaces manual spreadsheet workflows for small merchants.
   • Path: Route C (Engineering Manager found: Mandeep Singh).
   • Action: [Apply & Get Pack] | [Skip]

Reply with '1' or '2' to instantly generate and download your customized S8 Application Pack!
```

---

## 📊 The Weekly Momentum Dashboard ("The Money Screen")

Visualizes the ultimate tangible ROI. Sent as an automated image card or clean text dashboard every Sunday evening at 6 PM IST:

```
📈 YOUR WEEKLY CONVERSION MOMENTUM

┌───────────────────────────────────────┐
│  SUBMITTED APPLICATIONS:  [8]         │
│  RECRUITER OUTREACH DMs:  [11]        │
│  RESPONSES / REPLIES:     [3] (27%)   │
│  INTERVIEWS SCHEDULED:    [1]         │
└───────────────────────────────────────┘

🔥 WEEKLY HIGHLIGHTS:
• You bypassed 118 irrelevant body-shop listings.
• Mandeep Singh (BukuWarung) replied to your tailored S8 outreach!
• Your average response latency from recruiters dropped by 48%.

💪 Next week target: 10 applications + 15 outreach messages. Let's keep the conversion engine hot!
```

---

## 🛠️ Tele-Transport Architecture Specs

We decouple the Telegram Bot API from our core routing engine. The Telegram webhook serves as a lightweight gateway:

```python
# careerloop/transport/telegram_bot.py
import os
import requests
from fastapi import APIRouter, Request
from careerloop.transport.base import UserEvent
from careerloop.session.supervisor_graph import get_supervisor_graph

router = APIRouter()
TELEGRAM_API_URL = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}"

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    message = payload.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    document = message.get("document")

    # Map Telegram message schemas to standard UserEvent
    user_event = UserEvent(
        user_id=str(chat_id),
        raw_text=text,
        file_attachment=document.get("file_id") if document else None,
        source="telegram"
    )

    # Route event directly to our LangGraph Supervisor
    supervisor = get_supervisor_graph()
    result = await supervisor.ainvoke({
        "user_id": user_event.user_id,
        "messages": [user_event.raw_text],
        "current_state": "IDLE" # Handled dynamically by checkpointer
    }, config={"configurable": {"thread_id": user_event.user_id}})

    # Deliver output document/text back to Telegram
    assistant_response = result.get("assistant_response")
    send_telegram_message(chat_id, assistant_response)

    return {"status": "ok"}

def send_telegram_message(chat_id: int, text: str):
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })
```

---

## 📅 Roadmap Milestones (Phase 1.5 - 2.0)

*   **Milestone 1 (Gateway):** Initialize the Telegram Webhook router in FastAPI, configure bot credentials in `.env`, and test raw text exchange.
*   **Milestone 2 (Onboarding flow):** Wire the Telegram document receiver to our `DocumentExtractor` so dropping a `.pdf`/`.md` resume instantly initiates S5 User Onboarding.
*   **Milestone 3 (Action Brief delivery):** Implement the `DailyRunner` scheduler to format and push the 7 AM morning brief cards via Telegram API.
*   **Milestone 4 (Weekly Dashboard card):** Integrate `matplotlib` or a simple HTML-to-image service to render and deliver the Momentum Dashboard card every Sunday.
