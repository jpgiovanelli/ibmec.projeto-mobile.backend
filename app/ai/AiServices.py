import os
import asyncio
from typing import List
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from fastapi import HTTPException

from app.models.Request import SkinProfileRequest, AIRequest
from app.models.Response import AnalysisResponse, SkinTypes


@dataclass
class AnalysisDependencies:
    """Dependencies para o agente de análise de pele."""
    skin_profile: SkinProfileRequest
    age: int
    complexity: str


# Prompt base do sistema
BASE_SYSTEM_PROMPT = """
Você é um dermatologista altamente experiente, especializado em cuidados com a pele do rosto.
Receberá perguntas, respostas e imagens de um paciente relacionadas à saúde e estética facial.
Com base nessas informações, deve analisar cuidadosamente e responder seguindo exatamente o modelo de resposta fornecido, utilizando uma linguagem técnica, empática e profissional, adequada à prática dermatológica.
Suas respostas devem ser claras, objetivas e baseadas em evidências clínicas, considerando aspectos como diagnóstico diferencial, possíveis causas, tratamento recomendado e orientações preventivas.

IMPORTANTE - PRIORIZAÇÃO DE ANÁLISE:
- PRIORIZE as respostas do questionário fornecido pelo paciente como base principal da análise
- Use a análise visual da imagem para COMPLEMENTAR e VALIDAR as informações do questionário
- Em caso de discrepância entre questionário e imagem, dê PESO MAIOR às respostas do questionário, mas mencione as observações visuais relevantes
- A combinação de ambas as fontes (questionário + imagem) deve guiar o diagnóstico final

FLUXO DE TRABALHO:
1. Primeiro, analise a imagem e questionário para determinar o tipo de pele (seca, mista, oleosa ou normal)
2. Use a tool 'load_products_for_skin_type' passando o tipo de pele identificado
3. Com os produtos carregados, monte a rotina completa usando APENAS produtos dessa lista
4. NÃO invente produtos - use somente os retornados pela tool

IMPORTANTE - PADRÃO DE RESPOSTA:
1. SCORES: Use escala de 0 a 10 (onde 0 = ótimo, sem problemas e 10 = problema grave)
   - Sempre inclua: Hidratação, Acne, Manchas, Rugas
   - Adicione outros scores relevantes se necessário (Firmeza, Sensibilidade, Poros, etc)

2. CONCERNS: Escreva um texto detalhado e técnico (mínimo 3-4 frases) descrevendo:
   - Observações clínicas da pele com base PRIORITARIAMENTE no questionário e complementadas pela imagem
   - Diagnóstico das condições identificadas
   - Objetivos do tratamento proposto
   - Use terminologia médica adequada (pápulas, pústulas, eritema, hiperpigmentação, etc)

3. ROUTINE: Para cada produto, forneça:
   - title: Nome exato do produto da lista
   - description: Descrição expandida incluindo COMO USAR o produto (seja específico: "Aplique 3-5 gotas...", "Aplique sobre a pele úmida...", etc)
   - price: Use um valor placeholder como 100
   - image_url: URL exata da imagem
   - link: URL exato do produto

Mantenha sempre este padrão consistente em todas as respostas.
"""


# Criação do agente com system prompt dinâmico
dermage_agent = Agent[AnalysisDependencies, AnalysisResponse](
    "google-gla:gemini-2.5-pro",
    deps_type=AnalysisDependencies,
    retries=2,
)


@dermage_agent.tool
async def load_products_for_skin_type(
    ctx: RunContext[AnalysisDependencies],
    skin_type: str
) -> str:
    """
    Carrega o catálogo de produtos específico para um tipo de pele.
    
    Args:
        skin_type: O tipo de pele identificado. Deve ser: 'seca', 'mista', 'oleosa' ou 'normal'
    
    Returns:
        String com a lista de produtos disponíveis para esse tipo de pele
    """
    # Validar e converter tipo de pele
    skin_type_lower = skin_type.lower()
    
    try:
        # Mapear para o enum
        skin_type_enum = SkinTypes(skin_type_lower)
    except ValueError:
        return f"Erro: Tipo de pele '{skin_type}' inválido. Use: seca, mista, oleosa ou normal"
    
    try:
        # Carregar produtos apenas para este tipo de pele
        routine_file = get_routine_file(skin_type_enum, ctx.deps.age, ctx.deps.complexity)
        products_data = load_products_csv(routine_file)
        
        return f"""
=== PRODUTOS DISPONÍVEIS PARA PELE {skin_type_enum.value.upper()} ===

{products_data}

Use APENAS estes produtos para montar a rotina de cuidados.
Tipo de pele confirmado: {skin_type_enum.value}
"""
    except Exception as e:
        return f"Erro ao carregar produtos: {str(e)}"


@dermage_agent.system_prompt
async def get_system_prompt(ctx: RunContext[AnalysisDependencies]) -> str:
    """System prompt dinâmico com contexto do paciente."""
    return f"""
{BASE_SYSTEM_PROMPT}

CONTEXTO DO PACIENTE:
- Idade: {ctx.deps.age} anos
- Complexidade da rotina recomendada: {ctx.deps.complexity}

Questionário do paciente:
{ctx.deps.skin_profile.model_dump_json()}
"""


# Removido output_validator temporariamente para debug


def get_age_category(age: int) -> int:
    """
    Retorna a categoria de idade baseada na idade do usuário:
    - Até 30 anos: categoria 1
    - 30-45 anos: categoria 2
    - 45+ anos: categoria 3
    """
    if age <= 30:
        return 1
    elif age <= 45:
        return 2
    else:
        return 3


def determine_routine_complexity(questions: List) -> str:
    """
    Analisa as respostas do questionário para determinar se deve ser
    recomendada uma rotina SIMPLES ou COMPLETA.
    """
    # Esta lógica será implementada pela IA no prompt
    # Por padrão, retornamos COMPLETA para análise mais detalhada
    return "COMPLETA"


def get_routine_file(skin_type: SkinTypes, age: int, complexity: str) -> str:
    """
    Retorna o caminho do arquivo CSV apropriado baseado no tipo de pele,
    idade e complexidade da rotina.
    
    Args:
        skin_type: Tipo de pele (SECA, MISTA, OLEOSA, NORMAL)
        age: Idade do usuário
        complexity: SIMPLES ou COMPLETA
    
    Returns:
        Caminho completo para o arquivo CSV
    """
    age_category = get_age_category(age)
    skin_type_str = skin_type.value.upper()
    
    filename = f"Rotinas - {skin_type_str} - {complexity} - {age_category}.csv"
    
    # Caminho relativo da pasta data (volta 2 níveis de app/ai/ para a raiz)
    base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    file_path = os.path.join(base_path, filename)
    
    return file_path

def load_products_csv(file_path: str) -> str:
    """
    Carrega o conteúdo do arquivo CSV de produtos.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise Exception(f"Arquivo de produtos não encontrado: {file_path}")
    except Exception as e:
        raise Exception(f"Erro ao carregar arquivo de produtos: {str(e)}")


async def analyze_skin(ai_request: AIRequest) -> AnalysisResponse:
    """
    Analisa a pele do paciente usando IA com validação e retry automáticos.
    
    Args:
        ai_request: Requisição contendo perfil do paciente e imagens
        
    Returns:
        AnalysisResponse: Análise completa da pele com rotina personalizada
        
    Raises:
        HTTPException: Se exceder limite de quota ou houver erro fatal
    """
    skin_profile = ai_request.skin_profile
    
    # Extrair idade do questionário ou usar valor padrão
    age = skin_profile.age if skin_profile.age else 30
    
    # Determinar complexidade baseado no número de perguntas e respostas
    total_answer_length = sum(len(q.answer) for q in skin_profile.questions)
    complexity = "COMPLETA" if total_answer_length > 150 or len(skin_profile.questions) > 5 else "SIMPLES"
    
    print(f"[ANÁLISE] Iniciando - Idade: {age}, Complexidade: {complexity}")
    
    # Criar dependencies para o agente (SEM carregar produtos)
    deps = AnalysisDependencies(
        skin_profile=skin_profile,
        age=age,
        complexity=complexity
    )
    
    # Executar análise com retry inteligente
    max_retries = 2
    retry_delay = 60
    
    for attempt in range(max_retries):
        try:
            print(f"[ANÁLISE] Tentativa {attempt + 1}/{max_retries}")
            
            # O agente vai usar a tool para carregar produtos quando necessário
            result = await dermage_agent.run(
                ai_request.images,
                deps=deps
            )
            
            print(f"[ANÁLISE] Concluída com sucesso! Tipo de pele: {result.data.skin_type.value}")
            return result.data
            
        except Exception as e:
            error_message = str(e)
            print(f"[ERRO] Tentativa {attempt + 1} falhou: {error_message}")
            
            # Tratar erro de quota/rate limit
            if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message:
                if attempt < max_retries - 1:
                    print(f"[RETRY] Limite de quota atingido. Aguardando {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    raise HTTPException(
                        status_code=429,
                        detail="Limite de requisições da API atingido. Aguarde 1 minuto e tente novamente."
                    )
            # Outros erros
            elif attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                print(f"[RETRY] Aguardando {wait_time}s antes de tentar novamente...")
                await asyncio.sleep(wait_time)
            else:
                # Re-lançar erro após todas as tentativas
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro ao processar análise: {error_message}"
                )
