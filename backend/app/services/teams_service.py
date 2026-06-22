"""Microsoft Teams group notifications via Power Automate Workflow webhook.

Note: Microsoft retired the old "Incoming Webhook" connector (MessageCard format,
*.webhook.office.com). The replacement is a Power Automate "Workflow" trigger
("When a Teams webhook request is received"), whose URL looks like
https://...logic.azure.com/.../triggers/manual/paths/invoke?...

The flow expects the full Adaptive Card JSON as the request body (it forwards
the payload as-is to "Post adaptive card in a chat or channel"), so we send a
complete {$schema, type: AdaptiveCard, version, body, actions} object.
"""

import requests

from app.core.config import settings


def _post(webhook_url: str, card: dict):
    if not webhook_url:
        print("[Teams] Webhook not configured — skipping send")
        return

    try:
        resp = requests.post(webhook_url, json=card, timeout=10)
        if resp.status_code >= 300:
            print(f"[Teams] Failed to send: {resp.status_code} {resp.text}")
        else:
            print("[Teams] Sent debt reminder summary")
    except Exception as e:
        print(f"[Teams] Failed to send: {e}")


def send_debt_reminder_summary(debtors: list[dict], frontend_url: str = "", webhook_url: str = ""):
    """Gửi danh sách tổng hợp người đang nợ vào group Teams.

    debtors: list of {name, balance, email} (balance is negative, in nghìn đồng)
    """
    webhook_url = webhook_url or settings.teams_webhook_url
    if not debtors or not webhook_url:
        return

    def _vnd(amount: int) -> str:
        return f"{amount:,.0f}".replace(",", ".")

    total = sum(abs(d["balance"]) for d in debtors) * 1000

    def _debtor_line(d: dict) -> str:
        email_part = f" ({d['email']})" if d.get("email") else ""
        return f"**{d['name']}**{email_part}: -{_vnd(abs(d['balance']) * 1000)} đ"

    debtor_items = [
        {"type": "TextBlock", "text": _debtor_line(d), "wrap": True}
        for d in debtors
    ]

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "⚠️ Nhắc Nợ Tiền Cơm",
                        "wrap": True,
                        "size": "Large",
                        "weight": "Bolder",
                        "horizontalAlignment": "Center",
                    },
                    {
                        "type": "TextBlock",
                        "text": f"**{len(debtors)} người** đang nợ, tổng **{_vnd(total)} đ**",
                        "wrap": True,
                        "horizontalAlignment": "Center",
                        "color": "Attention",
                        "spacing": "Medium",
                    },
                    *debtor_items,
                ],
            },
        ],
    }

    _post(webhook_url, card)
