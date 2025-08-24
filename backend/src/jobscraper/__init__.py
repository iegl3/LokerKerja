from .scraper import search_jobs_async, JobSearchRequest, JobResult, JobSearchResponse
from .matcher import calculate_similarity, match_cv_to_jobs, JobMatchRequest, JobMatchResponse
from .scam_detector import detect_scam, detect_scam_batch, ScamResult
from .position_inference import (
	PositionInferenceRequest,
	PositionInferenceResult,
	infer_position_from_cv,
	UserPreferences,
	AIRecommendations,
	UserSelections,
)

__all__ = [
	"search_jobs_async",
	"JobSearchRequest", 
	"JobResult",
	"JobSearchResponse",
	"calculate_similarity",
	"match_cv_to_jobs",
	"JobMatchRequest",
	"JobMatchResponse",
	"detect_scam",
	"detect_scam_batch",
	"ScamResult",
	"PositionInferenceRequest",
	"PositionInferenceResult",
	"infer_position_from_cv",
	"UserPreferences",
	"AIRecommendations",
	"UserSelections",
] 