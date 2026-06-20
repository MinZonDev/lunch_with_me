"""Email notifications via Gmail SMTP."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _send(to: str | list[str], subject: str, html_body: str):
    if not settings.smtp_user or not settings.smtp_password:
        print(f"[Email] SMTP not configured — skipping send to {to}")
        return

    recipients = [to] if isinstance(to, str) else to
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_user
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, recipients, msg.as_string())
        print(f"[Email] Sent '{subject}' to {recipients}")
    except Exception as e:
        print(f"[Email] Failed to send to {recipients}: {e}")


def send_order_reminder(order_date: str, deadline_str: str, member_name: str, email: str, frontend_url: str):
    subject = f"🍚 Nhắc chọn món - {order_date}"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42">🍱 Lunch With Me</h2>
      <p>Xin chào <strong>{member_name}</strong>,</p>
      <p>Order hôm nay <strong>{order_date}</strong> sẽ đóng lúc <strong style="color:#ff8c42">{deadline_str}</strong>.</p>
      <p>Bạn chưa chọn món! Vào chọn ngay nhé:</p>
      <a href="{frontend_url}" style="display:inline-block;background:#ff8c42;color:#0a0a0f;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;margin-top:8px">
        Chọn Món Ngay →
      </a>
      <p style="color:#6b6b80;font-size:12px;margin-top:24px">Bạn nhận mail này vì bạn là thành viên của nhóm cơm trưa.</p>
    </div>
    """
    _send(email, subject, html)


def send_monthly_statement(month: int, year: int, member_name: str, email: str,
                           days_eaten: int, total_cost: int, balance: int):
    subject = f"📊 Sao kê tháng {month}/{year} - Lunch With Me"
    status_color = "#06d6a0" if balance >= 0 else "#ff6b6b"
    status_text = f"Còn dư <strong style='color:{status_color}'>{balance}k</strong>" if balance >= 0 \
        else f"Đang nợ <strong style='color:{status_color}'>{abs(balance)}k</strong>"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42">📊 Sao Kê Tháng {month}/{year}</h2>
      <p>Xin chào <strong>{member_name}</strong>,</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0">
        <tr><td style="padding:8px 0;color:#a0a0b8">Số ngày ăn</td><td style="text-align:right;font-weight:700">{days_eaten} ngày</td></tr>
        <tr><td style="padding:8px 0;color:#a0a0b8">Tổng chi phí</td><td style="text-align:right;font-weight:700">{total_cost}k</td></tr>
        <tr style="border-top:1px solid rgba(255,255,255,0.1)">
          <td style="padding:8px 0;color:#a0a0b8">Số dư hiện tại</td>
          <td style="text-align:right;font-weight:700">{status_text}</td>
        </tr>
      </table>
      {'<p style="color:#ff6b6b;background:rgba(255,107,107,0.1);padding:12px;border-radius:8px">⚠️ Bạn đang nợ tiền ăn. Vui lòng nạp thêm tiền!</p>' if balance < 0 else ''}
      <p style="color:#6b6b80;font-size:12px;margin-top:24px">Sao kê tự động từ hệ thống Lunch With Me.</p>
    </div>
    """
    _send(email, subject, html)


def send_reset_password(full_name: str, email: str, reset_url: str):
    subject = "🔑 Đặt lại mật khẩu - Lunch With Me"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42">🍱 Lunch With Me</h2>
      <p>Xin chào <strong>{full_name}</strong>,</p>
      <p>Bạn vừa yêu cầu đặt lại mật khẩu. Bấm nút bên dưới để tiếp tục:</p>
      <a href="{reset_url}" style="display:inline-block;background:#ff8c42;color:#0a0a0f;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;margin:16px 0">
        Đặt Lại Mật Khẩu →
      </a>
      <p style="color:#a0a0b8;font-size:0.85rem">Link có hiệu lực trong <strong>1 giờ</strong>. Nếu bạn không yêu cầu, hãy bỏ qua email này.</p>
      <p style="color:#6b6b80;font-size:12px;margin-top:24px">Lunch With Me — Hệ thống đặt cơm nhóm</p>
    </div>
    """
    _send(email, subject, html)


def send_low_balance_alert(member_name: str, email: str, balance: int):
    subject = "⚠️ Số dư sắp hết - Lunch With Me"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42">⚠️ Số Dư Sắp Hết</h2>
      <p>Xin chào <strong>{member_name}</strong>,</p>
      <p>Số dư của bạn còn <strong style="color:#ffe66d">{balance}k</strong>, sắp không đủ để ăn.</p>
      <p>Hãy nạp thêm tiền để tránh bị gián đoạn nhé!</p>
      <p style="color:#6b6b80;font-size:12px;margin-top:24px">Thông báo tự động từ hệ thống Lunch With Me.</p>
    </div>
    """
    _send(email, subject, html)
