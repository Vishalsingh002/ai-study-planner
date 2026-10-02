import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def _send_async_email_task(mail_server, mail_port, mail_user, mail_pass, use_tls, msg, reset_url):
    try:
        if not mail_user or not mail_pass:
            print("\n" + "="*70)
            print(f"[MAIL NOTICE] SMTP credentials not set in .env / Environment.")
            print(f"Target Email: {msg.get('To')}")
            print(f"[DEV RESET LINK] Open this link in your browser to reset password:")
            print(f"{reset_url}")
            print("="*70 + "\n")
            return

        server = smtplib.SMTP(mail_server, mail_port, timeout=12)
        if use_tls:
            server.starttls()
        server.login(mail_user, mail_pass)
        server.send_message(msg)
        server.quit()
        print(f"[MAIL SUCCESS] Password reset email successfully sent to {msg.get('To')}")
    except Exception as e:
        print(f"[MAIL ERROR] Failed to send email to {msg.get('To')}: {e}")
        print(f"[FALLBACK LINK] Use this reset link directly: {reset_url}")

def send_reset_email(recipient_email, recipient_name, reset_url):
    """
    Constructs and asynchronously dispatches a secure password reset email.
    """
    mail_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(os.environ.get('MAIL_PORT', 587))
    mail_user = os.environ.get('MAIL_USERNAME', '')
    mail_pass = os.environ.get('MAIL_PASSWORD', '')
    use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    sender_name = os.environ.get('MAIL_DEFAULT_SENDER_NAME', 'StudyAI Academic Support')

    from_address = mail_user if mail_user else 'support@studyai.app'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Reset Your StudyAI Password 🔐'
    msg['From'] = f'{sender_name} <{from_address}>'
    msg['To'] = recipient_email

    # Plain-text alternative
    text_content = f"""Hello {recipient_name},

You requested to reset your password for your StudyAI student account.

Click the link below to set your new password (valid for 15 minutes):
{reset_url}

If you did not request this, please ignore this email and your password will remain unchanged.

Best regards,
The StudyAI Team
"""

    # Rich responsive HTML template
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; }}
  .card {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.06); }}
  .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
  .content {{ padding: 32px 28px; color: #334155; line-height: 1.6; font-size: 15px; }}
  .btn-wrapper {{ text-align: center; margin: 28px 0; }}
  .btn {{ display: inline-block; background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); color: #ffffff !important; font-weight: 700; text-decoration: none; padding: 14px 32px; border-radius: 10px; font-size: 15px; }}
  .notice {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 6px; font-size: 13px; color: #1e40af; margin-top: 20px; }}
  .footer {{ padding: 20px 24px; background: #f8fafc; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div style="font-size: 28px; margin-bottom: 6px;">🎓</div>
    <h2 style="margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">StudyAI Academic Platform</h2>
    <p style="margin: 4px 0 0; color: #cbd5e1; font-size: 13px;">Secure Password Reset</p>
  </div>
  <div class="content">
    <p>Hello <strong>{recipient_name}</strong>,</p>
    <p>We received a request to reset the password for your student account associated with <strong>{recipient_email}</strong>.</p>
    
    <div class="btn-wrapper">
      <a href="{reset_url}" class="btn" target="_blank">Reset My Password →</a>
    </div>

    <div class="notice">
      ⏱️ <strong>Security Expiry:</strong> This reset link will automatically expire in <strong>15 minutes</strong>. If you did not make this request, you can safely ignore this email — your account remains secure.
    </div>

    <p style="margin-top: 24px; font-size: 12px; color: #94a3b8; word-break: break-all;">
      Button not working? Copy and paste this link into your browser:<br>
      <a href="{reset_url}" style="color: #4f46e5;">{reset_url}</a>
    </p>
  </div>
  <div class="footer">
    © StudyAI • Intelligent Academic Study Planner & Pomodoro Engine
  </div>
</div>
</body>
</html>"""

    part1 = MIMEText(text_content, 'plain')
    part2 = MIMEText(html_content, 'html')
    msg.attach(part1)
    msg.attach(part2)

    # Launch daemon background thread to send email without blocking HTTP worker
    thread = threading.Thread(
        target=_send_async_email_task,
        args=(mail_server, mail_port, mail_user, mail_pass, use_tls, msg, reset_url),
        daemon=True
    )
    thread.start()
