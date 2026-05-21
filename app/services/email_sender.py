import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailSender:

    @staticmethod
    def send_email_with_attachment(
        to_email: str,
        subject: str,
        body_html: str,
        attachment_bytes: bytes | None = None,
        attachment_name: str = "pagos_sin_factura.xlsx",
        settings=None,
    ) -> bool:
        if not settings:
            from app.config import settings as app_settings
            settings = app_settings

        if not settings.smtp_host or not settings.smtp_user:
            logger.error("SMTP no configurado")
            return False

        try:
            msg = MIMEMultipart("mixed")
            msg["From"] = settings.email_from or settings.smtp_user
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(body_html, "html"))

            if attachment_bytes:
                part = MIMEBase(
                    "application",
                    "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                part.set_payload(attachment_bytes)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{attachment_name}"',
                )
                msg.attach(part)

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info("Email enviado a %s", to_email)
            return True

        except Exception as e:
            logger.error("Error enviando email a %s: %s", to_email, e)
            return False
