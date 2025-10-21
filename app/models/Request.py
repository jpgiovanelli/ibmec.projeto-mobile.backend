from typing import List, Dict
from fastapi import UploadFile
from pydantic import BaseModel


class QuizQuestion(BaseModel):
    question: str
    answer: str


class CreateAnalysisRequest(BaseModel):
    questions: List[QuizQuestion]
    images: List[UploadFile]
    others: List[Dict[str, str]]