#!/usr/bin/env python3
"""
Job Alert Scheduler for LokerKerja
Runs background job alerts for subscribed users
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from subscriptions.service import SubscriptionService
from subscriptions.models import FrequencyType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class JobAlertScheduler:
    """Scheduler for job alerts"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.subscription_service = SubscriptionService()
    
    async def process_realtime_alerts(self):
        """Process real-time job alerts (every 15 minutes)"""
        logger.info("Processing real-time job alerts...")
        try:
            results = await self.subscription_service.process_due_subscriptions(FrequencyType.REALTIME)
            logger.info(f"Real-time alerts: {results}")
        except Exception as e:
            logger.error(f"Real-time alerts failed: {e}")
    
    async def process_daily_alerts(self):
        """Process daily job alerts"""
        logger.info("Processing daily job alerts...")
        try:
            results = await self.subscription_service.process_due_subscriptions(FrequencyType.DAILY)
            logger.info(f"Daily alerts: {results}")
        except Exception as e:
            logger.error(f"Daily alerts failed: {e}")
    
    async def process_weekly_alerts(self):
        """Process weekly job alerts"""
        logger.info("Processing weekly job alerts...")
        try:
            results = await self.subscription_service.process_due_subscriptions(FrequencyType.WEEKLY)
            logger.info(f"Weekly alerts: {results}")
        except Exception as e:
            logger.error(f"Weekly alerts failed: {e}")
    
    async def cleanup_old_data(self):
        """Clean up old job cache and sent job records"""
        logger.info("Cleaning up old data...")
        try:
            self.subscription_service.store.cleanup_old_data(days=30)
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    async def test_newsletter_now(self, email: str = None) -> Dict[str, Any]:
        """Test newsletter sending immediately (for demo purposes)"""
        try:
            if email:
                # Test specific email
                subscription = self.subscription_service.store.get_subscription_by_email(email)
                if not subscription:
                    return {"error": f"No subscription found for {email}"}
                
                result = await self.subscription_service.process_subscription(subscription)
                return {"success": True, "email": email, "result": result}
            else:
                # Test all active subscriptions
                due_subscriptions = self.subscription_service.store.get_due_subscriptions()
                results = []
                
                for subscription in due_subscriptions:
                    try:
                        result = await self.subscription_service.process_subscription(subscription)
                        results.append({"email": subscription.email, "success": True, "result": result})
                    except Exception as e:
                        results.append({"email": subscription.email, "success": False, "error": str(e)})
                
                return {"success": True, "processed": len(results), "results": results}
                
        except Exception as e:
            logger.error(f"Test newsletter failed: {e}")
            return {"success": False, "error": str(e)}
    
    def start(self):
        """Start the scheduler"""
        logger.info("Starting job alert scheduler...")
        
        # Real-time alerts (every 15 minutes)
        self.scheduler.add_job(
            self.process_realtime_alerts,
            trigger=CronTrigger(minute='*/15'),
            id='realtime_alerts',
            name='Process Real-time Alerts',
            max_instances=1,
            coalesce=True
        )
        
        # Daily alerts (every day at 7 AM)
        self.scheduler.add_job(
            self.process_daily_alerts,
            trigger=CronTrigger(hour=7, minute=0),
            id='daily_alerts',
            name='Process Daily Alerts',
            max_instances=1,
            coalesce=True
        )
        
        # Weekly alerts (every Monday at 8 AM)
        self.scheduler.add_job(
            self.process_weekly_alerts,
            trigger=CronTrigger(day_of_week=0, hour=8, minute=0),
            id='weekly_alerts',
            name='Process Weekly Alerts',
            max_instances=1,
            coalesce=True
        )
        
        # Cleanup (every day at 2 AM)
        self.scheduler.add_job(
            self.cleanup_old_data,
            trigger=CronTrigger(hour=2, minute=0),
            id='cleanup',
            name='Clean up old data',
            max_instances=1,
            coalesce=True
        )
        
        self.scheduler.start()
        logger.info("Scheduler started successfully")
        
        # Print scheduled jobs
        for job in self.scheduler.get_jobs():
            logger.info(f"Scheduled job: {job.name} - {job.trigger}")
    
    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


async def main():
    """Main function"""
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    scheduler = JobAlertScheduler()
    
    try:
        scheduler.start()
        
        # Keep the scheduler running
        logger.info("Scheduler is running... Press Ctrl+C to stop")
        while True:
            await asyncio.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
    finally:
        scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main()) 