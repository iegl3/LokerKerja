from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class FrequencyType(str, Enum):
    REALTIME = "realtime"
    DAILY = "daily"
    WEEKLY = "weekly"
    DISABLED = "disabled"


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"


class JobType(str, Enum):
    FULLTIME = "fulltime"
    PARTTIME = "parttime"
    CONTRACT = "contract"
    INTERN = "intern"
    FREELANCE = "freelance"


class RemoteType(str, Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class UserPreferences(BaseModel):
    """User manual preferences for job alerts"""
    final_role: Optional[str] = None  # Legacy single role (for backward compatibility)
    
    seniority: Optional[SeniorityLevel] = None
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    exclude_companies: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    sites: List[str] = Field(default_factory=lambda: ["linkedin", "indeed"])
    job_types: List[JobType] = Field(default_factory=list)
    remote_type: Optional[RemoteType] = None
    salary_min: Optional[int] = None
    salary_currency: str = "IDR"


class SubscriptionRequest(BaseModel):
    """Request to create or update subscription"""
    email: str
    user_name: Optional[str] = None
    preferences: UserPreferences
    frequency: FrequencyType = FrequencyType.WEEKLY
    top_n: int = Field(default=10, ge=1, le=50)
    alert_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    enable_matching: bool = True
    enable_scam_check: bool = True


class Subscription(BaseModel):
    """Full subscription record"""
    id: Optional[str] = None
    email: str
    user_name: Optional[str] = None
    preferences: UserPreferences
    frequency: FrequencyType
    top_n: int
    alert_threshold: float
    enable_matching: bool
    enable_scam_check: bool
    
    # Status fields
    active: bool = True
    last_checked_at: Optional[datetime] = None
    unsubscribe_token: Optional[str] = None
    
    # Audit fields
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    cv_profile_hash: Optional[str] = None


class SubscriptionResponse(BaseModel):
    """Response for subscription operations"""
    success: bool
    message: str
    subscription: Optional[Subscription] = None


class SentJob(BaseModel):
    """Record of jobs sent to user"""
    user_email: str
    job_url_hash: str
    job_title: str
    job_company: str
    sent_at: datetime
    similarity_score: Optional[float] = None


class JobCache(BaseModel):
    """Cached job from scraping"""
    id: Optional[str] = None
    site: str
    title: str
    company: str
    location: str
    description: Optional[str] = None
    job_url: str
    job_type: Optional[str] = None
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    currency: Optional[str] = None
    posted_at: Optional[datetime] = None
    fetched_at: datetime
    embedding: Optional[List[float]] = None
    url_hash: str  # For deduplication 