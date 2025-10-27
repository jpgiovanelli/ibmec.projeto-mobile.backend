from typing import List, Dict, Optional
from fastapi import UploadFile
from pydantic import BaseModel
from pydantic_ai import BinaryContent


class QuizQuestion(BaseModel):
    question: str
    answer: str


class CreateAnalysisRequest(BaseModel):
    questions: List[QuizQuestion]
    images: Optional[List[BinaryContent]] = None
    others: List[Dict[str, str]]