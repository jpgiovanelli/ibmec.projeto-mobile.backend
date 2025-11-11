import os
import asyncio
from typing import List

from pydantic_ai import Agent
from fastapi import HTTPException

from app.models.Request import SkinProfileRequest, AIRequest
from app.models.Response import AnalysisResponse, SkinTypes

PROMPT = """  
Você é um dermatologista altamente experiente, especializado em cuidados com a pele do rosto.
Receberá perguntas, respostas e imagens de um paciente relacionadas à saúde e estética facial.
Com base nessas informações, deve analisar cuidadosamente e responder seguindo exatamente o modelo de resposta fornecido, utilizando uma linguagem técnica, empática e profissional, adequada à prática dermatológica.
Suas respostas devem ser claras, objetivas e baseadas em evidências clínicas, considerando aspectos como diagnóstico diferencial, possíveis causas, tratamento recomendado e orientações preventivas.

Você receberá uma lista de produtos em formato CSV. Use APENAS os produtos dessa lista para montar a rotina de cuidados.
A lista de produtos foi selecionada especificamente para o tipo de pele e idade do paciente.
NÃO invente produtos. NÃO busque produtos fora da lista fornecida. Use somente os produtos presentes no CSV.

IMPORTANTE - PADRÃO DE RESPOSTA:
1. SCORES: Use escala de 0 a 10 (onde 0 = ótimo, sem problemas e 10 = problema grave)
   - Sempre inclua: Hidratação, Acne, Manchas, Rugas
   - Adicione outros scores relevantes se necessário (Firmeza, Sensibilidade, Poros, etc)

2. CONCERNS: Escreva um texto detalhado e técnico (mínimo 3-4 frases) descrevendo:
   - Observações clínicas da pele com base na imagem e questionário
   - Diagnóstico das condições identificadas
   - Objetivos do tratamento proposto
   - Use terminologia médica adequada (pápulas, pústulas, eritema, hiperpigmentação, etc)

3. ROUTINE: Para cada produto, forneça:
   - title: Nome exato do produto do CSV
   - description: Descrição expandida incluindo COMO USAR o produto (seja específico: "Aplique 3-5 gotas...", "Aplique sobre a pele úmida...", etc)
   - price: Use um valor placeholder como 100
   - image_url: URL exata da imagem do CSV
   - link: URL exato do produto do CSV

Mantenha sempre este padrão consistente em todas as respostas.
"""

dermage_agent = Agent(
    "google-gla:gemini-2.5-pro",
    deps_type=SkinProfileRequest,
    output_type=AnalysisResponse,
    system_prompt=PROMPT,
    retries=3
)


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
    deps = ai_request.skin_profile
    
    # Extrair idade do questionário ou usar valor padrão
    age = deps.age if deps.age else 30
    
    # Determinar complexidade baseado no número de perguntas e respostas
    total_answer_length = sum(len(q.answer) for q in deps.questions)
    complexity = "COMPLETA" if total_answer_length > 150 or len(deps.questions) > 5 else "SIMPLES"
    
    print(f"Iniciando análise - Idade: {age}, Complexidade: {complexity}")
    
    # Carregar produtos de TODOS os tipos de pele (mas será apenas 1 chamada à API)
    all_products = []
    for skin_type in SkinTypes:
        try:
            routine_file = get_routine_file(skin_type, age, complexity)
            products_data = load_products_csv(routine_file)
            all_products.append(f"\n=== PRODUTOS PARA PELE {skin_type.value.upper()} ===\n{products_data}")
        except Exception as e:
            print(f"Erro ao carregar produtos para pele {skin_type.value}: {e}")
    
    combined_products = "\n".join(all_products)
    
    # Análise ÚNICA com todos os produtos
    final_prompt = f"""
    {PROMPT}
    
    Lista de produtos disponíveis ORGANIZADOS POR TIPO DE PELE:
    {combined_products}
    
    INSTRUÇÕES IMPORTANTES:
    1. Analise a imagem e o questionário para determinar o tipo de pele (seca, mista, oleosa ou normal)
    2. Use APENAS os produtos da seção correspondente ao tipo de pele identificado
    3. Monte uma rotina de cuidados completa (manhã e noite) usando os produtos corretos
    4. Garanta que o campo "skin_type" na resposta corresponda ao tipo de pele para o qual você selecionou os produtos
    """
    
    final_agent = Agent(
        "google-gla:gemini-2.5-pro",
        deps_type=SkinProfileRequest,
        output_type=AnalysisResponse,
        system_prompt=final_prompt,
        retries=3
    )
    
    max_retries = 2
    retry_delay = 60  # 60 segundos para respeitar o rate limit
    
    # Análise com retry respeitando rate limit
    for attempt in range(max_retries):
        try:
            print(f"Tentativa {attempt + 1} - Gerando análise completa...")
            result = await final_agent.run(ai_request.images, deps=deps)
            final_response = AnalysisResponse.model_validate(result.output)
            print("Análise concluída com sucesso!")
            return final_response
        except Exception as e:
            error_message = str(e)
            print(f"Erro na análise (tentativa {attempt + 1}): {error_message}")
            
            # Se for erro de quota, aguardar mais tempo
            if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message:
                if attempt < max_retries - 1:
                    print(f"Limite de quota atingido. Aguardando {retry_delay} segundos...")
                    await asyncio.sleep(retry_delay)
                else:
                    raise HTTPException(
                        status_code=429,
                        detail="Limite de requisições da API atingido. Aguarde 1 minuto e tente novamente."
                    )
            elif attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                raise
