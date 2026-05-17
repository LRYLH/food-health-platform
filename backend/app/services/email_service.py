from email.message import EmailMessage
import smtplib

from ..core.config import settings


def send_verification_email(email: str, code: str) -> None:
    missing = [
        name
        for name, value in {
            "SMTP_HOST": settings.smtp_host,
            "SMTP_FROM_EMAIL": settings.smtp_from_email,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing SMTP configuration: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = "Food Health Platform verification code"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                "Your Food Health Platform verification code is:",
                "",
                code,
                "",
                f"This code expires in {settings.email_code_expire_minutes} minutes.",
                "If you did not request this code, ignore this email.",
            ]
        )
    )

    if settings.smtp_use_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
