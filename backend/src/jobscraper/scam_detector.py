import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

from cv_handler.config import LUNOS, SEM_LUNOS
from .scraper import JobResult

logger = logging.getLogger(__name__)

class ScamRiskLevel(str, Enum):
    """Scam risk levels"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ScamResult(BaseModel):
    """Scam detection result"""
    risk_level: ScamRiskLevel = Field(..., description="Risk level assessment")
    risk_score: float = Field(..., description="Risk score (0.0-1.0)")
    risk_percentage: float = Field(..., description="Risk percentage (0-100)")
    detected_flags: List[str] = Field(default_factory=list, description="Specific scam indicators found")
    analysis: str = Field(..., description="Detailed analysis of the job posting")
    recommendations: List[str] = Field(default_factory=list, description="Safety recommendations")

# Enhanced scam detection keywords and patterns
SCAM_KEYWORDS = {
    # Financial red flags
    "financial": [
        "send money", "transfer fee", "pay to apply", "wire transfer", "upfront payment",
        "processing fee", "registration fee", "training fee", "background check fee",
        "kirim uang", "biaya transfer", "bayar dulu", "biaya pendaftaran", "biaya training"
    ],
    
    # Work-from-home scams
    "work_from_home": [
        "work from home and earn thousands", "easy money", "no experience required",
        "earn $500+ daily", "make money fast", "guaranteed income",
        "kerja dari rumah dapat jutaan", "uang mudah", "penghasilan pasti"
    ],
    
    # Urgency tactics
    "urgency": [
        "act now", "limited time", "urgent", "immediate start", "apply today only",
        "bertindak sekarang", "waktu terbatas", "segera", "mulai langsung"
    ],
    
    # Vague job descriptions
    "vague": [
        "data entry", "envelope stuffing", "mystery shopper", "product tester",
        "survey taker", "click ads", "entry data", "isi survey"
    ],
    
    # Contact method red flags
    "contact": [
        "text only", "whatsapp only", "telegram only", "no phone interview",
        "hanya whatsapp", "hanya telegram", "tanpa wawancara"
    ],
    
    # Multi-level marketing
    "mlm": [
        "recruit others", "build your team", "unlimited earning potential",
        "be your own boss", "rekrut orang lain", "bangun tim", "jadi bos sendiri"
    ]
}

# Legitimate job indicators
LEGITIMATE_INDICATORS = [
    "interview process", "background check", "references required", "portfolio review",
    "technical assessment", "proses wawancara", "cek referensi", "tes teknis"
]

# Suspicious company patterns
SUSPICIOUS_PATTERNS = [
    r".*corp\.?$",  # Companies ending in "corp"
    r".*llc\.?$",   # Companies ending in "llc"
    r".*inc\.?$",   # Companies ending in "inc"
    r"^\w+\s*\d+$", # Company name with just numbers
]

def analyze_text_patterns(text: str) -> Dict[str, List[str]]:
    """
    Analyze text for suspicious patterns
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary of pattern categories and found matches
    """
    text_lower = text.lower()
    found_patterns = {}
    
    for category, keywords in SCAM_KEYWORDS.items():
        matches = []
        for keyword in keywords:
            if keyword in text_lower:
                matches.append(keyword)
        
        if matches:
            found_patterns[category] = matches
    
    return found_patterns

def calculate_risk_score(patterns: Dict[str, List[str]], job: JobResult) -> float:
    """
    Calculate risk score based on detected patterns
    
    Args:
        patterns: Detected suspicious patterns
        job: Job posting details
        
    Returns:
        Risk score (0.0-1.0)
    """
    risk_score = 0.0
    
    # Weight different pattern categories
    weights = {
        "financial": 0.4,      # Highest weight for financial scams
        "work_from_home": 0.25,
        "urgency": 0.15,
        "vague": 0.1,
        "contact": 0.2,
        "mlm": 0.3
    }
    
    for category, matches in patterns.items():
        if category in weights:
            # More matches = higher risk
            category_risk = min(len(matches) * 0.2, 1.0)
            risk_score += category_risk * weights[category]
    
    # Additional risk factors
    
    # Very high salary for simple work
    if job.salary_max and job.salary_max > 100000:  # $100k+
        if any(keyword in (job.description or "").lower() 
               for keyword in ["data entry", "simple", "easy", "no experience"]):
            risk_score += 0.3
    
    # Suspicious company name
    company_lower = job.company.lower()
    for pattern in SUSPICIOUS_PATTERNS:
        if re.match(pattern, company_lower):
            risk_score += 0.1
            break
    
    # No job description
    if not job.description or len(job.description.strip()) < 50:
        risk_score += 0.2
    
    # Check for legitimate indicators (reduces risk)
    legitimate_count = 0
    if job.description:
        desc_lower = job.description.lower()
        for indicator in LEGITIMATE_INDICATORS:
            if indicator in desc_lower:
                legitimate_count += 1
    
    # Reduce risk score based on legitimate indicators
    risk_reduction = min(legitimate_count * 0.1, 0.3)
    risk_score = max(0.0, risk_score - risk_reduction)
    
    return min(1.0, risk_score)

def determine_risk_level(risk_score: float) -> ScamRiskLevel:
    """
    Determine risk level based on score
    
    Args:
        risk_score: Risk score (0.0-1.0)
        
    Returns:
        Risk level enum
    """
    if risk_score >= 0.8:
        return ScamRiskLevel.CRITICAL
    elif risk_score >= 0.6:
        return ScamRiskLevel.HIGH
    elif risk_score >= 0.4:
        return ScamRiskLevel.MEDIUM
    elif risk_score >= 0.2:
        return ScamRiskLevel.LOW
    else:
        return ScamRiskLevel.SAFE

def generate_recommendations(risk_level: ScamRiskLevel, patterns: Dict[str, List[str]]) -> List[str]:
    """
    Generate safety recommendations based on risk assessment
    
    Args:
        risk_level: Assessed risk level
        patterns: Detected suspicious patterns
        
    Returns:
        List of safety recommendations
    """
    recommendations = []
    
    if risk_level in [ScamRiskLevel.CRITICAL, ScamRiskLevel.HIGH]:
        recommendations.append("DO NOT APPLY - High scam risk detected")
        recommendations.append("Never send money or personal financial information")
        
    if risk_level == ScamRiskLevel.MEDIUM:
        recommendations.append("PROCEED WITH CAUTION - Research company thoroughly")
        recommendations.append("Verify company legitimacy through official channels")
        
    if "financial" in patterns:
        recommendations.append("Legitimate employers never ask for upfront payments")
        
    if "work_from_home" in patterns:
        recommendations.append("Be skeptical of 'get rich quick' work-from-home schemes")
        
    if "urgency" in patterns:
        recommendations.append("Legitimate jobs don't pressure immediate decisions")
        
    if "contact" in patterns:
        recommendations.append("Legitimate companies provide multiple contact methods")
    
    # General safety recommendations
    if risk_level != ScamRiskLevel.SAFE:
        recommendations.extend([
            "Never share sensitive personal information early in the process",
            "Research the company on LinkedIn, Glassdoor, and official websites",
            "Ask for references from current employees",
            "Request a detailed job description and company information"
        ])
    
    return recommendations

async def analyze_with_llm(job: JobResult, patterns: Dict[str, List[str]]) -> str:
    """
    Get detailed LLM analysis of job posting
    
    Args:
        job: Job posting
        patterns: Detected suspicious patterns
        
    Returns:
        Detailed analysis text
    """
    async with SEM_LUNOS:
        try:
            prompt = f"""
Analyze this job posting for potential scam indicators:

Title: {job.title}
Company: {job.company}
Location: {job.location}
Description: {(job.description or 'No description')[:1000]}

Detected suspicious patterns: {patterns}

Provide a brief analysis covering:
1. Legitimacy assessment
2. Key red flags or positive indicators
3. Overall recommendation

Keep response concise and professional.
"""

            response = await LUNOS.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return "Unable to perform detailed analysis at this time."

async def detect_scam(job: JobResult) -> ScamResult:
    """
    Comprehensive scam detection for job posting
    
    Args:
        job: Job posting to analyze
        
    Returns:
        Scam detection result with risk assessment
    """
    try:
        # Analyze text patterns
        text_to_analyze = f"{job.title} {job.company} {job.description or ''}"
        patterns = analyze_text_patterns(text_to_analyze)
        
        # Calculate risk score
        risk_score = calculate_risk_score(patterns, job)
        risk_level = determine_risk_level(risk_score)
        
        # Generate detected flags
        detected_flags = []
        for category, matches in patterns.items():
            for match in matches[:2]:  # Limit to 2 matches per category
                detected_flags.append(f"{category.title()}: '{match}'")
        
        # Generate recommendations
        recommendations = generate_recommendations(risk_level, patterns)
        
        # Get LLM analysis
        analysis = await analyze_with_llm(job, patterns)
        
        return ScamResult(
            risk_level=risk_level,
            risk_score=risk_score,
            risk_percentage=round(risk_score * 100, 1),
            detected_flags=detected_flags,
            analysis=analysis,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Scam detection error: {e}")
        
        # Return safe default on error
        return ScamResult(
            risk_level=ScamRiskLevel.LOW,
            risk_score=0.1,
            risk_percentage=10.0,
            detected_flags=["Analysis error occurred"],
            analysis="Unable to complete full analysis. Please manually verify job legitimacy.",
            recommendations=[
                "Manually research this company and job posting",
                "Exercise standard job search caution"
            ]
        )

# Batch processing function
async def detect_scam_batch(jobs: List[JobResult]) -> List[ScamResult]:
    """
    Detect scams for multiple job postings
    
    Args:
        jobs: List of job postings
        
    Returns:
        List of scam detection results
    """
    # Process jobs concurrently but with limited concurrency
    semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent analyses
    
    async def analyze_job(job):
        async with semaphore:
            return await detect_scam(job)
    
    results = await asyncio.gather(*[analyze_job(job) for job in jobs])
    return results 