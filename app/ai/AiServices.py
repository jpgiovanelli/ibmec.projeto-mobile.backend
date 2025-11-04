from typing import List

from pydantic_ai import Agent

from app.models.Request import SkinProfileRequest, AIRequest
from app.models.Response import AnalysisResponse
from app.ai.ProductRecommendation import product_service

PROMPT = """  
Você é um dermatologista altamente experiente, especializado em cuidados com a pele do rosto.
Receberá perguntas, respostas e imagens de um paciente relacionadas à saúde e estética facial.
Com base nessas informações, deve analisar cuidadosamente e responder seguindo exatamente o modelo de resposta fornecido, utilizando uma linguagem técnica, empática e profissional, adequada à prática dermatológica.
Suas respostas devem ser claras, objetivas e baseadas em evidências clínicas, considerando aspectos como diagnóstico diferencial, possíveis causas, tratamento recomendado e orientações preventivas.

IMPORTANTE: Você receberá uma lista de produtos disponíveis para recomendação. 
- Use APENAS os produtos fornecidos na lista
- Recomende produtos adequados ao tipo de pele identificado (SECA, MISTA, OLEOSA ou NORMAL)
- Organize os produtos em rotinas de manhã (morning) e noite (night)
- Para cada produto recomendado, preencha os campos:
  * title: nome exato do produto
  * description: descrição fornecida
  * price: 0.0 (será preenchido posteriormente)
  * image_url: URL da imagem fornecida no campo "image"
  * link: URL fornecida no campo "url"
  * sku: código SKU do produto
  * category: categoria do produto
- Priorize produtos das categorias: Limpeza, Hidratação/Sérum, Proteção Solar (manhã), Tratamento (noite)
- Organize a rotina de forma lógica: manhã (limpeza → tratamento → protetor solar) e noite (limpeza → tratamento → hidratação)
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
    
    # Concatena todas as respostas do usuário para análise
    user_responses = " ".join([q.answer for q in deps.questions])
    
    # Obtém informações sobre a recomendação (idade e complexidade)
    recommendation_info = product_service.get_recommendation_info(user_responses)
    age_group = recommendation_info["age_group"]
    routine_type = recommendation_info["routine_type"]
    
    # Faz a análise inicial para identificar o tipo de pele
    initial_result = await dermage_agent.run(ai_request.images, deps=deps)
    initial_analysis = AnalysisResponse.model_validate(initial_result.output)
    
    # Mapeia o tipo de pele para o formato dos CSVs
    skin_type_map = {
        "seca": "SECA",
        "mista": "MISTA",
        "oleosa": "OLEOSA",
        "normal": "NORMAL"
    }
    skin_type = skin_type_map.get(initial_analysis.skin_type.value, "NORMAL")
    
    # Carrega os produtos apropriados
    products = product_service.load_routine(skin_type, routine_type, age_group)
    
    # Se não houver produtos, retorna a análise inicial
    if not products:
        print(f"⚠️ Nenhum produto encontrado para: {skin_type} - {routine_type} - Idade {age_group}")
        return initial_analysis
    
    # Formata os produtos para a IA
    products_context = product_service.format_products_for_ai(products)
    
    # Cria um prompt enriquecido com os produtos
    enhanced_prompt = f"""{PROMPT}

{products_context}

INSTRUÇÕES ESPECÍFICAS PARA ESTA ANÁLISE:
- Tipo de pele identificado: {skin_type}
- Faixa etária: {recommendation_info["age_description"]}
- Complexidade da rotina: {routine_type}
- Recomende produtos APENAS da lista acima
- Garanta que cada produto tenha todos os campos preenchidos corretamente
- Organize em rotina de manhã (morning) e noite (night)
- Explique brevemente por que cada produto é adequado para o tipo de pele e idade
"""
    
    # Cria um novo agente com o prompt enriquecido
    enhanced_agent = Agent(
        "google-gla:gemini-2.5-pro",
        deps_type=SkinProfileRequest,
        output_type=AnalysisResponse,
        system_prompt=enhanced_prompt,
        retries=3
    )
    
    # Faz a análise final com as recomendações de produtos
    final_result = await enhanced_agent.run(ai_request.images, deps=deps)
    
    return AnalysisResponse.model_validate(final_result.output)
