from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, field_validator


class EmotionScores(BaseModel):
    joy: float
    sadness: float
    anger: float
    calm: float
    anxiety: float
    expectation: float


class VideoAnalysisResult(BaseModel):
    emotions: EmotionScores
    risk_score: float
    keywords: List[str]
    suggestions: str
    category: Optional[str] = "其他"


class VideoAnalysisResponse(BaseModel):
    id: int
    file_name: str
    emotions: Dict[str, float]
    risk_score: float
    keywords: List[str]
    suggestions: str
    suggestions_detail: Optional[Dict[str, Any]] = None
    category: Optional[str] = "其他"
    counter_analysis: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("emotions", mode="before")
    @classmethod
    def coerce_emotions(cls, v: Any) -> Dict[str, float]:
        if not isinstance(v, dict):
            return {}
        return {str(k): float(vv) for k, vv in v.items()}

    @field_validator("keywords", mode="before")
    @classmethod
    def coerce_keywords(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        return [str(item) for item in v]


class VideoAnalysisCreate(BaseModel):
    file_name: str
    file_path: str
    result: VideoAnalysisResult
