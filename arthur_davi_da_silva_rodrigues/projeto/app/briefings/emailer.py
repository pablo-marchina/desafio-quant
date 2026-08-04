import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.settings import Settings


@dataclass(frozen=True)
class EmailDeliveryResult:
    status: str
    detail: str


class EmailNotConfiguredError(RuntimeError):
    pass


def send_markdown_report_email(
    settings: Settings,
    to_email: str,
    subject: str,
    markdown: str,
) -> EmailDeliveryResult:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailNotConfiguredError("SMTP não configurado")

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(markdown)
    message.add_attachment(
        markdown.encode("utf-8"),
        maintype="text",
        subtype="markdown",
        filename="relatorio-nvidia-startup-ai-radar.md",
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)

    return EmailDeliveryResult(status="sent", detail="Relatório enviado por e-mail.")
