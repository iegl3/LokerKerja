import sqlite3
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from .models import Subscription, SentJob, JobCache, UserPreferences, FrequencyType


class SubscriptionStore:
    """Simple SQLite-based storage for subscriptions"""
    
    def __init__(self, db_path: str = "data/subscriptions.db"):
        self.db_path = db_path
        # Create data directory if it doesn't exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    user_name TEXT,
                    preferences TEXT NOT NULL,  -- JSON
                    frequency TEXT NOT NULL,
                    top_n INTEGER NOT NULL,
                    alert_threshold REAL NOT NULL,
                    enable_matching BOOLEAN NOT NULL,
                    enable_scam_check BOOLEAN NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT 1,
                    last_checked_at TEXT,
                    unsubscribe_token TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    cv_profile_hash TEXT
                );
                
                CREATE TABLE IF NOT EXISTS sent_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT NOT NULL,
                    job_url_hash TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    job_company TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    similarity_score REAL,
                    UNIQUE(user_email, job_url_hash)
                );
                
                CREATE TABLE IF NOT EXISTS job_cache (
                    id TEXT PRIMARY KEY,
                    site TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    description TEXT,
                    job_url TEXT NOT NULL,
                    job_type TEXT,
                    min_amount INTEGER,
                    max_amount INTEGER,
                    currency TEXT,
                    posted_at TEXT,
                    fetched_at TEXT NOT NULL,
                    embedding TEXT,  -- JSON array
                    url_hash TEXT UNIQUE NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions(email);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(active);
                CREATE INDEX IF NOT EXISTS idx_sent_jobs_email ON sent_jobs(user_email);
                CREATE INDEX IF NOT EXISTS idx_job_cache_fetched ON job_cache(fetched_at);
                CREATE INDEX IF NOT EXISTS idx_job_cache_hash ON job_cache(url_hash);
            """)
    
    def create_subscription(self, subscription: Subscription) -> str:
        """Create a new subscription"""
        if not subscription.id:
            subscription.id = secrets.token_urlsafe(16)
        if not subscription.unsubscribe_token:
            subscription.unsubscribe_token = secrets.token_urlsafe(32)
        
        now = datetime.now().isoformat()
        subscription.created_at = datetime.fromisoformat(now)
        subscription.updated_at = datetime.fromisoformat(now)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO subscriptions 
                (id, email, user_name, preferences, frequency, top_n, alert_threshold,
                 enable_matching, enable_scam_check, active, last_checked_at,
                 unsubscribe_token, created_at, updated_at, cv_profile_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subscription.id,
                subscription.email,
                subscription.user_name,
                json.dumps(subscription.preferences.model_dump()),
                subscription.frequency.value,
                subscription.top_n,
                subscription.alert_threshold,
                subscription.enable_matching,
                subscription.enable_scam_check,
                subscription.active,
                subscription.last_checked_at.isoformat() if subscription.last_checked_at else None,
                subscription.unsubscribe_token,
                now,
                now,
                subscription.cv_profile_hash
            ))
        
        return subscription.id
    
    def get_subscription_by_email(self, email: str) -> Optional[Subscription]:
        """Get subscription by email"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE email = ?", (email,)
            ).fetchone()
            
            if not row:
                return None
            
            return self._row_to_subscription(row)
    
    def get_subscription_by_token(self, token: str) -> Optional[Subscription]:
        """Get subscription by unsubscribe token"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE unsubscribe_token = ?", (token,)
            ).fetchone()
            
            if not row:
                return None
            
            return self._row_to_subscription(row)
    
    def update_subscription(self, subscription: Subscription) -> bool:
        """Update existing subscription"""
        subscription.updated_at = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE subscriptions SET
                    user_name = ?, preferences = ?, frequency = ?, top_n = ?,
                    alert_threshold = ?, enable_matching = ?, enable_scam_check = ?,
                    active = ?, last_checked_at = ?, updated_at = ?, cv_profile_hash = ?
                WHERE email = ?
            """, (
                subscription.user_name,
                json.dumps(subscription.preferences.model_dump()),
                subscription.frequency.value,
                subscription.top_n,
                subscription.alert_threshold,
                subscription.enable_matching,
                subscription.enable_scam_check,
                subscription.active,
                subscription.last_checked_at.isoformat() if subscription.last_checked_at else None,
                subscription.updated_at.isoformat(),
                subscription.cv_profile_hash,
                subscription.email
            ))
            
            return cursor.rowcount > 0
    
    def get_due_subscriptions(self, frequency: FrequencyType) -> List[Subscription]:
        """Get subscriptions that are due for processing"""
        cutoff_hours = {
            FrequencyType.REALTIME: 0.25,  # 15 minutes
            FrequencyType.DAILY: 24,
            FrequencyType.WEEKLY: 168,  # 7 days
        }
        
        if frequency not in cutoff_hours:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=cutoff_hours[frequency])
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM subscriptions 
                WHERE active = 1 AND frequency = ? 
                AND (last_checked_at IS NULL OR last_checked_at < ?)
                ORDER BY last_checked_at ASC
            """, (frequency.value, cutoff_time.isoformat())).fetchall()
            
            return [self._row_to_subscription(row) for row in rows]
    
    def mark_job_sent(self, sent_job: SentJob):
        """Record that a job was sent to a user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sent_jobs
                (user_email, job_url_hash, job_title, job_company, sent_at, similarity_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sent_job.user_email,
                sent_job.job_url_hash,
                sent_job.job_title,
                sent_job.job_company,
                sent_job.sent_at.isoformat(),
                sent_job.similarity_score
            ))
            conn.commit()

    def was_email_sent_recently(self, email: str, subject_hash: str, minutes: int = 5) -> bool:
        """Check if an email with this subject was sent recently to this user"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM sent_jobs 
                WHERE user_email = ? AND job_title LIKE ? AND sent_at > ?
            """, (email, f"%{subject_hash}%", cutoff_time.isoformat()))
            
            result = cursor.fetchone()
            return result["count"] > 0 if result else False

    def mark_email_sent(self, email: str, subject: str, email_type: str = "job_alert"):
        """Record that an email was sent to prevent duplicates"""
        subject_hash = hashlib.md5(subject.encode()).hexdigest()[:8]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sent_jobs
                (user_email, job_url_hash, job_title, job_company, sent_at, similarity_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                email,
                f"email_{subject_hash}",
                f"{email_type}: {subject[:50]}...",
                "LokerKerja System",
                datetime.now().isoformat(),
                1.0
            ))
            conn.commit()
    
    def was_job_sent(self, user_email: str, job_url: str) -> bool:
        """Check if job was already sent to user"""
        job_hash = hashlib.sha256(job_url.encode()).hexdigest()[:16]
        
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM sent_jobs WHERE user_email = ? AND job_url_hash = ?",
                (user_email, job_hash)
            ).fetchone()[0]
            
            return count > 0
    
    def cache_job(self, job_cache: JobCache):
        """Cache a job from scraping"""
        if not job_cache.id:
            job_cache.id = secrets.token_urlsafe(16)
        
        job_cache.url_hash = hashlib.sha256(job_cache.job_url.encode()).hexdigest()[:16]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO job_cache
                (id, site, title, company, location, description, job_url, job_type,
                 min_amount, max_amount, currency, posted_at, fetched_at, embedding, url_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_cache.id,
                job_cache.site,
                job_cache.title,
                job_cache.company,
                job_cache.location,
                job_cache.description,
                job_cache.job_url,
                job_cache.job_type,
                job_cache.min_amount,
                job_cache.max_amount,
                job_cache.currency,
                job_cache.posted_at.isoformat() if job_cache.posted_at else None,
                job_cache.fetched_at.isoformat(),
                json.dumps(job_cache.embedding) if job_cache.embedding else None,
                job_cache.url_hash
            ))
    
    def get_recent_jobs(self, hours: int = 24) -> List[JobCache]:
        """Get jobs cached within the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM job_cache 
                WHERE fetched_at > ? 
                ORDER BY fetched_at DESC
            """, (cutoff_time.isoformat(),)).fetchall()
            
            return [self._row_to_job_cache(row) for row in rows]
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old job cache and sent job records"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM job_cache WHERE fetched_at < ?", 
                (cutoff_time.isoformat(),)
            )
            conn.execute(
                "DELETE FROM sent_jobs WHERE sent_at < ?", 
                (cutoff_time.isoformat(),)
            )
    
    def _row_to_subscription(self, row: sqlite3.Row) -> Subscription:
        """Convert database row to Subscription object"""
        return Subscription(
            id=row['id'],
            email=row['email'],
            user_name=row['user_name'],
            preferences=UserPreferences(**json.loads(row['preferences'])),
            frequency=FrequencyType(row['frequency']),
            top_n=row['top_n'],
            alert_threshold=row['alert_threshold'],
            enable_matching=bool(row['enable_matching']),
            enable_scam_check=bool(row['enable_scam_check']),
            active=bool(row['active']),
            last_checked_at=datetime.fromisoformat(row['last_checked_at']) if row['last_checked_at'] else None,
            unsubscribe_token=row['unsubscribe_token'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            cv_profile_hash=row['cv_profile_hash']
        )
    
    def _row_to_job_cache(self, row: sqlite3.Row) -> JobCache:
        """Convert database row to JobCache object"""
        return JobCache(
            id=row['id'],
            site=row['site'],
            title=row['title'],
            company=row['company'],
            location=row['location'],
            description=row['description'],
            job_url=row['job_url'],
            job_type=row['job_type'],
            min_amount=row['min_amount'],
            max_amount=row['max_amount'],
            currency=row['currency'],
            posted_at=datetime.fromisoformat(row['posted_at']) if row['posted_at'] else None,
            fetched_at=datetime.fromisoformat(row['fetched_at']),
            embedding=json.loads(row['embedding']) if row['embedding'] else None,
            url_hash=row['url_hash']
        ) 