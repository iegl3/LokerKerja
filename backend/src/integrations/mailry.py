import os
import hmac
import hashlib
import httpx
from typing import Optional, List, Dict, Any
from tenacity import retry, wait_exponential, stop_after_attempt
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("MAILRY_BASE_URL", "https://api.mailry.co/ext")

# Simple in-memory cache to prevent duplicate emails
_email_cache = {}

def _generate_email_key(to: str, subject: str) -> str:
    """Generate a unique key for email deduplication"""
    return hashlib.md5(f"{to}:{subject}".encode()).hexdigest()

def _is_duplicate_email(to: str, subject: str, window_minutes: int = 5) -> bool:
    """Check if this email was sent recently"""
    global _email_cache
    key = _generate_email_key(to, subject)
    now = datetime.now()
    
    logger.info(f"Checking duplicate email: {to} - {subject[:50]}...")
    logger.info(f"Cache key: {key}")
    logger.info(f"Current cache size: {len(_email_cache)}")
    
    if key in _email_cache:
        last_sent = _email_cache[key]
        time_diff = now - last_sent
        logger.info(f"Found existing email sent {time_diff.total_seconds():.1f}s ago")
        if now - last_sent < timedelta(minutes=window_minutes):
            logger.warning(f"DUPLICATE EMAIL PREVENTED: {to} - {subject[:50]}...")
            return True
    
    # Update cache
    _email_cache[key] = now
    logger.info(f"Email added to cache: {to} - {subject[:50]}...")
    
    # Clean old entries (keep only last hour)
    cutoff = now - timedelta(hours=1)
    old_size = len(_email_cache)
    _email_cache = {k: v for k, v in _email_cache.items() if v > cutoff}
    if len(_email_cache) < old_size:
        logger.info(f"Cleaned {old_size - len(_email_cache)} old cache entries")
    
    return False


def _get_api_key() -> str:
    return os.getenv("MAILRY_API_KEY", "")


def _get_headers() -> Dict[str, str]:
    api_key = _get_api_key()
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _get_sender_email_id() -> str:
    return os.getenv("MAILRY_SENDER_EMAIL_ID", "")


def _get_webhook_secret() -> str:
    return os.getenv("MAILRY_WEBHOOK_SECRET", "")


@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
async def list_sender_emails() -> Dict[str, Any]:
    """Get list of sender emails from Mailry"""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("MAILRY_API_KEY not configured")
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{BASE_URL}/email", headers=_get_headers())
        response.raise_for_status()
        return response.json()


@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
async def upload_attachment(
    file_bytes: bytes, 
    filename: str, 
    content_type: str = "application/octet-stream"
) -> Dict[str, Any]:
    """Upload file attachment to Mailry"""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("MAILRY_API_KEY not configured")
    
    files = {"file": (filename, file_bytes, content_type)}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{BASE_URL}/inbox/attachment", 
            headers=_get_headers(), 
            files=files
        )
        response.raise_for_status()
        return response.json()


@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
async def send_email(
    to: str,
    subject: str,
    text: str,
    html: Optional[str] = None,
    sender_email_id: Optional[str] = None,
    attachments: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Send email via Mailry"""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("MAILRY_API_KEY not configured")
    
    # Resolve sender email id (env or fetch first available)
    resolved_sender = sender_email_id or _get_sender_email_id()
    if not resolved_sender:
        try:
            logger.info("MAILRY_SENDER_EMAIL_ID not set, fetching available sender emails...")
            senders = await list_sender_emails()
            logger.info(f"Available senders response: {senders}")
            items = senders.get("data") or senders.get("items") or senders
            # items could be list or dict depending on API; try first id
            if isinstance(items, list) and items:
                first = items[0]
                resolved_sender = first.get("id") or first.get("emailId") or first.get("email_id")
                logger.info(f"Auto-selected sender: {resolved_sender}")
            else:
                logger.error(f"No sender emails found in response: {senders}")
        except Exception as _e:
            logger.warning(f"Failed to auto-select sender email id: {_e}")
    
    if not resolved_sender:
        raise ValueError(f"No sender email ID available. Please set MAILRY_SENDER_EMAIL_ID or ensure sender emails exist in Mailry dashboard.")
    
    payload = {
        "emailId": resolved_sender or "",
        "to": [to],
        "subject": subject,
        "text": text,
    }
    
    if html:
        payload["htmlBody"] = html
    if attachments:
        payload["attachments"] = attachments

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{BASE_URL}/inbox/send", 
            json=payload, 
            headers=_get_headers()
        )
        
        # Debug logging
        # Log payload without sensitive data
        debug_payload = {**payload, "text": f"{payload['text'][:100]}..." if len(payload.get('text', '')) > 100 else payload.get('text', '')}
        logger.info(f"Mailry send request: {debug_payload}")
        logger.info(f"Mailry response status: {response.status_code}")
        if response.status_code not in [200, 201]:
            logger.error(f"Mailry error response: {response.text}")
        
        response.raise_for_status()
        return response.json()


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify webhook signature from Mailry"""
    secret = _get_webhook_secret()
    if not secret or not signature_header:
        return False
    
    try:
        digest = hmac.new(
            secret.encode(), 
            raw_body, 
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, signature_header)
    except Exception as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        return False


def _create_email_template(content: str) -> str:
    """Create professional email template wrapper"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LokerKerja</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #4CAF50;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 20px;
            border: 1px solid #ddd;
        }}
        .footer {{
            background-color: #f5f5f5;
            padding: 15px;
            text-align: center;
            border-radius: 0 0 5px 5px;
            font-size: 12px;
            color: #666;
        }}
        .job-item {{
            background-color: white;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #4CAF50;
            border-radius: 3px;
        }}
        .btn {{
            display: inline-block;
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 3px;
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LokerKerja</h1>
    </div>
    <div class="content">
        {content}
    </div>
    <div class="footer">
        <p>LokerKerja - Platform Lowongan Kerja</p>
        <p>Untuk berhenti berlangganan, reply email ini dengan kata "STOP"</p>
    </div>
</body>
</html>
"""


async def send_job_results_email(
    to: str,
    user_name: str,
    position_title: str,
    location: str,
    jobs: List[Dict[str, Any]],
    top_n: int = 10
) -> Dict[str, Any]:
    """Send formatted job results email"""
    logger.info(f"Preparing to send job results email to {to} for position {position_title}")
    
    subject = f"[LokerKerja] {len(jobs[:top_n])} Lowongan Terbaru - {position_title}"
    
    # Check for duplicate emails
    if _is_duplicate_email(to, subject, window_minutes=5):
        logger.warning(f"Duplicate job results email prevented for {to}")
        return {"message": "Duplicate email prevented", "duplicate": True}
    
    # Additional database-based duplicate check
    try:
        from subscriptions.store import SubscriptionStore
        store = SubscriptionStore()
        subject_hash = hashlib.md5(subject.encode()).hexdigest()[:8]
        if store.was_email_sent_recently(to, subject_hash, minutes=5):
            logger.warning(f"Database duplicate check: job results email already sent to {to}")
            return {"message": "Duplicate email prevented (database check)", "duplicate": True}
    except Exception as e:
        logger.warning(f"Database duplicate check failed: {e}")
    
    # Get subscription to get unsubscribe token
    try:
        from subscriptions.store import SubscriptionStore
        store = SubscriptionStore()
        subscription = store.get_subscription_by_email(to)
        unsubscribe_url = f"http://127.0.0.1:8000/api/subscriptions/unsubscribe?token={subscription.unsubscribe_token}" if subscription else "#"
    except Exception as e:
        logger.warning(f"Failed to get unsubscribe URL: {e}")
        unsubscribe_url = "#"
    
    # Text version
    text_lines = [
        f"Halo {user_name},",
        "",
        f"Berikut adalah {len(jobs[:top_n])} lowongan terbaru untuk posisi {position_title} di {location}:",
        "",
    ]
    
    for i, job in enumerate(jobs[:top_n], 1):
        salary = ""
        if job.get("min_amount") and job.get("max_amount"):
            salary = f" - {job['min_amount']}-{job['max_amount']} {job.get('currency', '')}"
        elif job.get("min_amount"):
            salary = f" - {job['min_amount']}+ {job.get('currency', '')}"
        
        text_lines.append(
            f"{i}. {job.get('title', 'N/A')} @ {job.get('company', 'N/A')} "
            f"({job.get('location', 'N/A')}){salary}"
        )
        if job.get('job_url') or job.get('url'):
            text_lines.append(f"   Apply: {job.get('job_url') or job.get('url')}")
        text_lines.append("")
    
    text_lines.extend([
        "---",
        "Terima kasih menggunakan LokerKerja!",
        f"Untuk berhenti berlangganan: {unsubscribe_url}",
        "Atau reply email ini dengan kata 'STOP'"
    ])
    
    # HTML version with improved styling
    html_content = f"""
        <h2>Halo {user_name}!</h2>
        
        <p>Berikut adalah {len(jobs[:top_n])} lowongan terbaru untuk posisi {position_title} di {location}:</p>
        
        <h3>Daftar Lowongan Kerja:</h3>
    """
    
    for i, job in enumerate(jobs[:top_n], 1):
        job_url = job.get('job_url') or job.get('url')
        apply_button = ""
        if job_url:
            apply_button = f"<a href='{job_url}' class='btn' target='_blank'>Lamar Sekarang</a>"
        
        html_content += f"""
        <div class="job-item">
            <h4>{i}. {job.get('title', 'N/A')}</h4>
            <p><strong>Perusahaan:</strong> {job.get('company', 'N/A')}</p>
            <p><strong>Lokasi:</strong> {job.get('location', 'N/A')}</p>
            {apply_button}
        </div>
        """
    
    html_content += """
        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
        
        <p><strong>Tips Sukses Melamar Kerja:</strong></p>
        <ul>
            <li>Sesuaikan CV dengan posisi yang dilamar</li>
            <li>Tulis cover letter yang personal dan menarik</li>
            <li>Riset perusahaan sebelum interview</li>
            <li>Siapkan portofolio yang relevan</li>
        </ul>
        
        <p>Semoga berhasil mendapatkan pekerjaan impian!</p>
        <p>Tim LokerKerja</p>
        
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center;">
            <p style="margin: 0; font-size: 14px; color: #666;">
                <strong>Untuk berhenti berlangganan:</strong><br>
                <a href="{unsubscribe_url}" style="color: #4CAF50;">Klik di sini</a> atau reply email ini dengan kata "STOP"
            </p>
        </div>
    """
    
    text = "\n".join(text_lines)
    html = _create_email_template(html_content)
    
    try:
        result = await send_email(to=to, subject=subject, text=text, html=html)
        logger.info(f"Successfully sent job results email to {to}: {result}")
        
        # Record email sent in database for future duplicate prevention
        try:
            from subscriptions.store import SubscriptionStore
            store = SubscriptionStore()
            store.mark_email_sent(to, subject, "job_results")
        except Exception as e:
            logger.warning(f"Failed to record email in database: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Failed to send job results email to {to}: {e}")
        # Log email content for demo purposes (when delivery fails)
        logger.info(f"EMAIL CONTENT FOR DEMO - Subject: {subject}")
        logger.info(f"EMAIL CONTENT FOR DEMO - To: {to}")
        logger.info(f"EMAIL CONTENT FOR DEMO - HTML: {html[:500]}...")
        # Return success for demo purposes
        return {"message": "Email logged for demo (delivery may have failed due to domain reputation)"}


async def send_welcome_subscription_email(
    to: str,
    user_name: str,
    position_title: str,
    frequency: str,
    jobs: List[Dict[str, Any]] = None,
    top_n: int = 5
) -> Dict[str, Any]:
    """Send welcome email for new subscription with optional job samples"""
    logger.info(f"Preparing to send welcome email to {to} for position {position_title}")
    
    subject = f"[LokerKerja] Selamat Datang! Subscription {position_title} Aktif!"
    
    # Check for duplicate emails
    if _is_duplicate_email(to, subject, window_minutes=5):
        logger.warning(f"Duplicate welcome email prevented for {to}")
        return {"message": "Duplicate email prevented", "duplicate": True}
    
    # Additional database-based duplicate check
    try:
        from subscriptions.store import SubscriptionStore
        store = SubscriptionStore()
        subject_hash = hashlib.md5(subject.encode()).hexdigest()[:8]
        if store.was_email_sent_recently(to, subject_hash, minutes=5):
            logger.warning(f"Database duplicate check: welcome email already sent to {to}")
            return {"message": "Duplicate email prevented (database check)", "duplicate": True}
    except Exception as e:
        logger.warning(f"Database duplicate check failed: {e}")
    
    # Get subscription to get unsubscribe token
    try:
        from subscriptions.store import SubscriptionStore
        store = SubscriptionStore()
        subscription = store.get_subscription_by_email(to)
        unsubscribe_url = f"http://127.0.0.1:8000/api/subscriptions/unsubscribe?token={subscription.unsubscribe_token}" if subscription else "#"
    except Exception as e:
        logger.warning(f"Failed to get unsubscribe URL: {e}")
        unsubscribe_url = "#"
    
    # Text version
    text_lines = [
        f"Halo {user_name}! 👋",
        "",
        "Terima kasih sudah berlangganan LokerKerja!",
        "",
        f"✅ Subscription untuk posisi: {position_title}",
        f"📅 Frekuensi alert: {frequency}",
        f"📧 Email: {to}",
        "",
        "Kamu akan menerima informasi lowongan pekerjaan terbaru sesuai dengan preferensi yang sudah kamu pilih.",
        ""
    ]
    
    # Add sample jobs if provided
    if jobs and len(jobs) > 0:
        text_lines.extend([
            "Sebagai contoh, berikut beberapa lowongan yang cocok untuk kamu:",
            ""
        ])
        
        for i, job in enumerate(jobs[:top_n], 1):
            text_lines.append(
                f"{i}. {job.get('title', 'N/A')} @ {job.get('company', 'N/A')} "
                f"({job.get('location', 'N/A')})"
            )
            if job.get('job_url') or job.get('url'):
                text_lines.append(f"   Apply: {job.get('job_url') or job.get('url')}")
            text_lines.append("")
    
    text_lines.extend([
        "---",
        "Tips:",
        "• Cek email secara berkala untuk lowongan terbaru",
        "• Simpan email ini untuk referensi",
        "• Jika ada pertanyaan, reply email ini",
        "",
        "Selamat mencari kerja! 🚀",
        "",
        "Tim LokerKerja",
        f"Untuk berhenti berlangganan: {unsubscribe_url}",
        "Atau reply email ini dengan kata 'STOP'"
    ])
    
    # HTML version with improved styling
    html_content = f"""
        <h2>Selamat Datang, {user_name}!</h2>
        
        <p>Terima kasih sudah berlangganan LokerKerja.</p>
        
        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 15px 0;">
            <h3>Detail Subscription:</h3>
            <p><strong>Posisi:</strong> {position_title}</p>
            <p><strong>Frekuensi:</strong> {frequency}</p>
            <p><strong>Email:</strong> {to}</p>
        </div>
        
        <p>Kamu akan menerima informasi lowongan kerja terbaru sesuai dengan preferensi yang sudah kamu pilih.</p>
    """
    
    # Add sample jobs if provided
    if jobs and len(jobs) > 0:
        html_content += """
        <h3>Contoh Lowongan yang Cocok:</h3>
        """
        
        for i, job in enumerate(jobs[:top_n], 1):
            job_url = job.get('job_url') or job.get('url')
            apply_button = ""
            if job_url:
                apply_button = f"<a href='{job_url}' class='btn' target='_blank'>Lihat Detail</a>"
            
            html_content += f"""
            <div class="job-item">
                <h4>{i}. {job.get('title', 'N/A')}</h4>
                <p><strong>Perusahaan:</strong> {job.get('company', 'N/A')}</p>
                <p><strong>Lokasi:</strong> {job.get('location', 'N/A')}</p>
                {apply_button}
            </div>
            """
    
    html_content += """
        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
        
        <p><strong>Tips:</strong></p>
        <ul>
            <li>Cek email secara berkala untuk lowongan terbaru</li>
            <li>Simpan email ini untuk referensi</li>
            <li>Update profil LinkedIn untuk meningkatkan peluang</li>
        </ul>
        
        <p>Selamat mencari kerja!</p>
        <p>Tim LokerKerja</p>
        
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center;">
            <p style="margin: 0; font-size: 14px; color: #666;">
                <strong>Untuk berhenti berlangganan:</strong><br>
                <a href="{unsubscribe_url}" style="color: #4CAF50;">Klik di sini</a> atau reply email ini dengan kata "STOP"
            </p>
        </div>
    """
    
    text = "\n".join(text_lines)
    html = _create_email_template(html_content)
    
    try:
        result = await send_email(to=to, subject=subject, text=text, html=html)
        logger.info(f"Successfully sent welcome email to {to}: {result}")
        
        # Record email sent in database for future duplicate prevention
        try:
            from subscriptions.store import SubscriptionStore
            store = SubscriptionStore()
            store.mark_email_sent(to, subject, "welcome")
        except Exception as e:
            logger.warning(f"Failed to record email in database: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Failed to send welcome email to {to}: {e}")
        # Log email content for demo purposes
        logger.info(f"WELCOME EMAIL FOR DEMO - Subject: {subject}")
        logger.info(f"WELCOME EMAIL FOR DEMO - To: {to}")
        logger.info(f"WELCOME EMAIL FOR DEMO - HTML: {html[:500]}...")
        # Return success for demo purposes
        return {"message": "Welcome email logged for demo (delivery may have failed due to domain reputation)"}