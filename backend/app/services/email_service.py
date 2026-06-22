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
    balance_vnd = f"{balance * 1000:,}".replace(",", ".")
    abs_balance_vnd = f"{abs(balance) * 1000:,}".replace(",", ".")
    total_cost_vnd = f"{total_cost * 1000:,}".replace(",", ".")
    status_text = f"Còn dư <strong style='color:{status_color}'>{balance_vnd} đ</strong>" if balance >= 0 \
        else f"Đang nợ <strong style='color:{status_color}'>{abs_balance_vnd} đ</strong>"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42">📊 Sao Kê Tháng {month}/{year}</h2>
      <p>Xin chào <strong>{member_name}</strong>,</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0">
        <tr><td style="padding:8px 0;color:#a0a0b8">Số ngày ăn</td><td style="text-align:right;font-weight:700">{days_eaten} ngày</td></tr>
        <tr><td style="padding:8px 0;color:#a0a0b8">Tổng chi phí</td><td style="text-align:right;font-weight:700">{total_cost_vnd} đ</td></tr>
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


def _vietqr_url(bank_id: str, account: str, account_name: str, amount: int = 0, info: str = "") -> str:
    import urllib.parse
    base = f"https://img.vietqr.io/image/{bank_id}-{account}-compact2.png"
    params = {"accountName": account_name}
    if amount > 0:
        params["amount"] = str(amount * 1000)  # amount in VND (input is k)
    if info:
        params["addInfo"] = info
    return base + "?" + urllib.parse.urlencode(params)


def send_debt_reminder(full_name: str, email: str, balance: int, frontend_url: str):
    """Nhắc thành viên nạp tiền vì đang nợ."""
    from app.core.config import settings as cfg
    transfer_info = f"{full_name} nap com"
    qr_url = _vietqr_url(cfg.bank_id, cfg.bank_account, cfg.bank_account_name, abs(balance), transfer_info)

    subject = "⚠️ Nhắc nợ tiền cơm - Lunch With Me"
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42;margin:0 0 4px">🍱 Lunch With Me</h2>
      <p style="color:#a0a0b8;font-size:13px;margin:0 0 20px">Hệ thống đặt cơm nhóm</p>

      <p>Xin chào <strong>{full_name}</strong>,</p>
      <p>Bạn hiện đang <strong style="color:#ff6b6b;font-size:1.1em">nợ {abs(balance) * 1000:,} đ</strong> tiền cơm. Vui lòng làm theo 2 bước bên dưới.</p>

      <!-- Step 1: Bank transfer -->
      <div style="background:rgba(255,140,66,0.08);border:1px solid rgba(255,140,66,0.25);border-radius:12px;padding:20px;margin:20px 0">
        <div style="font-weight:700;color:#ff8c42;font-size:15px;margin-bottom:14px">Bước 1 — Quét QR hoặc chuyển khoản</div>

        <!-- QR code centered -->
        <div style="text-align:center;margin-bottom:16px">
          <img src="{qr_url}" alt="QR chuyển khoản"
               style="width:200px;height:200px;border-radius:12px;border:4px solid #fff;background:#fff" />
          <p style="color:#a0a0b8;font-size:12px;margin:6px 0 0">Quét bằng app ngân hàng bất kỳ</p>
        </div>

        <!-- Bank details -->
        <table style="width:100%;border-collapse:collapse;font-size:14px;border-top:1px solid rgba(255,255,255,0.08);padding-top:12px">
          <tr><td style="color:#a0a0b8;padding:5px 0;width:130px">Ngân hàng</td><td style="font-weight:600">Vikki Digital Bank</td></tr>
          <tr><td style="color:#a0a0b8;padding:5px 0">Chủ tài khoản</td><td style="font-weight:600">{cfg.bank_account_name}</td></tr>
          <tr><td style="color:#a0a0b8;padding:5px 0">Số tài khoản</td><td style="font-weight:700;font-size:1.1em;letter-spacing:1.5px;color:#ffe66d">{cfg.bank_account}</td></tr>
          <tr><td style="color:#a0a0b8;padding:5px 0">Số tiền gợi ý</td><td style="font-weight:700;color:#ff8c42">{abs(balance) * 1000:,} đ</td></tr>
          <tr><td style="color:#a0a0b8;padding:5px 0">Nội dung CK</td><td style="font-weight:600">{transfer_info}</td></tr>
        </table>
      </div>

      <!-- Step 2: Create deposit request -->
      <div style="background:rgba(78,205,196,0.07);border:1px solid rgba(78,205,196,0.22);border-radius:12px;padding:20px;margin:20px 0">
        <div style="font-weight:700;color:#4ecdc4;font-size:15px;margin-bottom:10px">Bước 2 — Tạo yêu cầu nạp tiền trên app</div>
        <p style="margin:0 0 14px;font-size:14px;color:#c0c0d8">Sau khi chuyển khoản xong, vào app tạo yêu cầu nạp tiền để admin xác nhận và cộng vào số dư.</p>
        <a href="{frontend_url}/deposit"
           style="display:inline-block;background:#4ecdc4;color:#0a0a0f;padding:11px 24px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px">
          Tạo Yêu Cầu Nạp Tiền →
        </a>
      </div>

      <p style="color:#6b6b80;font-size:12px;margin-top:20px;border-top:1px solid rgba(255,255,255,0.07);padding-top:14px">
        Thông báo tự động · Lunch With Me. Nếu bạn đã nạp tiền, hãy bỏ qua email này.
      </p>
    </div>
    """
    _send(email, subject, html)


def send_account_approved(full_name: str, email: str, frontend_url: str = ""):
    subject = "✅ Tài khoản đã được duyệt - Lunch With Me"
    login_url = f"{frontend_url}/login" if frontend_url else "/login"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42">🍱 Lunch With Me</h2>
      <p>Xin chào <strong>{full_name}</strong>,</p>
      <p>Tài khoản của bạn đã được <strong style="color:#06d6a0">admin duyệt</strong>. Bạn có thể đăng nhập ngay bây giờ!</p>
      <a href="{login_url}" style="display:inline-block;background:#06d6a0;color:#0a0a0f;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;margin-top:8px">
        Đăng Nhập Ngay →
      </a>
      <p style="color:#6b6b80;font-size:12px;margin-top:24px">Lunch With Me — Hệ thống đặt cơm nhóm</p>
    </div>
    """
    _send(email, subject, html)


def send_otp_email(email: str, code: str, full_name: str = "bạn"):
    subject = "🔐 Mã OTP xác thực - Lunch With Me"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#f0f0f5;padding:32px;border-radius:16px">
      <h2 style="color:#ff8c42">🍱 Lunch With Me</h2>
      <p>Xin chào <strong>{full_name}</strong>,</p>
      <p>Đây là mã OTP để xác thực email đăng ký tài khoản của bạn:</p>
      <div style="text-align:center;margin:24px 0">
        <span style="font-size:2.4rem;font-weight:900;letter-spacing:10px;color:#ffe66d;background:rgba(255,230,109,0.1);padding:16px 24px;border-radius:12px;display:inline-block;border:1px solid rgba(255,230,109,0.25)">
          {code}
        </span>
      </div>
      <p style="color:#a0a0b8;font-size:0.875rem">
        Mã có hiệu lực trong <strong style="color:#f0f0f5">10 phút</strong>.
        Nếu bạn không thực hiện đăng ký, hãy bỏ qua email này.
      </p>
      <p style="color:#6b6b80;font-size:12px;margin-top:24px">Lunch With Me — Hệ thống đặt cơm nhóm</p>
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
      <p>Số dư của bạn còn <strong style="color:#ffe66d">{balance * 1000:,} đ</strong>, sắp không đủ để ăn.</p>
      <p>Hãy nạp thêm tiền để tránh bị gián đoạn nhé!</p>
      <p style="color:#6b6b80;font-size:12px;margin-top:24px">Thông báo tự động từ hệ thống Lunch With Me.</p>
    </div>
    """
    _send(email, subject, html)
