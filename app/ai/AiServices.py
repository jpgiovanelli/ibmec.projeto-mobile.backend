from typing import List

from pydantic_ai import Agent

from app.models.Request import SkinProfileRequest, AIRequest
from app.models.Response import AnalysisResponse

PROMPT = """  
Você é um dermatologista altamente experiente, especializado em cuidados com a pele do rosto.
Receberá perguntas, respostas e imagens de um paciente relacionadas à saúde e estética facial.
Com base nessas informações, deve analisar cuidadosamente e responder seguindo exatamente o modelo de resposta fornecido, utilizando uma linguagem técnica, empática e profissional, adequada à prática dermatológica.
Suas respostas devem ser claras, objetivas e baseadas em evidências clínicas, considerando aspectos como diagnóstico diferencial, possíveis causas, tratamento recomendado e orientações preventivas.
"""

dermage_agent = Agent(
    "google-gla:gemini-2.5-pro",
    deps_type=SkinProfileRequest,
    output_type=AnalysisResponse,
    system_prompt=PROMPT,
    retries=3
)

async def analyze_skin(ai_request: AIRequest) -> AnalysisResponse:
    deps = ai_request.skin_profile

    result = await dermage_agent.run(ai_request.images, deps=deps)

    return AnalysisResponse.model_validate(result.output())
