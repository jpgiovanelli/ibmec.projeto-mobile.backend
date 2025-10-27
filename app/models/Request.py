from typing import List, Dict, Optional
from fastapi import UploadFile
from pydantic import BaseModel
from pydantic_ai import BinaryContent


class QuizQuestion(BaseModel):
    question: str
    answer: str


class SkinProfileRequest(BaseModel):
    questions: List[QuizQuestion]
    others: List[Dict[str, str]]

class AIRequest(BaseModel):
    skin_profile: SkinProfileRequest
    images: Optional[List[BinaryContent]] = None