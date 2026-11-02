import httpx
from fastapi import HTTPException, status

from app.config import get_settings

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


async def send_result(to: str, username: str, receiver: str) -> None:
    settings = get_settings()
    payload = {
        "sender": {"name": settings.email_sender_name, "email": settings.email_sender_address},
        "to": [{"email": to, "name": username}],
        "subject": "Wynik losowania prezentów",
        "htmlContent": (
            f"<p>Cześć {username}!</p><p>Wylosowałeś/aś <b>{receiver}</b>. "
            "Pomyśl o jakimś prezencie.</p>"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                BREVO_URL, json=payload, headers={"api-key": settings.brevo_api_key}
            )
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "email_failed") from None
