import asyncio
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from jobscraper import search_jobs_async, match_cv_to_jobs, detect_scam_batch
from integrations.mailry import send_job_results_email
from .models import Subscription, SentJob, JobCache, FrequencyType, UserPreferences
from .store import SubscriptionStore

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing job subscriptions and alerts"""
    
    def __init__(self, store: Optional[SubscriptionStore] = None):
        self.store = store or SubscriptionStore()
    
    def build_search_query(self, preferences: UserPreferences) -> str:
        """Build JobSpy search query from user preferences"""
        query_parts = []
        
        # Legacy: Single role
        if preferences.final_role:
            query_parts.append(preferences.final_role)
        
        # Must-have skills
        if preferences.must_have_skills:
            # Use AND logic for must-have skills
            for skill in preferences.must_have_skills[:3]:  # Limit to avoid too long queries
                query_parts.append(skill)
        
        # Nice-to-have skills (add some but not all to avoid noise)
        if preferences.nice_to_have_skills:
            query_parts.extend(preferences.nice_to_have_skills[:2])
        
        # Dynamic fallback based on user preferences
        if query_parts:
            return " ".join(query_parts)
        
        # Use inferred_role as fallback if available
        if preferences.inferred_role:
            return preferences.inferred_role
        
        # Final fallback
        return "jobs"
    
    def filter_jobs_by_preferences(
        self, 
        jobs: List[Dict[str, Any]], 
        preferences: UserPreferences
    ) -> List[Dict[str, Any]]:
        """Filter jobs based on user preferences"""
        filtered_jobs = []
        
        for job in jobs:
            # Check salary minimum
            if preferences.salary_min:
                job_salary = job.get('min_amount') or job.get('max_amount')
                if job_salary and job_salary < preferences.salary_min:
                    continue
            
            # Check job type
            if preferences.job_types:
                job_type = job.get('job_type', '').lower()
                if job_type and job_type not in [jt.value for jt in preferences.job_types]:
                    continue
            
            # Check exclude keywords
            if preferences.exclude_keywords:
                job_text = f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')}".lower()
                if any(keyword.lower() in job_text for keyword in preferences.exclude_keywords):
                    continue
            
            # Check exclude companies
            if preferences.exclude_companies:
                company = job.get('company', '').lower()
                if any(exc_company.lower() in company for exc_company in preferences.exclude_companies):
                    continue
            
            filtered_jobs.append(job)
        
        return filtered_jobs
    
    def score_job_relevance(
        self, 
        job: Dict[str, Any], 
        preferences: UserPreferences
    ) -> float:
        """Score job relevance based on preferences (simple keyword matching)"""
        score = 0.0
        job_text = f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')}".lower()
        
        # Must-have skills (high weight)
        for skill in preferences.must_have_skills:
            if skill.lower() in job_text:
                score += 0.3
        
        # Nice-to-have skills (medium weight)
        for skill in preferences.nice_to_have_skills:
            if skill.lower() in job_text:
                score += 0.1
        
        # Role match (high weight)
        if preferences.final_role and preferences.final_role.lower() in job_text:
            score += 0.4
        
        # Seniority match
        if preferences.seniority:
            seniority_keywords = {
                'intern': ['intern', 'internship', 'magang'],
                'junior': ['junior', 'entry', 'graduate', 'fresh'],
                'mid': ['mid', 'middle', 'intermediate'],
                'senior': ['senior', 'lead', 'principal'],
                'lead': ['lead', 'principal', 'staff'],
                'manager': ['manager', 'head', 'director']
            }
            
            keywords = seniority_keywords.get(preferences.seniority.value, [])
            if any(keyword in job_text for keyword in keywords):
                score += 0.2
        
        return min(score, 1.0)  # Cap at 1.0
    
    async def process_subscription(self, subscription: Subscription) -> int:
        """Process a single subscription and send job alerts"""
        try:
            logger.info(f"Processing subscription for {subscription.email}")
            
            # Legacy: Single role processing
            return await self._process_single_role_subscription(subscription)
            
        except Exception as e:
            logger.error(f"Failed to process subscription for {subscription.email}: {e}")
            return 0

    async def _process_single_role_subscription(self, subscription: Subscription) -> int:
        """Process subscription with single role (legacy method)"""
        try:
            logger.info(f"Processing subscription for {subscription.email}")
            
            # Build search query
            search_query = self.build_search_query(subscription.preferences)
            
            all_jobs = []
            for location in subscription.preferences.locations or ["Indonesia"]:
                try:
                    from jobscraper import JobSearchRequest
                    search_request = JobSearchRequest(
                        keyword=search_query,
                        location=location,
                        results_wanted=subscription.top_n * 2,
                        sites=subscription.preferences.sites,
                        linkedin_fetch_description=True
                    )
                    
                    search_result = await search_jobs_async(search_request)
                    if search_result.jobs:
                        all_jobs.extend([job.model_dump() for job in search_result.jobs])
                except Exception as e:
                    logger.warning(f"Job search failed for {location}: {e}")
                    continue
            
            if not all_jobs:
                logger.info(f"No jobs found for {subscription.email}")
                return 0
            
            # Filter out jobs already sent
            new_jobs = []
            for job in all_jobs:
                job_url = job.get('job_url') or job.get('url', '')
                if job_url and not self.store.was_job_sent(subscription.email, job_url):
                    new_jobs.append(job)
            
            if not new_jobs:
                logger.info(f"No new jobs for {subscription.email}")
                return 0
            
            # Filter by preferences
            filtered_jobs = self.filter_jobs_by_preferences(new_jobs, subscription.preferences)
            
            if not filtered_jobs:
                logger.info(f"No jobs passed preference filters for {subscription.email}")
                return 0
            
            # Score and sort jobs
            scored_jobs = []
            for job in filtered_jobs:
                score = self.score_job_relevance(job, subscription.preferences)
                if score >= subscription.alert_threshold:
                    job['_relevance_score'] = score
                    scored_jobs.append(job)
            
            scored_jobs.sort(key=lambda x: x.get('_relevance_score', 0), reverse=True)
            
            # Take top N
            top_jobs = scored_jobs[:subscription.top_n]
            
            if not top_jobs:
                logger.info(f"No jobs met threshold for {subscription.email}")
                return 0
            
            # Optional: Run scam detection
            if subscription.enable_scam_check:
                try:
                    scam_results = await detect_scam_batch([job.get('description', '') for job in top_jobs])
                    for job, scam_result in zip(top_jobs, scam_results):
                        job['_scam_risk'] = scam_result.risk_level.value
                        job['_scam_score'] = scam_result.risk_score
                except Exception as e:
                    logger.warning(f"Scam detection failed: {e}")
            
            # Send email
            try:
                await send_job_results_email(
                    to=subscription.email,
                    user_name=subscription.user_name or "User",
                    position_title=subscription.preferences.final_role or subscription.preferences.inferred_role or "Career Opportunities",
                    location=", ".join(subscription.preferences.locations) or "Indonesia",
                    jobs=top_jobs,
                    top_n=subscription.top_n
                )
                
                # Mark jobs as sent
                for job in top_jobs:
                    job_url = job.get('job_url') or job.get('url', '')
                    if job_url:
                        sent_job = SentJob(
                            user_email=subscription.email,
                            job_url_hash=hashlib.sha256(job_url.encode()).hexdigest()[:16],
                            job_title=job.get('title', ''),
                            job_company=job.get('company', ''),
                            sent_at=datetime.now(),
                            similarity_score=job.get('_relevance_score')
                        )
                        self.store.mark_job_sent(sent_job)
                
                # Update last checked time
                subscription.last_checked_at = datetime.now()
                self.store.update_subscription(subscription)
                
                logger.info(f"Sent {len(top_jobs)} jobs to {subscription.email}")
                return len(top_jobs)
                
            except Exception as e:
                logger.error(f"Failed to send email to {subscription.email}: {e}")
                return 0
            
        except Exception as e:
            logger.error(f"Failed to process subscription for {subscription.email}: {e}")
            return 0
    
    async def process_due_subscriptions(self, frequency: FrequencyType) -> Dict[str, int]:
        """Process all subscriptions due for the given frequency"""
        subscriptions = self.store.get_due_subscriptions(frequency)
        
        if not subscriptions:
            return {"processed": 0, "jobs_sent": 0}
        
        logger.info(f"Processing {len(subscriptions)} {frequency.value} subscriptions")
        
        results = []
        for subscription in subscriptions:
            try:
                jobs_sent = await self.process_subscription(subscription)
                results.append(jobs_sent)
                
                # Add small delay to avoid overwhelming APIs
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to process subscription {subscription.email}: {e}")
                results.append(0)
        
        return {
            "processed": len(results),
            "jobs_sent": sum(results),
            "successful": sum(1 for r in results if r > 0)
        }
    
    async def create_subscription_from_smart_discovery(
        self,
        email: str,
        user_name: Optional[str],
        cv_profile: Dict[str, Any],
        position_inference: Dict[str, Any],
        frequency: FrequencyType = FrequencyType.WEEKLY,
        locations: Optional[List[str]] = None,
        sites: Optional[List[str]] = None
    ) -> tuple[str, bool]:
        """Create subscription from Smart Discovery results"""
        
        # Extract skills from CV
        skills = cv_profile.get('skills', {})
        all_skills = []
        if isinstance(skills, dict):
            all_skills.extend(skills.get('technical', []))
            all_skills.extend(skills.get('soft', []))
            all_skills.extend(skills.get('languages', []))
        elif isinstance(skills, list):
            all_skills.extend(skills)
        
        # NEW: Auto-split multi-role subscriptions
        primary_role = position_inference.get('primary_role') or position_inference.get('position_title')
        alternates = position_inference.get('alternates', [])
        
        # Get up to 2 roles (primary + first alternate)
        roles_to_subscribe = [primary_role]
        if alternates and len(alternates) > 0:
            roles_to_subscribe.append(alternates[0])
        
        # Limit to 2 roles max
        roles_to_subscribe = roles_to_subscribe[:2]
        
        subscription_ids = []
        is_new_subscription = False
        
        for i, role in enumerate(roles_to_subscribe):
            if not role or role == "N/A":
                continue
                
            # Create unique email for each role subscription
            role_email = f"{email}+{role.lower().replace(' ', '_')}" if i > 0 else email
            
            # Check if role-specific subscription exists
            existing_role = self.store.get_subscription_by_email(role_email)
            
            # Create preferences for this specific role
            preferences = UserPreferences(
                final_role=role,  # Single role per subscription
                inferred_role=role,
                seniority=None,
                must_have_skills=all_skills[:5],
                nice_to_have_skills=all_skills[5:10],
                locations=locations or ["Indonesia"],
                sites=sites or ["linkedin", "indeed"]
            )
            
            if existing_role:
                # Update existing role subscription
                existing_role.preferences = preferences
                existing_role.frequency = frequency
                existing_role.top_n = 10
                existing_role.alert_threshold = 0.3
                existing_role.enable_matching = True
                existing_role.enable_scam_check = True
                existing_role.cv_profile_hash = hashlib.sha256(str(cv_profile).encode()).hexdigest()[:16]
                self.store.update_subscription(existing_role)
                subscription_ids.append(existing_role.id or existing_role.email)
            else:
                # Create new role subscription
                subscription = Subscription(
                    email=role_email,
                    user_name=user_name,
                    preferences=preferences,
                    frequency=frequency,
                    top_n=10,
                    alert_threshold=0.3,
                    enable_matching=True,
                    enable_scam_check=True,
                    cv_profile_hash=hashlib.sha256(str(cv_profile).encode()).hexdigest()[:16]
                )
                subscription_id = self.store.create_subscription(subscription)
                subscription_ids.append(subscription_id)
                is_new_subscription = True
        
        # Return primary subscription ID and new status
        primary_subscription_id = subscription_ids[0] if subscription_ids else email
        return primary_subscription_id, is_new_subscription 