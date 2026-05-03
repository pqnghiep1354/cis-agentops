"""CIS AgentOps — Output Schema (Pydantic v2)"""
from pydantic import BaseModel, field_validator
from typing import List


class TourContentOutput(BaseModel):
    title: str
    tagline: str
    description: str
    highlights: List[str]
    seo_meta_title: str
    seo_meta_description: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError("title too short")
        return v.strip()

    @field_validator("description")
    @classmethod
    def desc_min_length(cls, v):
        words = v.split()
        if len(words) < 50:
            raise ValueError(f"description too short ({len(words)} words)")
        return v

    @field_validator("highlights")
    @classmethod
    def at_least_three(cls, v):
        if len(v) < 3:
            raise ValueError("need at least 3 highlights")
        return v

    @field_validator("seo_meta_title")
    @classmethod
    def meta_title_length(cls, v):
        if len(v) > 60:
            raise ValueError("meta title exceeds 60 chars")
        return v

    @field_validator("seo_meta_description")
    @classmethod
    def meta_desc_length(cls, v):
        if len(v) > 155:
            raise ValueError("meta description exceeds 155 chars")
        return v
