import asyncio
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from cv_handler.config import LUNOS, SEM_LUNOS
from .scraper import JobResult

logger = logging.getLogger(__name__)

class JobMatchRequest(BaseModel):
    """Job matching request parameters"""
    cv_profile: Dict[str, Any] = Field(..., description="Parsed CV profile data")
    jobs: List[JobResult] = Field(..., description="List of jobs to match against")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of top matches to return")

class JobMatch(BaseModel):
    """Individual job match result"""
    job: JobResult = Field(..., description="Job details")
    similarity_score: float = Field(..., description="Similarity score (0.0-1.0)")
    match_percentage: float = Field(..., description="Match percentage (0-100)")
    match_reasons: List[str] = Field(default_factory=list, description="Reasons for the match")

class JobMatchResponse(BaseModel):
    """Job matching response"""
    matches: List[JobMatch] = Field(..., description="Ranked job matches")
    cv_summary: str = Field(..., description="CV summary used for matching")
    total_jobs_analyzed: int = Field(..., description="Total number of jobs analyzed")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")

async def get_embedding_async(text: str) -> List[float]:
    """
    Get text embedding using LUNOS API
    
    Args:
        text: Text to embed
        
    Returns:
        List of embedding values
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding")
        return []
    
    async with SEM_LUNOS:
        try:
            # Clean and limit text
            clean_text = text.strip()[:4000]  # Reduced from 8000
            
            response = await LUNOS.embeddings.create(
                model="google/gemini-embedding-001",
                input=clean_text
            )
            
            # Debug the response structure
            logger.debug(f"Embedding response type: {type(response)}")
            logger.debug(f"Embedding response: {response}")
            
            if response and hasattr(response, 'data') and response.data and len(response.data) > 0:
                embedding = response.data[0].embedding
                if embedding and len(embedding) > 0:
                    logger.debug(f"Successfully got embedding of length {len(embedding)}")
                    return embedding
                else:
                    logger.warning("Embedding is empty or None")
                    return []
            else:
                logger.warning("No embedding data in response structure")
                return []
                
        except Exception as e:
            logger.error(f"Embedding API error: {e}")
            return []

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors
    
    Args:
        a, b: Vector embeddings
        
    Returns:
        Cosine similarity score (0.0-1.0)
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    
    try:
        a_np = np.array(a)
        b_np = np.array(b)
        
        # Calculate cosine similarity
        dot_product = np.dot(a_np, b_np)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
            
        similarity = dot_product / (norm_a * norm_b)
        
        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, float(similarity)))
        
    except Exception as e:
        logger.error(f"Cosine similarity calculation error: {e}")
        return 0.0

def simple_text_similarity(cv_text: str, job_text: str) -> float:
    """
    Calculate simple text similarity as fallback when embeddings fail
    
    Args:
        cv_text: CV text content
        job_text: Job description text
        
    Returns:
        Similarity score (0.0-1.0) based on keyword overlap
    """
    try:
        # Convert to lowercase and split into words
        cv_words = set(cv_text.lower().split())
        job_words = set(job_text.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}
        cv_words = cv_words - stop_words
        job_words = job_words - stop_words
        
        if not cv_words or not job_words:
            return 0.0
        
        # Calculate Jaccard similarity (intersection over union)
        intersection = len(cv_words & job_words)
        union = len(cv_words | job_words)
        
        similarity = intersection / union if union > 0 else 0.0
        
        # Boost score if there are technical skill matches
        tech_keywords = {'python', 'java', 'javascript', 'react', 'node', 'sql', 'aws', 'docker', 'kubernetes', 'git', 'api', 'rest', 'graphql', 'mongodb', 'postgresql', 'mysql', 'redis', 'elasticsearch', 'kafka', 'spark', 'hadoop', 'tensorflow', 'pytorch', 'scikit', 'pandas', 'numpy', 'flutter', 'android', 'ios', 'swift', 'kotlin', 'go', 'rust', 'c++', 'c#', 'php', 'ruby', 'scala', 'r', 'matlab', 'tableau', 'powerbi', 'excel', 'azure', 'gcp', 'linux', 'windows', 'macos', 'agile', 'scrum', 'devops', 'ci/cd', 'jenkins', 'github', 'gitlab', 'jira', 'confluence'}
        
        tech_matches = len((cv_words & job_words) & tech_keywords)
        if tech_matches > 0:
            similarity += tech_matches * 0.1  # Boost by 10% per tech match
        
        return min(1.0, similarity)  # Cap at 1.0
        
    except Exception as e:
        logger.error(f"Simple text similarity error: {e}")
        return 0.0

def extract_cv_text_for_matching(cv_profile: Dict[str, Any]) -> str:
    """
    Extract relevant text from CV profile for matching
    
    Args:
        cv_profile: Parsed CV profile
        
    Returns:
        Combined text representation of CV
    """
    text_parts = []
    
    # Add summary
    if cv_profile.get("summary"):
        text_parts.append(cv_profile["summary"])
    
    # Add skills
    if cv_profile.get("skills"):
        skills_text = " ".join(cv_profile["skills"])
        text_parts.append(f"Skills: {skills_text}")
    
    # Add experience
    if cv_profile.get("experience"):
        for exp in cv_profile["experience"]:
            exp_parts = []
            if exp.get("role"):
                exp_parts.append(exp["role"])
            if exp.get("company"):
                exp_parts.append(f"at {exp['company']}")
            if exp.get("bullets"):
                exp_parts.extend(exp["bullets"])
            
            if exp_parts:
                text_parts.append(" ".join(exp_parts))
    
    # Add education
    if cv_profile.get("education"):
        for edu in cv_profile["education"]:
            edu_parts = []
            if edu.get("degree"):
                edu_parts.append(edu["degree"])
            if edu.get("school"):
                edu_parts.append(f"from {edu['school']}")
            
            if edu_parts:
                text_parts.append(" ".join(edu_parts))
    
    return ". ".join(text_parts)

def extract_job_text_for_matching(job: JobResult) -> str:
    """
    Extract relevant text from job posting for matching
    
    Args:
        job: Job result
        
    Returns:
        Combined text representation of job
    """
    text_parts = []
    
    # Add title and company
    text_parts.append(f"{job.title} at {job.company}")
    
    # Add description if available
    if job.description:
        # Limit description length to avoid token limits
        desc = job.description[:2000]
        text_parts.append(desc)
    
    return ". ".join(text_parts)

async def calculate_similarity(cv_profile: Dict[str, Any], job: JobResult) -> float:
    """
    Calculate similarity between CV and job posting
    
    Args:
        cv_profile: Parsed CV profile
        job: Job posting
        
    Returns:
        Similarity score (0.0-1.0)
    """
    try:
        # Extract text representations
        cv_text = extract_cv_text_for_matching(cv_profile)
        job_text = extract_job_text_for_matching(job)
        
        if not cv_text or not job_text:
            return 0.0
        
        # Try embedding-based similarity first
        try:
            cv_embedding, job_embedding = await asyncio.gather(
                get_embedding_async(cv_text),
                get_embedding_async(job_text)
            )
            
            if cv_embedding and job_embedding:
                similarity = cosine_similarity(cv_embedding, job_embedding)
                logger.debug(f"Embedding similarity for {job.title}: {similarity:.3f}")
                return similarity
            else:
                logger.warning(f"Embeddings failed for {job.title}, using fallback")
        except Exception as e:
            logger.warning(f"Embedding similarity failed for {job.title}: {e}, using fallback")
        
        # Fallback to simple text similarity
        similarity = simple_text_similarity(cv_text, job_text)
        logger.debug(f"Fallback similarity for {job.title}: {similarity:.3f}")
        return similarity
        
    except Exception as e:
        logger.error(f"Similarity calculation error: {e}")
        return 0.0

def generate_match_reasons(cv_profile: Dict[str, Any], job: JobResult, similarity: float) -> List[str]:
    """
    Generate human-readable reasons for job match
    
    Args:
        cv_profile: CV profile
        job: Job posting  
        similarity: Similarity score
        
    Returns:
        List of match reasons
    """
    reasons = []
    
    # Skill matching
    cv_skills = set(skill.lower() for skill in cv_profile.get("skills", []))
    job_text = (job.description or "").lower()
    
    matching_skills = []
    for skill in cv_skills:
        if skill in job_text:
            matching_skills.append(skill)
    
    if matching_skills:
        reasons.append(f"Skills match: {', '.join(matching_skills[:3])}")
    
    # Experience level
    total_months = cv_profile.get("total_duration_months", 0)
    years = total_months / 12 if total_months else 0
    
    if years >= 5:
        reasons.append("Senior level experience")
    elif years >= 2:
        reasons.append("Mid-level experience")
    elif years > 0:
        reasons.append("Entry-level experience")
    
    # Industry/company matching
    cv_companies = []
    for exp in cv_profile.get("experience", []):
        if exp.get("company"):
            cv_companies.append(exp["company"].lower())
    
    if any(company in job.company.lower() for company in cv_companies):
        reasons.append("Similar company background")
    
    # Overall similarity assessment
    if similarity >= 0.8:
        reasons.append("Excellent overall match")
    elif similarity >= 0.6:
        reasons.append("Good overall match")
    elif similarity >= 0.4:
        reasons.append("Moderate match")
    
    return reasons[:5]  # Limit to 5 reasons

async def match_cv_to_jobs(request: JobMatchRequest) -> JobMatchResponse:
    """
    Match CV profile against multiple job postings
    
    Args:
        request: Job matching request
        
    Returns:
        Ranked job matches with similarity scores
    """
    import time
    start_time = time.perf_counter()
    
    try:
        logger.info(f"Starting job matching for {len(request.jobs)} jobs")
        
        # Extract CV summary for response
        cv_summary = extract_cv_text_for_matching(request.cv_profile)[:200] + "..."
        
        # Calculate similarities for all jobs
        matches = []
        for job in request.jobs:
            similarity = await calculate_similarity(request.cv_profile, job)
            
            # Always include jobs, even with low similarity (changed from > 0 to >= 0)
            if similarity >= 0:  # Include all jobs with valid similarity
                match_reasons = generate_match_reasons(request.cv_profile, job, similarity)
                
                job_match = JobMatch(
                    job=job,
                    similarity_score=similarity,
                    match_percentage=round(similarity * 100, 1),
                    match_reasons=match_reasons
                )
                matches.append(job_match)
        
        # Sort by similarity score (descending)
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Limit to top_k results
        top_matches = matches[:request.top_k]
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        logger.info(f"Job matching completed: {len(top_matches)} matches in {processing_time:.1f}ms")
        
        return JobMatchResponse(
            matches=top_matches,
            cv_summary=cv_summary,
            total_jobs_analyzed=len(request.jobs),
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        logger.error(f"Job matching failed: {e}")
        raise Exception(f"Job matching failed: {str(e)}") 