from typing import List

from pydantic_ai import Agent

from app.models.Response import AnalysisResponse

PROMPT = """  
...
"""

leiloai_agent = Agent(
    "google-gla:gemini-2.5-pro",
    output_type=AnalysisResponse,
    system_prompt=PROMPT,
    retries=3
)