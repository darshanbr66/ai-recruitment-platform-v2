import httpx

from app.integrations.email.base import EmailError, EmailProvider

_RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailProvider(EmailProvider):
    """Real integration against Resend's REST API — no SDK dependency, a
    plain authenticated POST (see README for the required env vars:
    `RESEND_API_KEY`, `EMAIL_FROM`)."""

    def __init__(self, *, api_key: str, from_email: str) -> None:
        self._api_key = api_key
        self._from_email = from_email

    async def send(self, *, to: str, subject: str, html: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    _RESEND_API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "from": self._from_email,
                        "to": [to],
                        "subject": subject,
                        "html": html,
                    },
                )
            except httpx.HTTPError as exc:
                raise EmailError(f"Could not reach the email provider: {exc}") from exc

        if response.status_code >= 400:
            raise EmailError(
                f"Email provider rejected the request ({response.status_code}): {response.text}"
            )
