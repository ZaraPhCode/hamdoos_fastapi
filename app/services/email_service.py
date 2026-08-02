"""Email service — Outlook SMTP via aiosmtplib.

Mirrors EmailSender.cs from the .NET domain:
- SendConfrimOrderAsync
- SendViewEmailAsync
- SendEmailAsync
- SendNotifyEmailAsync
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger

from app.config.settings import settings


class EmailSender:
    def __init__(self):
        self.host = settings.EMAIL_HOST
        self.port = settings.EMAIL_PORT
        self.username = settings.EMAIL_USERNAME
        self.password = settings.EMAIL_PASSWORD
        self.from_addr = settings.EMAIL_FROM
        self.use_tls = settings.EMAIL_USE_TLS

    async def _send(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
    ) -> bool:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_addr
        msg["To"] = to
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        all_recipients = [to] + (cc or []) + (bcc or [])

        try:
            smtp = aiosmtplib.SMTP(hostname=self.host, port=self.port, use_tls=self.use_tls)
            await smtp.connect()
            await smtp.login(self.username, self.password)
            await smtp.send_message(msg)
            await smtp.quit()
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email send failed to {to}: {e}")
            return False

    async def send_verification_code(self, to: str, code: str, full_name: str = "") -> bool:
        subject = "کد تأیید - آشا شاپ"
        body = f"""
        <html><body dir="rtl">
        <h2>کد تأیید شما</h2>
        <p style="font-size: 24px; font-weight: bold; color: #4F46E5;">{code}</p>
        <p>این کد تا ۵ دقیقه معتبر است.</p>
        <hr><p style="color: #888;">آشا شاپ</p>
        </body></html>
        """
        return await self._send(to, subject, body)

    async def send_order_confirmation(
        self,
        to: str,
        full_name: str,
        reference_code: int,
        total_price: float,
        order_date: datetime,
    ) -> bool:
        subject = f"تأیید سفارش #{reference_code} - آشا شاپ"
        body = f"""
        <html><body dir="rtl">
        <h2>سفارش شما ثبت شد</h2>
        <p>کاربر گرامی {full_name}، سفارش شما با موفقیت ثبت شد.</p>
        <table style="border-collapse: collapse; width: 100%; max-width: 400px;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;">شماره سفارش</td>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{reference_code}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;">مبلغ قابل پرداخت</td>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{total_price:,.0f} تومان</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;">تاریخ</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{order_date.strftime("%Y/%m/%d %H:%M")}</td></tr>
        </table>
        <hr><p style="color: #888;">آشا شاپ</p>
        </body></html>
        """
        return await self._send(to, subject, body)

    async def send_payment_confirmation(
        self,
        to: str,
        full_name: str,
        reference_code: int,
        ref_id: int,
        amount: float,
    ) -> bool:
        subject = f"پرداخت سفارش #{reference_code} تأیید شد - آشا شاپ"
        body = f"""
        <html><body dir="rtl">
        <h2>پرداخت با موفقیت انجام شد</h2>
        <p>کاربر گرامی {full_name}، پرداخت سفارش شما تأیید شد.</p>
        <table style="border-collapse: collapse; width: 100%; max-width: 400px;">
            <tr><td style="padding: 8px; border: 1px solid #ddd;">شماره سفارش</td>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{reference_code}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;">مبلغ</td>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{amount:,.0f} تومان</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #ddd;">کد پیگیری</td>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{ref_id}</td></tr>
        </table>
        <hr><p style="color: #888;">آشا شاپ</p>
        </body></html>
        """
        return await self._send(to, subject, body)

    async def send_notify_product(
        self,
        to: str,
        full_name: str,
        product_name: str,
        product_url: str = "",
    ) -> bool:
        subject = "محصول مورد نظر شما موجود شد - آشا شاپ"
        body = f"""
        <html><body dir="rtl">
        <h2>محصول موجود شد</h2>
        <p>کاربر گرامی {full_name}، محصول "{product_name}" موجود شد.</p>
        {"<p><a href='" + product_url + "'>مشاهده محصول</a></p>" if product_url else ""}
        <hr><p style="color: #888;">آشا شاپ</p>
        </body></html>
        """
        return await self._send(to, subject, body)

    async def send_password_reset(self, to: str, code: str) -> bool:
        subject = "بازیابی رمز عبور - آشا شاپ"
        body = f"""
        <html><body dir="rtl">
        <h2>بازیابی رمز عبور</h2>
        <p>کد بازیابی رمز عبور شما:</p>
        <p style="font-size: 24px; font-weight: bold; color: #4F46E5;">{code}</p>
        <p>این کد تا ۵ دقیقه معتبر است.</p>
        <hr><p style="color: #888;">آشا شاپ</p>
        </body></html>
        """
        return await self._send(to, subject, body)