from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

class SkinCareProduct(BaseModel):
    title: str
    description: str
    price: float
    image_url: str
    link: str
    sku: Optional[str] = None
    category: Optional[str] = None

class SkinCareRoutine(BaseModel):
    morning: List[SkinCareProduct]
    night: List[SkinCareProduct]

class SkinTypes(Enum):
    SECA = "seca"
    MISTA = "mista"
    OLEOSA = "oleosa"
    NORMAL = "normal"

class SkinScore(BaseModel):
    score_tag: str
    score_number: float

class AnalysisResponse(BaseModel):
    scores: List[SkinScore]
    concerns: str
    skin_type: SkinTypes
    routine: SkinCareRoutine

