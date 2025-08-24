import asyncio
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from jobspy import scrape_jobs
import pandas as pd

# Setup logging
logger = logging.getLogger(__name__)

class JobSearchRequest(BaseModel):
    """Job search request parameters"""
    keyword: str = Field(..., description="Job search keyword/position")
    location: str = Field(default="Indonesia", description="Job location")
    results_wanted: int = Field(default=10, ge=1, le=100, description="Number of results (1-100)")
    sites: List[str] = Field(default=["linkedin", "indeed"], description="Job sites to search")
    linkedin_fetch_description: bool = Field(default=True, description="Fetch full job descriptions from LinkedIn")

class JobResult(BaseModel):
    """Individual job result"""
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    location: str = Field(..., description="Job location")
    job_url: str = Field(..., description="URL to job posting")
    description: Optional[str] = Field(None, description="Job description")
    date_posted: Optional[str] = Field(None, description="Date posted")
    salary_min: Optional[float] = Field(None, description="Minimum salary")
    salary_max: Optional[float] = Field(None, description="Maximum salary")
    job_type: Optional[str] = Field(None, description="Job type (full-time, part-time, etc)")
    site: str = Field(..., description="Source site (linkedin, indeed, etc)")

class JobSearchResponse(BaseModel):
    """Job search response with metadata"""
    jobs: List[JobResult] = Field(..., description="List of job results")
    total_found: int = Field(..., description="Total jobs found")
    search_params: JobSearchRequest = Field(..., description="Search parameters used")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")

async def search_jobs_async(request: JobSearchRequest) -> JobSearchResponse:
    """
    Async wrapper for job scraping using JobSpy
    
    Args:
        request: Job search parameters
        
    Returns:
        JobSearchResponse with job results and metadata
        
    Raises:
        Exception: If job scraping fails
    """
    import time
    start_time = time.perf_counter()
    
    try:
        logger.info(f"Starting job search: {request.keyword} in {request.location}")
        
        # Run JobSpy scraping in thread pool to avoid blocking
        jobs_df = await asyncio.to_thread(
            scrape_jobs,
            site_name=request.sites,
            search_term=request.keyword,
            location=request.location,
            results_wanted=request.results_wanted,
            linkedin_fetch_description=request.linkedin_fetch_description
        )
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        if jobs_df is None or len(jobs_df) == 0:
            logger.warning(f"No jobs found for: {request.keyword}")
            return JobSearchResponse(
                jobs=[],
                total_found=0,
                search_params=request,
                processing_time_ms=processing_time
            )
        
        # Convert DataFrame to JobResult objects
        job_results = []
        for _, row in jobs_df.iterrows():
            # Determine source site from URL
            job_url = str(row.get("job_url", ""))
            site = "other"
            if "linkedin" in job_url.lower():
                site = "linkedin"
            elif "indeed" in job_url.lower():
                site = "indeed"
            
            job_result = JobResult(
                title=str(row.get("title", "")).strip() or "Unknown Title",
                company=str(row.get("company", "")).strip() or "Unknown Company",
                location=str(row.get("location", "")).strip() or request.location,
                job_url=job_url,
                description=str(row.get("description", "")).strip() if pd.notna(row.get("description")) else None,
                date_posted=str(row.get("date_posted", "")).strip() if pd.notna(row.get("date_posted")) else None,
                salary_min=float(row["salary_min"]) if pd.notna(row.get("salary_min")) else None,
                salary_max=float(row["salary_max"]) if pd.notna(row.get("salary_max")) else None,
                job_type=str(row.get("job_type", "")).strip() if pd.notna(row.get("job_type")) else None,
                site=site
            )
            job_results.append(job_result)
        
        logger.info(f"Successfully scraped {len(job_results)} jobs in {processing_time:.1f}ms")
        
        return JobSearchResponse(
            jobs=job_results,
            total_found=len(job_results),
            search_params=request,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        logger.error(f"Job scraping failed: {e}")
        raise Exception(f"Job scraping failed: {str(e)}")

# Utility functions for backwards compatibility
async def scrape_jobs_simple(keyword: str, location: str = "Indonesia", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Simple job scraping function for quick use
    
    Returns:
        List of job dictionaries
    """
    request = JobSearchRequest(
        keyword=keyword,
        location=location,
        results_wanted=limit
    )
    
    response = await search_jobs_async(request)
    
    # Convert to simple dict format
    return [job.model_dump() for job in response.jobs] 