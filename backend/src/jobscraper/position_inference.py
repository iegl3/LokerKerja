import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from cv_handler.config import LUNOS, SEM_LUNOS, TEXT_MODEL

logger = logging.getLogger(__name__)


class UserPreferences(BaseModel):
    """User preferences for position inference"""
    seniority_override: Optional[str] = Field(None, description="User-specified seniority: intern, junior, mid, senior, lead, manager")
    role_override: Optional[str] = Field(None, description="User-specified role override")
    role_preference_index: Optional[int] = Field(None, ge=0, le=2, description="Index of preferred AI suggestion: 0=primary, 1=alt1, 2=alt2")


class PositionInferenceRequest(BaseModel):
    """Request body for position inference from CV."""
    cv_profile: Dict[str, Any] = Field(..., description="Parsed CV profile data")
    top_alternates: int = Field(default=2, ge=0, le=3, description="Number of alternate roles to suggest (0-3)")
    allow_freshgrad_bias: bool = Field(default=True, description="Bias toward junior/intern roles if experience is limited")
    language: str = Field(default="en", description="Language for role naming: 'en' or 'id'")
    user_preferences: Optional[UserPreferences] = Field(None, description="User preferences to override AI suggestions")


class AIRecommendations(BaseModel):
    """AI-generated recommendations"""
    primary_role: str = Field(..., description="AI's primary role recommendation")
    alternates: List[str] = Field(default_factory=list, description="AI's alternative role suggestions")
    seniority: str = Field("unspecified", description="AI's seniority assessment")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="AI confidence score")
    search_keywords: List[str] = Field(default_factory=list, description="AI-generated search keywords")


class UserSelections(BaseModel):
    """Final user selections after applying preferences"""
    selected_role: str = Field(..., description="Final role after user preferences")
    selected_seniority: str = Field(..., description="Final seniority after user preferences")
    selection_method: str = Field(..., description="How the selection was made: ai_primary, ai_alternate_N, user_override_role, user_override_seniority")
    final_search_keywords: List[str] = Field(default_factory=list, description="Final keywords for job search")


class PositionInferenceResult(BaseModel):
    """Enhanced position inference result with user control"""
    ai_recommendations: AIRecommendations = Field(..., description="AI-generated suggestions")
    user_selections: UserSelections = Field(..., description="Final selections after user preferences")
    
    # Backward compatibility fields
    primary_role: str = Field(..., description="Final selected role (for backward compatibility)")
    alternates: List[str] = Field(default_factory=list, description="Alternative roles (for backward compatibility)")
    seniority: str = Field("unspecified", description="Final seniority (for backward compatibility)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="AI confidence (for backward compatibility)")
    search_keywords: List[str] = Field(default_factory=list, description="Final search keywords (for backward compatibility)")


def _compose_cv_summary(cv: Dict[str, Any]) -> str:
    parts: List[str] = []
    if cv.get("summary"):
        parts.append(str(cv["summary"]))
    skills = cv.get("skills") or []
    if skills:
        parts.append("Skills: " + ", ".join(map(str, skills)))
    exp = cv.get("experience") or []
    for e in exp[:5]:
        role = e.get("role")
        company = e.get("company")
        bullets = e.get("bullets") or []
        line_parts: List[str] = []
        if role:
            line_parts.append(str(role))
        if company:
            line_parts.append(f"at {company}")
        if line_parts:
            parts.append(" ".join(line_parts))
        for b in bullets[:2]:
            parts.append(str(b))
    edu = cv.get("education") or []
    for ed in edu[:2]:
        degree = ed.get("degree")
        school = ed.get("school")
        ed_parts: List[str] = []
        if degree:
            ed_parts.append(str(degree))
        if school:
            ed_parts.append(f"from {school}")
        if ed_parts:
            parts.append(" ".join(ed_parts))
    total_months = cv.get("total_duration_months")
    if total_months:
        parts.append(f"Total experience months: {total_months}")
    return ". ".join(parts)[:5000]


def _apply_user_preferences(
    ai_recommendations: AIRecommendations, 
    user_preferences: Optional[UserPreferences]
) -> UserSelections:
    """Apply user preferences to AI recommendations"""
    
    if not user_preferences:
        # No user preferences, use AI primary
        return UserSelections(
            selected_role=ai_recommendations.primary_role,
            selected_seniority=ai_recommendations.seniority,
            selection_method="ai_primary",
            final_search_keywords=ai_recommendations.search_keywords
        )
    
    selected_role = ai_recommendations.primary_role
    selection_method = "ai_primary"
    
    # Handle role selection
    if user_preferences.role_override:
        # User specified a custom role
        selected_role = user_preferences.role_override
        selection_method = "user_override_role"
    elif user_preferences.role_preference_index is not None:
        # User selected an AI alternative
        if user_preferences.role_preference_index == 0:
            selected_role = ai_recommendations.primary_role
            selection_method = "ai_primary"
        elif user_preferences.role_preference_index == 1 and len(ai_recommendations.alternates) > 0:
            selected_role = ai_recommendations.alternates[0]
            selection_method = "ai_alternate_1"
        elif user_preferences.role_preference_index == 2 and len(ai_recommendations.alternates) > 1:
            selected_role = ai_recommendations.alternates[1]
            selection_method = "ai_alternate_2"
    
    # Handle seniority selection
    selected_seniority = ai_recommendations.seniority
    if user_preferences.seniority_override:
        selected_seniority = user_preferences.seniority_override.lower()
        if selection_method.startswith("ai_"):
            selection_method += "_seniority_override"
        elif selection_method == "user_override_role":
            selection_method = "user_override_both"
    
    # Generate final search keywords
    final_keywords = []
    if selected_seniority in ["intern", "junior"] and selected_seniority not in selected_role.lower():
        final_keywords.append(f"{selected_seniority.title()} {selected_role}")
    final_keywords.append(selected_role)
    final_keywords.extend(ai_recommendations.search_keywords[:3])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for kw in final_keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique_keywords.append(kw)
    
    return UserSelections(
        selected_role=selected_role,
        selected_seniority=selected_seniority,
        selection_method=selection_method,
        final_search_keywords=unique_keywords[:5]
    )


async def infer_position_from_cv(
    cv_profile: Dict[str, Any],
    top_alternates: int = 2,
    allow_freshgrad_bias: bool = True,
    language: str = "en",
    user_preferences: Optional[UserPreferences] = None,
) -> PositionInferenceResult:
    """
    Infer the most suitable position title(s) from a CV profile using LLM with user preferences.
    """
    cv_text = _compose_cv_summary(cv_profile)

    prompt = (
        "You are a career advisor. From the CV content below, infer the best-suited job position.\n"
        "Be selective and realistic based on skills and experience, but inclusive for fresh graduates.\n"
        "If experience < 24 months, prefer junior/intern/associate variants.\n"
        "Return STRICT JSON with these keys only:\n"
        "{\n"
        '  "primary_role": string,\n'
        '  "alternates": [string, ...],\n'
        '  "seniority": string,\n'
        '  "confidence": number,\n'
        '  "search_keywords": [string, ...]\n'
        "}\n"
        f"Language for role naming: {language}.\n\n"
        "CV CONTENT:\n"
        f"{cv_text}\n\n"
        f"Limit alternates to {top_alternates}.\n"
        "Do not add explanations, output JSON only."
    )

    async with SEM_LUNOS:
        try:
            response = await LUNOS.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1,
            )
            raw = (response.choices[0].message.content or "").strip()
            data: Optional[Dict[str, Any]] = None
            try:
                data = json.loads(raw)
            except Exception:
                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        data = json.loads(raw[start : end + 1])
                    except Exception:
                        data = None

            if not isinstance(data, dict):
                logger.warning("Position inference JSON parsing failed; returning fallback")
                fallback_ai = AIRecommendations(
                    primary_role="N/A",
                    alternates=[],
                    seniority="unspecified",
                    confidence=0.0,
                    search_keywords=[],
                )
                fallback_user = _apply_user_preferences(fallback_ai, user_preferences)
                return PositionInferenceResult(
                    ai_recommendations=fallback_ai,
                    user_selections=fallback_user,
                    primary_role=fallback_user.selected_role,
                    alternates=fallback_ai.alternates,
                    seniority=fallback_user.selected_seniority,
                    confidence=fallback_ai.confidence,
                    search_keywords=fallback_user.final_search_keywords,
                )

            months = int((cv_profile or {}).get("total_duration_months") or 0)
            if allow_freshgrad_bias and months < 24:
                kws = [k.strip() for k in (data.get("search_keywords") or []) if isinstance(k, str)]
                primary = (data.get("primary_role") or "").strip()
                lowered = primary.lower()
                if primary and all(s not in lowered for s in ["intern", "junior", "associate"]):
                    if language == "en":
                        kws = [f"Junior {primary}"] + kws
                    else:
                        kws = [f"{primary} Junior"] + kws
                data["search_keywords"] = kws[:5]

            # Create AI recommendations
            ai_recommendations = AIRecommendations(
                primary_role=(data.get("primary_role") or "N/A").strip(),
                alternates=[s for s in (data.get("alternates") or []) if isinstance(s, str)][: max(0, top_alternates)],
                seniority=(data.get("seniority") or "unspecified").strip().lower(),
                confidence=float(data.get("confidence") or 0.0),
                search_keywords=[s for s in (data.get("search_keywords") or []) if isinstance(s, str)][:5],
            )
            
            # Apply user preferences
            user_selections = _apply_user_preferences(ai_recommendations, user_preferences)
            
            result = PositionInferenceResult(
                ai_recommendations=ai_recommendations,
                user_selections=user_selections,
                # Backward compatibility
                primary_role=user_selections.selected_role,
                alternates=ai_recommendations.alternates,
                seniority=user_selections.selected_seniority,
                confidence=ai_recommendations.confidence,
                search_keywords=user_selections.final_search_keywords,
            )
            
            logger.info(f"Position inference: AI={ai_recommendations.primary_role}, User={user_selections.selected_role} ({ai_recommendations.confidence:.2f} confidence, method={user_selections.selection_method})")
            return result
            
        except Exception as e:
            logger.error(f"Position inference error: {e}")
            fallback_ai = AIRecommendations(
                primary_role="N/A",
                alternates=[],
                seniority="unspecified",
                confidence=0.0,
                search_keywords=[],
            )
            fallback_user = _apply_user_preferences(fallback_ai, user_preferences)
            return PositionInferenceResult(
                ai_recommendations=fallback_ai,
                user_selections=fallback_user,
                primary_role=fallback_user.selected_role,
                alternates=fallback_ai.alternates,
                seniority=fallback_user.selected_seniority,
                confidence=fallback_ai.confidence,
                search_keywords=fallback_user.final_search_keywords,
            ) 
