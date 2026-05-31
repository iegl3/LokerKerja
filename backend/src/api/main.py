from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ValidationError, field_validator
import uuid, os, time, logging

from dotenv import load_dotenv
load_dotenv()

from cv_handler import read_cv_from_bytes_async
from jobscraper import (
    search_jobs_async, JobSearchRequest, JobResult, JobSearchResponse,
    match_cv_to_jobs, JobMatchRequest, JobMatchResponse,
    detect_scam, detect_scam_batch, ScamResult,
    PositionInferenceRequest, PositionInferenceResult, infer_position_from_cv,
    UserPreferences, AIRecommendations, UserSelections
)

# New imports for Mailry and subscriptions
from integrations.mailry import (
    list_sender_emails, upload_attachment, send_email, verify_webhook_signature,
    send_job_results_email, send_welcome_subscription_email
)
from subscriptions.models import (
    SubscriptionRequest, Subscription, SubscriptionResponse, 
    FrequencyType, UserPreferences as SubUserPreferences
)
from subscriptions.store import SubscriptionStore
from subscriptions.service import SubscriptionService

# Initialize services
subscription_store = SubscriptionStore()
subscription_service = SubscriptionService(subscription_store)

logger = logging.getLogger(__name__)

# Response Models for OpenAPI
class HealthResponse(BaseModel):
    ok: bool = Field(..., description="Health status")

class ContactInfo(BaseModel):
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    phone_masked: Optional[str] = Field(None, description="Masked phone number for privacy")
    location: Optional[str] = Field(None, description="Location/address")
    links: List[str] = Field(default_factory=list, description="Social media/portfolio links")

    @field_validator('links', mode='before')
    @classmethod
    def validate_links(cls, v):
        if v is None:
            return []
        return v

class Experience(BaseModel):
    company: Optional[str] = Field(None, description="Company name")
    role: Optional[str] = Field(None, description="Job title/role")
    start: Optional[str] = Field(None, description="Start date (YYYY-MM format)")
    end: Optional[str] = Field(None, description="End date (YYYY-MM format)")
    duration_months: Optional[int] = Field(None, description="Duration in months")
    bullets: List[str] = Field(default_factory=list, description="Job responsibilities/achievements")
    
    @field_validator('bullets', mode='before')
    @classmethod
    def validate_bullets(cls, v):
        if v is None:
            return []
        return v

class Education(BaseModel):
    degree: Optional[str] = Field(None, description="Degree/certification name")
    school: Optional[str] = Field(None, description="Institution name")
    start: Optional[str] = Field(None, description="Start date (YYYY-MM format)")
    end: Optional[str] = Field(None, description="End date (YYYY-MM format)")

class ProfileFeatures(BaseModel):
    skills_norm: List[str] = Field(default_factory=list, description="Normalized skills list")
    years_total: float = Field(0.0, description="Total years of experience")
    latest_role: Optional[str] = Field(None, description="Most recent job title")
    latest_company: Optional[str] = Field(None, description="Most recent company")
    confidence: float = Field(0.0, description="Parsing confidence score (0-1)")

class CVProfile(BaseModel):
    schema_version: str = Field("1.0", description="Profile schema version")
    source: str = Field("cv_upload", description="Data source")
    name: Optional[str] = Field(None, description="Full name")
    contacts: ContactInfo = Field(default_factory=ContactInfo.model_construct, description="Contact information")
    summary: Optional[str] = Field(None, description="Professional summary")
    skills: List[str] = Field(default_factory=list, description="Skills list")
    experience: List[Experience] = Field(default_factory=list, description="Work experience")
    education: List[Education] = Field(default_factory=list, description="Education history")
    certs: List[str] = Field(default_factory=list, description="Certifications")
    extras: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    total_duration_months: int = Field(0, description="Total work experience in months")
    total_duration: Optional[str] = Field(None, description="Human-readable total duration")
    features: Optional[ProfileFeatures] = Field(None, description="Additional computed features")
    
    @field_validator('skills', 'certs', mode='before')
    @classmethod
    def validate_lists(cls, v):
        if v is None:
            return []
        return v
    
    @field_validator('experience', 'education', mode='before')
    @classmethod
    def validate_object_lists(cls, v):
        if v is None:
            return []
        return v
    
    @field_validator('extras', mode='before')
    @classmethod
    def validate_extras(cls, v):
        if v is None:
            return {}
        return v

class ParseMetadata(BaseModel):
    ocr_ms: Optional[str] = Field(None, description="OCR processing time")
    parse_ms: Optional[str] = Field(None, description="LLM parsing time")
    fix_ms: Optional[str] = Field(None, description="JSON repair time")
    total_ms: Optional[str] = Field(None, description="Total processing time")
    parse_model: Optional[str] = Field(None, description="LLM model used for parsing")
    fix_model: Optional[str] = Field(None, description="LLM model used for repair")
    ocr_model: Optional[str] = Field(None, description="OCR model used")

class CVParseResponse(BaseModel):
    req_id: str = Field(..., description="Unique request identifier")
    profile: CVProfile = Field(..., description="Parsed CV profile data")
    meta: ParseMetadata = Field(..., description="Processing metadata")
    from_cache: bool = Field(False, description="Whether result was served from cache")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    req_id: Optional[str] = Field(None, description="Request ID for debugging")

# Constants
ALLOWED = {
    "application/pdf",
    "image/png","image/jpeg","image/webp"
}
MAX_SIZE = 12 * 1024 * 1024  # 12MB

# FastAPI app with enhanced metadata
app = FastAPI(
    title="LokerKerja CV Intelligence API",
    version="0.1.0",
    description="""
## CV Intelligence & Safe Apply Kit

**Tagline:** "Verifikasi dulu, tailor cepat, kirim rapi—tanpa spam."

### Features
- **Smart CV Parsing**: PDF & Image support with OCR
- **Multi-language**: English & Indonesian date parsing
- **Duration Extraction**: Automatic work experience calculation
- **ATS-Friendly**: Structured data for job applications
- **Privacy-First**: PII masking and secure processing

### Supported File Types
- PDF (searchable and scanned)
- Images: PNG, JPEG, WebP

### Rate Limits
- File size: 12MB max
- Pages: 3 pages default (configurable)
- Concurrent requests: Rate limited per provider

### Authentication
Currently open API. JWT authentication coming soon.
    """,
    contact={
        "name": "LokerKerja Team",
    },
    license_info={
        "name": "MIT",
    },
    servers=[
        {"url": "http://127.0.0.1:8000", "description": "Development server"},
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API is running and healthy",
    tags=["System"]
)
async def healthz():
    """
    Simple health check endpoint.
    Returns {"ok": true} if the service is running.
    """
    return {"ok": True}

@app.get(
    "/",
    summary="API Information",
    description="Get basic API information and available endpoints",
    tags=["System"]
)
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "LokerKerja CV Intelligence API",
        "version": "0.1.0",
        "description": "CV parsing and job application intelligence",
        "docs": "/docs",
        "health": "/healthz",
        "endpoints": {
            "cv_parse": "/api/cv/parse"
        }
    }

@app.get(
    "/upload",
    response_class=HTMLResponse,
    summary="Upload Test Page",
    description="Simple HTML form for testing file uploads",
    tags=["Testing"]
)
async def upload_form():
    """
    Simple HTML upload form for testing CV parsing.
    Alternative to Swagger UI for file uploads.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LokerKerja CV Upload Test</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select { padding: 8px; width: 100%; max-width: 400px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            .result { margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px; }
            .error { background: #f8d7da; color: #721c24; }
            .success { background: #d4edda; color: #155724; }
        </style>
    </head>
    <body>
        <h1>LokerKerja CV Upload Test</h1>
        <p>Upload CV file untuk testing API parsing</p>

        <form id="uploadForm" enctype="multipart/form-data">
            <div class="form-group">
                <label for="file">CV File (PDF, PNG, JPEG, WebP):</label>
                <input type="file" id="file" name="file" accept=".pdf,.png,.jpg,.jpeg,.webp" required>
            </div>

            <div class="form-group">
                <label for="pages">Pages (optional):</label>
                <input type="text" id="pages" name="pages" placeholder="e.g., 1-3 or 1,3">
            </div>

            <div class="form-group">
                <label for="force_ocr">Force OCR:</label>
                <select id="force_ocr" name="force_ocr">
                    <option value="false">No</option>
                    <option value="true">Yes</option>
                </select>
            </div>

            <div class="form-group">
                <label for="max_pages">Max Pages:</label>
                <select id="max_pages" name="max_pages">
                    <option value="1">1</option>
                    <option value="2">2</option>
                    <option value="3" selected>3</option>
                    <option value="5">5</option>
                </select>
            </div>

            <div class="form-group">
                <label for="use_cache">Use Cache:</label>
                <select id="use_cache" name="use_cache">
                    <option value="true" selected>Yes</option>
                    <option value="false">No</option>
                </select>
            </div>

            <button type="submit">Upload & Parse CV</button>
        </form>

        <div id="result"></div>

        <script>
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(e.target);
            const resultDiv = document.getElementById('result');

            resultDiv.innerHTML = '<p>Processing... Please wait (5-30 seconds)</p>';

            try {
                const response = await fetch('/api/cv/parse', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    resultDiv.className = 'result success';
                    resultDiv.innerHTML = `
                        <h3>Success!</h3>
                        <p><strong>Request ID:</strong> ${data.req_id}</p>
                        <p><strong>Name:</strong> ${data.profile.name || 'Not found'}</p>
                        <p><strong>Skills:</strong> ${data.profile.skills.length} skills</p>
                        <p><strong>Experience:</strong> ${data.profile.experience.length} jobs</p>
                        <p><strong>Total Duration:</strong> ${data.profile.total_duration || 'Not calculated'}</p>
                        <p><strong>Processing Time:</strong> ${data.meta.total_ms}</p>
                        <p><strong>From Cache:</strong> ${data.from_cache ? 'Yes' : 'No'}</p>
                        <details>
                            <summary>Raw JSON Response</summary>
                            <pre>${JSON.stringify(data, null, 2)}</pre>
                        </details>
                    `;
                } else {
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `
                        <h3>Error ${response.status}</h3>
                        <p>${data.detail || 'Unknown error'}</p>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    `;
                }
            } catch (error) {
                resultDiv.className = 'result error';
                resultDiv.innerHTML = `<h3>Network Error</h3><p>${error.message}</p>`;
            }
        });
        </script>
    </body>
    </html>
    """
    return html_content

@app.post(
    "/api/cv/parse",
    response_model=CVParseResponse,
    responses={
        200: {"description": "CV successfully parsed"},
        413: {"model": ErrorResponse, "description": "File too large (>12MB)"},
        415: {"model": ErrorResponse, "description": "Unsupported file type"},
        500: {"model": ErrorResponse, "description": "Parsing failed"},
    },
    summary="Parse CV Document",
    description="Upload and parse CV/resume from PDF or image file",
    tags=["CV Processing"]
)
async def parse_cv(
    file: UploadFile = File(
        ...,
        description="CV file (PDF, PNG, JPEG, WebP)",
        example="cv_document.pdf"
    ),
    pages: Optional[str] = Query(
        None,
        description="Page range to process (e.g., '1-3' or '1,3')",
        example="1-3"
    ),
    force_ocr: bool = Query(
        False,
        description="Force OCR even for searchable PDFs"
    ),
    max_pages: int = Query(
        3,
        ge=1,
        le=10,
        description="Maximum pages to process (1-10)"
    ),
    scale: float = Query(
        2.0,
        ge=1.0,
        le=4.0,
        description="Image scaling factor for OCR quality (1.0-4.0)"
    ),
    use_cache: bool = Query(
        True,
        description="Use cached results if available"
    )
):
    """
    ## Parse CV Document

    Upload a CV/resume file and extract structured profile information.

    ### Process Flow:
    1. **File Validation**: Check type and size
    2. **Text Extraction**: PDF parsing or OCR for images
    3. **AI Parsing**: Extract structured data using LLM
    4. **Validation**: Ensure data quality and format
    5. **Enhancement**: Calculate durations and normalize dates

    ### Supported Formats:
    - **PDF**: Both searchable and scanned documents
    - **Images**: PNG, JPEG, WebP (requires OCR)

    ### Performance:
    - **Typical**: 5-15 seconds for PDF
    - **OCR**: 10-30 seconds for images
    - **Cached**: <1 second for repeated requests

    ### Privacy:
    - Phone numbers are automatically masked
    - Files are processed in memory only
    - No permanent storage of uploaded files
    """
    # Validate file type
    if file.content_type not in ALLOWED:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Supported: {', '.join(ALLOWED)}"
        )

    # Read and validate file size
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(data)} bytes (max: {MAX_SIZE} bytes / 12MB)"
        )

    req_id = str(uuid.uuid4())
    profile: Dict[str, Any] = {}
    meta: Dict[str, Any] = {}

    try:
        profile, meta, flags = await read_cv_from_bytes_async(
            data=data,
            filename=file.filename or "upload.pdf",
            pages=pages,
            force_ocr=force_ocr,
            max_pages=max_pages,
            scale=scale,
            use_cache=use_cache,
            ttl_days=7,
            req_id=req_id
        )

        # Debug: Log the actual structure
        print(f"DEBUG - Profile keys: {list(profile.keys()) if isinstance(profile, dict) else type(profile)}")
        print(f"DEBUG - Meta keys: {list(meta.keys()) if isinstance(meta, dict) else type(meta)}")

        # Handle the __features field issue
        if isinstance(profile, dict) and '__features' in profile:
            profile['features'] = profile.pop('__features')

        # Fix validation issues - ensure all required fields have proper defaults
        if isinstance(profile, dict):
            # Fix contacts structure
            if 'contacts' in profile and profile['contacts']:
                contacts = profile['contacts']
                if contacts.get('links') is None:
                    contacts['links'] = []
            elif 'contacts' not in profile or profile['contacts'] is None:
                profile['contacts'] = {'links': []}

            # Fix other potential None values
            if profile.get('skills') is None:
                profile['skills'] = []
            if profile.get('experience') is None:
                profile['experience'] = []
            if profile.get('education') is None:
                profile['education'] = []
            if profile.get('certs') is None:
                profile['certs'] = []
            if profile.get('extras') is None:
                profile['extras'] = {}

        return CVParseResponse(
            req_id=req_id,
            profile=CVProfile(**profile),
            meta=ParseMetadata(**meta),
            from_cache=flags.get("from_cache", False)
        )

    except ValidationError as ve:
        print(f"DEBUG - Validation Error: {ve}")
        # Return raw data on validation error for debugging
        return JSONResponse({
            "error": "validation_failed",
            "req_id": req_id,
            "details": str(ve),
            "raw_profile": profile if 'profile' in locals() else None,
            "raw_meta": meta if 'meta' in locals() else None
        }, status_code=422)

    except Exception as e:
        print(f"DEBUG - General Error: {e}")
        print(f"DEBUG - Error type: {type(e)}")
        # Log error but don't expose internal details
        raise HTTPException(
            status_code=500,
            detail=f"CV parsing failed. Request ID: {req_id}"
        ) from e

# New: Position inference endpoint
@app.post(
    "/api/cv/infer-position",
    response_model=PositionInferenceResult,
    summary="Infer Suitable Positions from CV",
    description="Use LLM to infer the most suitable role(s) from a parsed CV profile (selective but inclusive for fresh graduates)",
    tags=["CV Processing"]
)
async def infer_position_api(request: PositionInferenceRequest):
    try:
        result = await infer_position_from_cv(
            cv_profile=request.cv_profile,
            top_alternates=request.top_alternates,
            allow_freshgrad_bias=request.allow_freshgrad_bias,
            language=request.language,
            user_preferences=request.user_preferences,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Position inference failed: {str(e)}")

# New: Smart discovery (infer -> search -> match -> optional scam)
@app.post(
    "/api/jobs/smart-discovery",
    summary="Smart Job Discovery from CV",
    description="Infer positions from CV, search jobs, match and optionally include scam detection",
    tags=["Job Matching"]
)
async def smart_discovery(
    cv_profile: Dict[str, Any],
    location: str = Query("Indonesia", description="Job location"),
    include_scam_check: bool = Query(True, description="Include scam detection for results"),
    results_wanted: int = Query(20, ge=1, le=50, description="Number of jobs to fetch"),
    sites: List[str] = Query(["linkedin", "indeed"], description="Sites to search"),
    top_matches: int = Query(10, ge=1, le=20, description="Number of top matches to return"),
    language: str = Query("en", description="Language for role naming: 'en' or 'id'"),
    # NEW: Optional pre-computed inference
    position_inference: Optional[Dict[str, Any]] = None,
    # NEW: Enable/disable matching (default: show all jobs)
    enable_matching: bool = Query(False, description="Enable AI matching (slower, may fail)"),
):
    import time
    start_time = time.perf_counter()

    # Step 1: Use provided inference OR compute new one
    if position_inference and position_inference.get("primary_role"):
        # Use provided inference (from frontend step 2)
        inf = PositionInferenceResult(**position_inference)
        print(f"DEBUG - Using provided inference: {inf.primary_role}")
    else:
        # Fallback: compute new inference
        inf = await infer_position_from_cv(cv_profile, top_alternates=2, allow_freshgrad_bias=True, language=language)
        print(f"DEBUG - Computed new inference: {inf.primary_role}")

    # Step 2: Search using primary keyword (fallback to alternates)
    keywords: List[str] = [inf.primary_role] + inf.alternates if inf.primary_role and inf.primary_role != "N/A" else inf.search_keywords
    if not keywords:
        # Dynamic fallback based on CV profile
        if isinstance(cv_profile, dict):
            # Check latest experience role
            experience = cv_profile.get("experience", [])
            if experience and isinstance(experience, list):
                latest_role = experience[0].get("role") if experience[0] else None
                if latest_role:
                    keywords = [str(latest_role)]
            
            # Check skills for common patterns if no experience
            if not keywords:
                # If no keywords from inference, try to infer position dynamically
                try:
                    print("DEBUG - No keywords from inference, running dynamic position inference...")
                    fallback_inf = await infer_position_from_cv(cv_profile, top_alternates=2, allow_freshgrad_bias=True, language=language)
                    if fallback_inf.primary_role and fallback_inf.primary_role != "N/A":
                        keywords = [fallback_inf.primary_role] + fallback_inf.alternates
                        print(f"DEBUG - Dynamic inference fallback keywords: {keywords}")
                    elif fallback_inf.search_keywords:
                        keywords = fallback_inf.search_keywords
                        print(f"DEBUG - Using search_keywords from fallback: {keywords}")
                except Exception as e:
                    print(f"DEBUG - Dynamic inference fallback failed: {e}")
        
        # Final fallback if still empty
        if not keywords:
            # Use generic broad search terms as last resort
            print("DEBUG - Using generic fallback search terms")
            keywords = ["jobs", "career opportunities", "employment"]

    aggregated_jobs: List[JobResult] = []
    for kw in keywords[:3]:
        try:
            jsr = JobSearchRequest(
                keyword=kw,
                location=location,
                results_wanted=results_wanted,
                sites=sites,
                linkedin_fetch_description=True,
            )
            resp = await search_jobs_async(jsr)
            if resp.jobs:
                aggregated_jobs.extend(resp.jobs)
            # Stop early if we already have enough jobs
            if len(aggregated_jobs) >= results_wanted:
                break
        except Exception:
            continue

    # Deduplicate by URL
    seen: set[str] = set()
    unique_jobs: List[JobResult] = []
    for j in aggregated_jobs:
        key = j.job_url or f"{j.title}|{j.company}|{j.location}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(j)

    # Step 3: Matching (OPTIONAL - only if enabled)
    if enable_matching:
        try:
            match_req = JobMatchRequest(cv_profile=cv_profile, jobs=unique_jobs[:results_wanted], top_k=top_matches)
            match_resp = await match_cv_to_jobs(match_req)
            jobs_to_show = match_resp.matches
            print(f"DEBUG - AI matching enabled: {len(jobs_to_show)} matches")
        except Exception as e:
            print(f"DEBUG - Matching failed: {e}, showing all jobs")
            # Fallback: show all jobs without matching
            jobs_to_show = [{"job": job, "similarity_score": None, "match_percentage": None, "match_reasons": ["Job found by inferred keyword search"]} for job in unique_jobs[:top_matches]]
    else:
        # Show all jobs without matching
        jobs_to_show = [{"job": job, "similarity_score": None, "match_percentage": None, "match_reasons": ["Job found by inferred keyword search"]} for job in unique_jobs[:top_matches]]
        print(f"DEBUG - AI matching disabled: showing {len(jobs_to_show)} jobs")

    # Step 4: Optional scam detection
    enhanced_matches: List[Dict[str, Any]] = []
    if include_scam_check and jobs_to_show:
        try:
            normalized_matches: List[Dict[str, Any]] = [m if isinstance(m, dict) else m.model_dump() for m in jobs_to_show]
            job_objects = [m["job"] for m in normalized_matches]
            scams = await detect_scam_batch(job_objects)
            for m, s in zip(normalized_matches, scams):
                enhanced_matches.append({**m, "scam_result": s.model_dump()})
        except Exception as e:
            print(f"DEBUG - Scam detection failed: {e}")
            enhanced_matches = []
            for m in jobs_to_show:
                enhanced_matches.append(m if isinstance(m, dict) else m.model_dump())
    else:
        enhanced_matches = []
        for m in jobs_to_show:
            enhanced_matches.append(m if isinstance(m, dict) else m.model_dump())

    return {
        "inference": inf.model_dump(),
        "matches": enhanced_matches,
        "search_summary": {
            "keywords_used": keywords[:3],
            "jobs_considered": len(unique_jobs),
            "sites": sites,
            "location": location,
        },
        "processing_time_ms": (time.perf_counter() - start_time) * 1000,
    }

# Add custom OpenAPI tags metadata
app.openapi_tags = [
    {
        "name": "System",
        "description": "System health and information endpoints",
    },
    {
        "name": "CV Processing",
        "description": "CV parsing and analysis endpoints",
    },
    {
        "name": "Job Search",
        "description": "Job scraping and search endpoints",
    },
    {
        "name": "Job Matching", 
        "description": "CV-to-job matching and analysis endpoints",
    },
    {
        "name": "Scam Detection",
        "description": "Job posting scam detection and verification endpoints",
    },
    {
        "name": "Testing",
        "description": "Testing and debugging utilities",
    }
]

# Job Search Endpoints
@app.post(
    "/api/jobs/search",
    response_model=JobSearchResponse,
    summary="Search Job Postings",
    description="Search for job postings using JobSpy integration",
    tags=["Job Search"]
)
async def search_jobs(request: JobSearchRequest):
    """
    ## Search Job Postings
    
    Search for job postings from multiple sources (LinkedIn, Indeed) using JobSpy.
    
    ### Features:
    - Multi-platform scraping (LinkedIn, Indeed)
    - Real-time job data
    - Detailed job descriptions
    - Salary information (when available)
    - Company and location details
    
    ### Performance:
    - Typical: 10-30 seconds for 10 jobs
    - Concurrent processing for multiple sites
    - Automatic retry on failures
    
    ### Rate Limits:
    - Recommended: Max 50 results per request
    - Avoid too frequent requests to prevent IP blocking
    """
    try:
        response = await search_jobs_async(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Job search failed: {str(e)}"
        )

@app.post(
    "/api/jobs/match",
    response_model=JobMatchResponse,
    summary="Match CV to Jobs",
    description="Match parsed CV profile against job postings using AI similarity",
    tags=["Job Matching"]
)
async def match_cv_jobs(request: JobMatchRequest):
    """
    ## Match CV to Job Postings
    
    Analyze CV profile against job postings and rank by relevance using:
    - Semantic similarity (embeddings + cosine similarity)
    - Skill matching
    - Experience level assessment
    - Company background analysis
    
    ### Matching Algorithm:
    1. **Text Extraction**: Extract relevant text from CV and job descriptions
    2. **Embeddings**: Generate vector embeddings using Gemini
    3. **Similarity**: Calculate cosine similarity between vectors
    4. **Ranking**: Sort jobs by similarity score
    5. **Reasoning**: Generate human-readable match explanations
    
    ### Response Format:
    - Ranked list of job matches (highest similarity first)
    - Similarity scores (0.0-1.0) and percentages (0-100%)
    - Match reasons and explanations
    - Processing metadata
    """
    try:
        response = await match_cv_to_jobs(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Job matching failed: {str(e)}"
        )

@app.post(
    "/api/jobs/verify",
    response_model=ScamResult,
    summary="Verify Job Legitimacy",
    description="Analyze job posting for scam indicators and safety risks",
    tags=["Scam Detection"]
)
async def verify_job(job: JobResult):
    """
    ## Job Scam Detection & Verification
    
    Comprehensive analysis of job postings to detect potential scams and fraud.
    
    ### Detection Methods:
    - **Keyword Analysis**: Financial red flags, urgency tactics, vague descriptions
    - **Pattern Recognition**: Suspicious company names, contact methods
    - **LLM Analysis**: AI-powered detailed assessment
    - **Risk Scoring**: Weighted risk calculation (0-100%)
    
    ### Risk Levels:
    - **SAFE** (0-20%): Low risk, appears legitimate
    - **LOW** (20-40%): Minor concerns, generally safe
    - **MEDIUM** (40-60%): Moderate risk, research recommended
    - **HIGH** (60-80%): High risk, proceed with extreme caution
    - **CRITICAL** (80-100%): Very high risk, likely scam
    
    ### Features:
    - Bilingual detection (English & Indonesian)
    - Detailed safety recommendations
    - Specific scam indicators identified
    - LLM-powered detailed analysis
    """
    try:
        result = await detect_scam(job)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Job verification failed: {str(e)}"
        )

@app.post(
    "/api/jobs/search-and-match",
    summary="Search Jobs and Match to CV",
    description="Combined endpoint: search jobs and match against CV profile",
    tags=["Job Matching"]
)
async def search_and_match_jobs(
    search_request: JobSearchRequest,
    cv_profile: Dict[str, Any],
    include_scam_check: bool = Query(default=True, description="Include scam detection for results"),
    top_matches: int = Query(default=10, ge=1, le=20, description="Number of top matches to return")
):
    """
    ## Search Jobs and Match to CV (Combined)
    
    Convenient endpoint that combines job searching, CV matching, and optional scam detection.
    
    ### Process Flow:
    1. **Search Jobs**: Find job postings based on search criteria
    2. **Match CV**: Calculate similarity scores for all found jobs
    3. **Scam Check**: Analyze jobs for scam indicators (optional)
    4. **Rank Results**: Return top matches with safety information
    
    ### Response Format:
    ```json
    {
      "matches": [
        {
          "job": {...},
          "similarity_score": 0.85,
          "match_percentage": 85.0,
          "match_reasons": ["Skills match: python, sql", "Senior level experience"],
          "scam_result": {
            "risk_level": "safe",
            "risk_percentage": 5.0,
            "recommendations": [...]
          }
        }
      ],
      "search_summary": {...},
      "processing_time_ms": 15000
    }
    ```
    """
    import time
    start_time = time.perf_counter()
    
    try:
        # Step 1: Search for jobs
        search_response = await search_jobs_async(search_request)
        
        if not search_response.jobs:
            return {
                "matches": [],
                "search_summary": search_response,
                "processing_time_ms": (time.perf_counter() - start_time) * 1000,
                "message": "No jobs found for the search criteria"
            }
        
        # Step 2: Match CV to jobs
        match_request = JobMatchRequest(
            cv_profile=cv_profile,
            jobs=search_response.jobs,
            top_k=top_matches
        )
        match_response = await match_cv_to_jobs(match_request)
        
        # Step 3: Optional scam detection
        enhanced_matches = []
        if include_scam_check and match_response.matches:
            scam_results = await detect_scam_batch([match.job for match in match_response.matches])
            
            for match, scam_result in zip(match_response.matches, scam_results):
                enhanced_match = {
                    **match.model_dump(),
                    "scam_result": scam_result.model_dump()
                }
                enhanced_matches.append(enhanced_match)
        else:
            enhanced_matches = [match.model_dump() for match in match_response.matches]
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return {
            "matches": enhanced_matches,
            "search_summary": {
                "total_jobs_found": search_response.total_found,
                "jobs_analyzed": len(match_response.matches),
                "search_params": search_response.search_params.model_dump()
            },
            "cv_summary": match_response.cv_summary,
            "processing_time_ms": processing_time,
            "scam_check_included": include_scam_check
        }
        
    except Exception as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        raise HTTPException(
            status_code=500,
            detail=f"Search and match failed: {str(e)}"
        )


# === MAILRY INTEGRATION ENDPOINTS ===

class SendEmailRequest(BaseModel):
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    text: str = Field(..., description="Plain text email body")
    html: Optional[str] = Field(None, description="HTML email body")
    attachments: Optional[List[Dict[str, str]]] = Field(None, description="Attachments list")


@app.get("/api/mailry/emails", 
         summary="List Sender Emails",
         description="Get list of available sender emails from Mailry",
         tags=["Mailry"])
async def mailry_list_emails():
    """Get list of sender emails from Mailry"""
    try:
        return await list_sender_emails()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")


@app.post("/api/mailry/upload-attachment",
          summary="Upload Attachment", 
          description="Upload file attachment to Mailry",
          tags=["Mailry"])
async def mailry_upload_attachment(file: UploadFile = File(...)):
    """Upload file attachment to Mailry"""
    try:
        content = await file.read()
        return await upload_attachment(
            content, 
            file.filename or "attachment", 
            file.content_type or "application/octet-stream"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload attachment: {str(e)}")


@app.post("/api/mailry/send",
          summary="Send Email",
          description="Send email via Mailry",
          tags=["Mailry"])
async def mailry_send(req: SendEmailRequest):
    """Send email via Mailry"""
    try:
        return await send_email(
            to=req.to,
            subject=req.subject,
            text=req.text,
            html=req.html,
            attachments=req.attachments,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@app.post("/api/mailry/webhook",
          summary="Mailry Webhook",
          description="Receive webhook notifications from Mailry",
          tags=["Mailry"])
async def mailry_webhook(request: Request, x_mailry_signature: str = Header(None)):
    """Handle webhook from Mailry"""
    try:
        raw_body = await request.body()
        
        # Verify signature if configured (optional for testing)
        if x_mailry_signature and not verify_webhook_signature(raw_body, x_mailry_signature):
            logger.warning("Invalid webhook signature, but continuing for testing")
            # raise HTTPException(status_code=401, detail="Invalid signature")
        
        data = await request.json()
        logger.info(f"Received Mailry webhook: {data}")
        
        # Process webhook data
        webhook_type = data.get("type", "")
        
        if webhook_type == "email_reply":
            # Handle email replies (unsubscribe, etc.)
            await _handle_email_reply(data)
        elif webhook_type == "email_bounce":
            # Handle email bounces
            await _handle_email_bounce(data)
        elif webhook_type == "email_delivered":
            # Handle delivery confirmations
            logger.info(f"Email delivered: {data.get('email_id')}")
        else:
            logger.info(f"Unhandled webhook type: {webhook_type}")
        
        return {"ok": True, "message": "Webhook processed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


async def _handle_email_reply(data: Dict[str, Any]):
    """Handle email reply webhook from Mailry"""
    try:
        # Extract reply information
        reply_to = data.get("reply_to", "")
        reply_from = data.get("reply_from", "")
        reply_subject = data.get("reply_subject", "")
        reply_body = data.get("reply_body", "")
        
        logger.info(f"Processing email reply from {reply_from} to {reply_to}")
        logger.info(f"Subject: {reply_subject}")
        logger.info(f"Body: {reply_body[:200]}...")
        
        # Check if this is an unsubscribe request
        if _is_unsubscribe_request(reply_body):
            await _process_unsubscribe(reply_to, reply_from)
        else:
            logger.info(f"Regular reply from {reply_from} - no action needed")
            
    except Exception as e:
        logger.error(f"Failed to handle email reply: {e}")


def _is_unsubscribe_request(reply_body: str) -> bool:
    """Check if reply body contains unsubscribe keywords"""
    if not reply_body:
        return False
    
    # Convert to lowercase for case-insensitive matching
    body_lower = reply_body.lower().strip()
    
    # Common unsubscribe keywords
    unsubscribe_keywords = [
        "stop", "unsubscribe", "cancel", "berhenti", "tolak", "no more",
        "stop sending", "unsubscribe me", "cancel subscription",
        "berhenti kirim", "tolak email", "stop email"
    ]
    
    return any(keyword in body_lower for keyword in unsubscribe_keywords)


async def _process_unsubscribe(email: str, reply_from: str):
    """Process unsubscribe request"""
    try:
        logger.info(f"Processing unsubscribe request for {email}")
        
        # Get subscription
        subscription = subscription_store.get_subscription_by_email(email)
        if not subscription:
            logger.warning(f"No subscription found for {email}")
            return
        
        # Deactivate subscription
        subscription.active = False
        success = subscription_store.update_subscription(subscription)
        
        if success:
            logger.info(f"Successfully unsubscribed {email}")
            
            # Send confirmation email
            await _send_unsubscribe_confirmation(email, reply_from)
        else:
            logger.error(f"Failed to unsubscribe {email}")
            
    except Exception as e:
        logger.error(f"Failed to process unsubscribe: {e}")


async def _send_unsubscribe_confirmation(email: str, reply_from: str):
    """Send confirmation email for successful unsubscribe"""
    try:
        subject = "LokerKerja - Berhenti Berlangganan Berhasil"
        
        text_content = f"""
Halo,

Terima kasih telah menggunakan LokerKerja.

Email {email} telah berhasil dihapus dari daftar berlangganan kami.

Anda tidak akan lagi menerima email lowongan kerja dari LokerKerja.

Jika Anda ingin berlangganan kembali, silakan kunjungi website kami.

Terima kasih,
Tim LokerKerja
        """
        
        html_content = f"""
        <h2>Berhenti Berlangganan Berhasil</h2>
        
        <p>Halo,</p>
        
        <p>Terima kasih telah menggunakan LokerKerja.</p>
        
        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 15px 0;">
            <p><strong>Email {email} telah berhasil dihapus dari daftar berlangganan kami.</strong></p>
        </div>
        
        <p>Anda tidak akan lagi menerima email lowongan kerja dari LokerKerja.</p>
        
        <p>Jika Anda ingin berlangganan kembali, silakan kunjungi website kami.</p>
        
        <p>Terima kasih,<br>
        Tim LokerKerja</p>
        """
        
        # Send confirmation email
        from integrations.mailry import send_email, _create_email_template
        html = _create_email_template(html_content)
        
        result = await send_email(
            to=email,
            subject=subject,
            text=text_content,
            html=html
        )
        
        logger.info(f"Unsubscribe confirmation sent to {email}: {result}")
        
    except Exception as e:
        logger.error(f"Failed to send unsubscribe confirmation: {e}")


async def _handle_email_bounce(data: Dict[str, Any]):
    """Handle email bounce webhook from Mailry"""
    try:
        bounce_to = data.get("bounce_to", "")
        bounce_reason = data.get("bounce_reason", "")
        
        logger.warning(f"Email bounce for {bounce_to}: {bounce_reason}")
        
        # Optionally deactivate subscription for hard bounces
        if "hard" in bounce_reason.lower() or "permanent" in bounce_reason.lower():
            subscription = subscription_store.get_subscription_by_email(bounce_to)
            if subscription:
                subscription.active = False
                subscription_store.update_subscription(subscription)
                logger.info(f"Deactivated subscription for {bounce_to} due to hard bounce")
                
    except Exception as e:
        logger.error(f"Failed to handle email bounce: {e}")


# === SUBSCRIPTION MANAGEMENT ENDPOINTS ===

@app.post("/api/subscriptions",
          response_model=SubscriptionResponse,
          summary="Create/Update Subscription",
          description="Create or update job alert subscription",
          tags=["Subscriptions"])
async def create_subscription(req: SubscriptionRequest):
    """Create or update job alert subscription"""
    try:
        # Check if subscription already exists
        existing = subscription_store.get_subscription_by_email(req.email)
        
        if existing:
            # Update existing subscription
            existing.user_name = req.user_name or existing.user_name
            existing.preferences = req.preferences
            existing.frequency = req.frequency
            existing.top_n = req.top_n
            existing.alert_threshold = req.alert_threshold
            existing.enable_matching = req.enable_matching
            existing.enable_scam_check = req.enable_scam_check
            existing.active = True  # Reactivate if was paused
            
            success = subscription_store.update_subscription(existing)
            if success:
                return SubscriptionResponse(
                    success=True,
                    message="Subscription updated successfully",
                    subscription=existing
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to update subscription")
        else:
            # Create new subscription
            subscription = Subscription(
                email=req.email,
                user_name=req.user_name,
                preferences=req.preferences,
                frequency=req.frequency,
                top_n=req.top_n,
                alert_threshold=req.alert_threshold,
                enable_matching=req.enable_matching,
                enable_scam_check=req.enable_scam_check
            )
            
            subscription_id = subscription_store.create_subscription(subscription)
            subscription.id = subscription_id
            
            return SubscriptionResponse(
                success=True,
                message="Subscription created successfully", 
                subscription=subscription
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create/update subscription: {str(e)}")


@app.get("/api/subscriptions/me",
         response_model=Optional[Subscription],
         summary="Get My Subscription",
         description="Get subscription by email (query parameter)",
         tags=["Subscriptions"])
async def get_my_subscription(email: str = Query(..., description="User email address")):
    """Get subscription by email"""
    try:
        subscription = subscription_store.get_subscription_by_email(email)
        return subscription
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch subscription: {str(e)}")


@app.patch("/api/subscriptions/{subscription_id}",
           response_model=SubscriptionResponse,
           summary="Update Subscription",
           description="Update subscription preferences or status",
           tags=["Subscriptions"])
async def update_subscription_by_id(subscription_id: str, req: SubscriptionRequest):
    """Update subscription by ID"""
    try:
        # For simplicity, we'll use email-based lookup since that's our primary key
        existing = subscription_store.get_subscription_by_email(req.email)
        
        if not existing:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        existing.user_name = req.user_name or existing.user_name
        existing.preferences = req.preferences
        existing.frequency = req.frequency
        existing.top_n = req.top_n
        existing.alert_threshold = req.alert_threshold
        existing.enable_matching = req.enable_matching
        existing.enable_scam_check = req.enable_scam_check
        
        success = subscription_store.update_subscription(existing)
        if success:
            return SubscriptionResponse(
                success=True,
                message="Subscription updated successfully",
                subscription=existing
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update subscription")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update subscription: {str(e)}")


@app.post("/api/subscriptions/{subscription_id}/pause",
          response_model=SubscriptionResponse,
          summary="Pause Subscription",
          description="Pause job alert subscription",
          tags=["Subscriptions"])
async def pause_subscription(subscription_id: str, email: str = Query(...)):
    """Pause subscription"""
    try:
        subscription = subscription_store.get_subscription_by_email(email)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        subscription.active = False
        success = subscription_store.update_subscription(subscription)
        
        if success:
            return SubscriptionResponse(
                success=True,
                message="Subscription paused successfully",
                subscription=subscription
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to pause subscription")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause subscription: {str(e)}")


@app.get("/api/subscriptions/unsubscribe",
         summary="Unsubscribe",
         description="Unsubscribe using token from email link",
         tags=["Subscriptions"])
async def unsubscribe(token: str = Query(..., description="Unsubscribe token")):
    """Unsubscribe using token"""
    try:
        subscription = subscription_store.get_subscription_by_token(token)
        if not subscription:
            raise HTTPException(status_code=404, detail="Invalid unsubscribe token")
        
        subscription.active = False
        subscription.frequency = FrequencyType.DISABLED
        success = subscription_store.update_subscription(subscription)
        
        if success:
            return HTMLResponse("""
            <html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>Unsubscribed Successfully</h2>
                <p>You have been unsubscribed from LokerKerja job alerts.</p>
                <p>You can resubscribe anytime by using our service again.</p>
            </body></html>
            """)
        else:
            raise HTTPException(status_code=500, detail="Failed to unsubscribe")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe: {str(e)}")


@app.post("/api/subscriptions/test-newsletter",
          summary="Test Newsletter (Demo)",
          description="Manually trigger newsletter sending for testing",
          tags=["Subscriptions"])
async def test_newsletter(email: str = Query(None, description="Test specific email (optional)")):
    """Test newsletter sending immediately"""
    try:
        # Import scheduler here to avoid circular imports
        from scheduler import JobAlertScheduler
        
        # Create scheduler instance
        scheduler = JobAlertScheduler()
        
        # Run test
        result = await scheduler.test_newsletter_now(email)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test newsletter failed: {str(e)}")


@app.get("/api/subscriptions/dashboard",
         summary="Subscription Dashboard",
         description="View subscription statistics and database status",
         tags=["Subscriptions"])
async def subscription_dashboard():
    """Get subscription dashboard with statistics"""
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data/subscriptions.db")
        
        if not db_path.exists():
            return {
                "database_exists": False,
                "total_subscriptions": 0,
                "active_subscriptions": 0,
                "recent_subscriptions": [],
                "message": "No subscriptions database found"
            }
        
        # Get stats from database
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Total subscriptions
            cursor.execute("SELECT COUNT(*) as total FROM subscriptions")
            total_subs = cursor.fetchone()["total"]
            
            # Active subscriptions
            cursor.execute("SELECT COUNT(*) as active FROM subscriptions WHERE active = 1")
            active_subs = cursor.fetchone()["active"]
            
            # Recent subscriptions (last 10)
            cursor.execute("""
                SELECT email, user_name, created_at, frequency, active
                FROM subscriptions 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            recent = [dict(row) for row in cursor.fetchall()]
            
            # Frequency distribution
            cursor.execute("""
                SELECT frequency, COUNT(*) as count 
                FROM subscriptions 
                WHERE active = 1
                GROUP BY frequency
            """)
            freq_dist = [dict(row) for row in cursor.fetchall()]
            
        return {
            "database_exists": True,
            "total_subscriptions": total_subs,
            "active_subscriptions": active_subs,
            "recent_subscriptions": recent,
            "frequency_distribution": freq_dist,
            "database_path": str(db_path)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard failed: {str(e)}")


# === ENHANCED SMART DISCOVERY WITH EMAIL OPTION ===

@app.post("/api/jobs/smart-discovery-with-email",
          summary="Smart Discovery + Email",
          description="Smart job discovery with optional email delivery",
          tags=["Jobs", "AI"])
async def smart_discovery_with_email(
    background_tasks: BackgroundTasks,
    cv_profile: Optional[Dict[str, Any]] = None,
    position_inference: Optional[Dict[str, Any]] = None,
    email_to: str = Query(None, description="Email address to send results to"),
    user_name: str = Query(None, description="User name for email"),
    location: str = Query("Indonesia", description="Job search location"),
    sites: List[str] = Query(["linkedin", "indeed"], description="Job sites to search"),
    results_wanted: int = Query(20, description="Number of jobs to find"),
    include_scam_check: bool = Query(False, description="Include scam detection"),
    top_matches: int = Query(10, description="Number of top matches to return"),
    language: str = Query("en", description="Language for AI processing"),
    enable_matching: bool = Query(False, description="Enable AI job matching"),
    subscribe_alerts: bool = Query(False, description="Subscribe to job alerts"),
    alert_frequency: FrequencyType = Query(FrequencyType.WEEKLY, description="Alert frequency")
):
    """Enhanced smart discovery with email and subscription options"""
    start_time = time.perf_counter()
    
    # Run the regular smart discovery
    try:
        # Call the existing endpoint logic (simplified)
        if not cv_profile:
            raise HTTPException(status_code=400, detail="cv_profile is required")
        
        # Position inference
        if not position_inference or not isinstance(position_inference, dict):
            inference_request = PositionInferenceRequest(
                cv_profile=cv_profile,
                top_alternates=2,
                allow_freshgrad_bias=True,
                language=language,
                user_preferences=None,
            )
            position_inference_result = await infer_position_from_cv(
                cv_profile=inference_request.cv_profile,
                top_alternates=inference_request.top_alternates,
                allow_freshgrad_bias=inference_request.allow_freshgrad_bias,
                language=inference_request.language,
                user_preferences=inference_request.user_preferences,
            )
            position_inference = position_inference_result.model_dump()
        else:
            print(f"DEBUG - Using provided position_inference: {position_inference}")
        
        # Job search
        # Dynamic keyword extraction from position inference
        def get_search_keyword(pi: Dict[str, Any], cv_prof: Dict[str, Any]) -> str:
            print(f"DEBUG - get_search_keyword received pi: {pi}")
            
            # Try position inference first
            # Check ai_recommendations structure first
            air = pi.get('ai_recommendations') or {}
            if air.get('primary_role'):
                keyword = str(air['primary_role'])
                print(f"DEBUG - Using ai_recommendations.primary_role: {keyword}")
                return keyword
             
            # Try direct primary_role (fallback)
            if pi.get('primary_role'):
                keyword = str(pi['primary_role'])
                print(f"DEBUG - Using direct primary_role: {keyword}")
                return keyword
            
            # Try position_title
            if pi.get('position_title'):
                keyword = str(pi['position_title'])
                print(f"DEBUG - Using position_title: {keyword}")
                return keyword
            
            # Try alternates if available
            alternates = air.get('alternates') or pi.get('alternates') or []
            if alternates and isinstance(alternates, list) and alternates:
                keyword = str(alternates[0])
                print(f"DEBUG - Using first alternate: {keyword}")
                return keyword
            
            # Try search_keywords
            search_keywords = pi.get('search_keywords') or []
            if search_keywords and isinstance(search_keywords, list) and search_keywords:
                keyword = str(search_keywords[0])
                print(f"DEBUG - Using first search_keyword: {keyword}")
                return keyword
             
            # Try user selections
            us = pi.get('user_selections') or {}
            if us.get('selected_role'):
                keyword = str(us['selected_role'])
                print(f"DEBUG - Using user_selections.selected_role: {keyword}")
                return keyword
             
            # Fallback to CV profile analysis
            if cv_prof:
                # Check latest experience role
                experience = cv_prof.get("experience", [])
                if experience and isinstance(experience, list):
                    latest_role = experience[0].get("role") if experience[0] else None
                    if latest_role:
                        keyword = str(latest_role)
                        print(f"DEBUG - Using latest experience role: {keyword}")
                        return keyword
                 
                # Check skills for common patterns
                skills = cv_prof.get("skills", [])
                if isinstance(skills, list) and skills:
                    # Use skills directly as search keywords instead of hardcoded mappings
                    relevant_skills = [skill for skill in skills if len(skill) > 2][:3]  # Top 3 meaningful skills
                    if relevant_skills:
                        keyword = f"{relevant_skills[0]} specialist"
                        print(f"DEBUG - Using skills-based dynamic fallback: {keyword}")
                        return keyword
             
            # Final fallback
            print(f"DEBUG - Using final fallback: jobs")
            return "jobs"
        
        search_keyword = get_search_keyword(position_inference, cv_profile)
        
        search_request = JobSearchRequest(
            keyword=search_keyword,
            location=location,
            results_wanted=results_wanted,
            sites=sites,
            linkedin_fetch_description=True
        )
        
        search_response = await search_jobs_async(search_request)
        
        if not search_response.jobs:
            jobs_to_display = []
            enhanced_matches = []
        else:
            if enable_matching:
                # AI matching
                match_request = JobMatchRequest(
                    cv_profile=cv_profile,
                    jobs=search_response.jobs,
                    top_k=top_matches
                )
                match_response = await match_cv_to_jobs(match_request)
                enhanced_matches = [match.model_dump() for match in match_response.matches]
                jobs_to_display = enhanced_matches
            else:
                # No matching, just return all jobs
                jobs_to_display = [job.model_dump() for job in search_response.jobs[:top_matches]]
                enhanced_matches = jobs_to_display
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        result: Dict[str, Any] = {
            "matches": enhanced_matches,
            "search_summary": {
                "total_jobs_found": search_response.total_found,
                "jobs_analyzed": len(enhanced_matches),
                "search_params": search_response.search_params.model_dump()
            },
            "position_inference": position_inference,
            "processing_time_ms": processing_time,
            "email_sent": False,
            "subscription_created": False
        }
        
        subscription_created = False
        is_new_subscription = False
        if subscribe_alerts and email_to:
            try:
                subscription_id, is_new_subscription = await subscription_service.create_subscription_from_smart_discovery(
                    email=email_to,
                    user_name=user_name,
                    cv_profile=cv_profile,
                    position_inference=position_inference,
                    frequency=alert_frequency,
                    locations=[location],
                    sites=sites
                )
                subscription_created = True
                result["subscription_created"] = True
                result["subscription_id"] = subscription_id
                result["is_new_subscription"] = is_new_subscription
                
                # Send welcome email with job samples ONLY for new subscriptions
                if enhanced_matches and is_new_subscription:
                    background_tasks.add_task(
                        send_welcome_subscription_email,
                        to=email_to,
                        user_name=user_name or "User",
                        position_title=search_keyword,
                        frequency=alert_frequency.value if hasattr(alert_frequency, 'value') else str(alert_frequency),
                        jobs=[m.get("job", m) if isinstance(m, dict) else m.job for m in enhanced_matches],
                        top_n=min(5, len(enhanced_matches))
                    )
                    result["email_sent"] = True
                    result["email_type"] = "welcome_with_jobs"
                elif not is_new_subscription:
                    result["email_sent"] = False
                    result["email_type"] = "subscription_updated"
                
            except Exception as e:
                logger.warning(f"Failed to create subscription: {e}")
        
        # Send regular job results email if no subscription but email requested
        if email_to and enhanced_matches and not subscription_created:
            try:
                background_tasks.add_task(
                    send_job_results_email,
                    to=email_to,
                    user_name=user_name or "User", 
                    position_title=search_keyword,
                    location=location,
                    jobs=[m.get("job", m) if isinstance(m, dict) else m.job for m in enhanced_matches],
                    top_n=min(10, len(enhanced_matches))
                )
                result["email_sent"] = True
                result["email_type"] = "job_results"
            except Exception as e:
                logger.warning(f"Failed to queue email: {e}")
         
        return result
        
    except Exception as e:
        processing_time = (time.perf_counter() - start_time) * 1000
        raise HTTPException(
            status_code=500,
            detail=f"Enhanced smart discovery failed: {str(e)}"
        )
