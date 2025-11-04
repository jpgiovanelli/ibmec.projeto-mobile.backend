import csv
import os
import json
from typing import List, Dict, Literal, Optional
from pathlib import Path

SkinType = Literal["SECA", "MISTA", "OLEOSA", "NORMAL"]
RoutineType = Literal["SIMPLES", "COMPLETA"]
AgeGroup = Literal[1, 2, 3]  # 1: até 30, 2: 30-45, 3: 45+

class ProductRecommendationService:
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / "data"
        self.products_cache = {}
    
    def _parse_csv_content(self, content: str) -> List[Dict]:
        """Parse o conteúdo CSV que está em formato pseudo-JSON"""
        products = []
        lines = content.strip().split('\n')
        current_product_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Pula linhas vazias ou cabeçalhos
            if not line or 'Opções Protetor solar' in line:
                continue
            
            # Se a linha contém o início de um produto (nome do produto com ":")
            if '": {' in line:
                current_product_lines = [line]
            # Se já estamos construindo um produto, adiciona a linha
            elif current_product_lines:
                current_product_lines.append(line)
            
            # Se encontramos o final do produto
            if current_product_lines and line == '}':
                try:
                    # Junta todas as linhas do produto
                    product_str = '\n'.join(current_product_lines)
                    
                    # Remove aspas extras do início e fim
                    product_str = product_str.strip('"')
                    
                    # Extrai o JSON do produto (tudo depois de "nome": {)
                    if '": {' in product_str:
                        json_part = product_str.split('": {', 1)[1]
                        # Remove o " final se existir
                        json_part = json_part.rstrip('"').rstrip()
                        # Adiciona o { de volta
                        json_part = '{' + json_part
                        
                        # Corrige o formato para JSON válido:
                        # 1. Troca "" por " nas chaves e valores
                        json_part = json_part.replace('""', '"')
                        
                        # 2. Adiciona aspas nas chaves (name:, url:, etc)
                        import re
                        # Adiciona aspas nas chaves (palavra seguida de :)
                        json_part = re.sub(r'\n\s*(\w+):', r'\n"\1":', json_part)
                        # Também trata a primeira chave (após o {)
                        json_part = re.sub(r'{\s*(\w+):', r'{"\1":', json_part)
                        
                        # Parse do JSON
                        product = json.loads(json_part)
                        products.append(product)
                except (json.JSONDecodeError, Exception) as e:
                    # Silenciosamente ignora produtos com erro
                    pass
                
                current_product_lines = []
        
        return products
    
    def determine_age_group(self, user_responses: str) -> AgeGroup:
        """
        Determina o grupo etário baseado nas respostas do usuário
        1: até 30 anos
        2: 30-45 anos
        3: 45+ anos
        """
        user_lower = user_responses.lower()
        
        # Procura por idade explícita
        import re
        age_patterns = [
            r'(\d{2})\s*anos',
            r'idade[:\s]+(\d{2})',
            r'tenho\s+(\d{2})',
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, user_lower)
            if match:
                age = int(match.group(1))
                if age < 30:
                    return 1
                elif age < 45:
                    return 2
                else:
                    return 3
        
        # Palavras-chave para diferentes faixas etárias
        young_keywords = [
            'jovem', 'novo', 'nova', '20 anos', 'vinte', 'adolescent',
            'início', 'prevenção', 'primeira rotina'
        ]
        
        middle_keywords = [
            'trinta', '30', '35', '40', 'meia idade', 
            'primeiras rugas', 'sinais de idade', 'preventivo'
        ]
        
        mature_keywords = [
            '45', '50', '55', '60', 'quarenta', 'cinquenta',
            'madur', 'rugas profundas', 'flacidez', 'anti-idade',
            'rejuvenescimento', 'lifting'
        ]
        
        young_score = sum(1 for keyword in young_keywords if keyword in user_lower)
        middle_score = sum(1 for keyword in middle_keywords if keyword in user_lower)
        mature_score = sum(1 for keyword in mature_keywords if keyword in user_lower)
        
        # Retorna o grupo com maior score
        scores = {1: young_score, 2: middle_score, 3: mature_score}
        max_group = max(scores, key=scores.get)
        
        # Se não houver indicação clara, assume grupo 1 (mais comum)
        if scores[max_group] == 0:
            return 1
        
        return max_group
    
    def determine_routine_complexity(self, user_responses: str) -> RoutineType:
        """
        Analisa a resposta do usuário para determinar se deve recomendar 
        rotina SIMPLES ou COMPLETA.
        
        Critérios:
        - SIMPLES: Para iniciantes, rotina básica, poucos passos, orçamento limitado
        - COMPLETA: Para usuários avançados, múltiplas preocupações, resultados intensivos
        """
        user_lower = user_responses.lower()
        
        # Palavras-chave para rotina SIMPLES
        simple_keywords = [
            'simples', 'básico', 'básica', 'iniciante', 'começando', 'poucos produtos',
            'rápido', 'rápida', 'prático', 'prática', 'orçamento', 'barato', 'econômico',
            'primeiro', 'primeira', 'mínimo', 'mínima', 'essencial', 'começo'
        ]
        
        # Palavras-chave para rotina COMPLETA
        complete_keywords = [
            'completo', 'completa', 'avançado', 'avançada', 'intensivo', 'intensiva',
            'detalhado', 'detalhada', 'múltiplos', 'múltiplas', 'várias', 'vários',
            'muitas preocupações', 'muitos problemas', 'problemas', 'preocupações',
            'resultados rápidos', 'eficaz', 'potente', 'tratamento completo',
            'anti-idade', 'rugas', 'manchas', 'acne severa', 'melasma',
            'flacidez', 'rejuvenescimento', 'tratamento intensivo'
        ]
        
        simple_score = sum(1 for keyword in simple_keywords if keyword in user_lower)
        complete_score = sum(1 for keyword in complete_keywords if keyword in user_lower)
        
        # Se a resposta mencionar explicitamente "completa", prioriza
        if 'completa' in user_lower or 'completo' in user_lower:
            return "COMPLETA"
        
        # Se a resposta mencionar explicitamente "simples", prioriza
        if 'simples' in user_lower or 'básica' in user_lower or 'básico' in user_lower:
            return "SIMPLES"
        
        # Caso contrário, decide por score
        if complete_score > simple_score:
            return "COMPLETA"
        else:
            return "SIMPLES"  # Default para SIMPLES
    
    def load_routine(self, skin_type: SkinType, routine_type: RoutineType, age_group: AgeGroup) -> List[Dict]:
        """Carrega a rotina específica para o tipo de pele, complexidade e faixa etária"""
        cache_key = f"{skin_type}_{routine_type}_{age_group}"
        
        if cache_key in self.products_cache:
            return self.products_cache[cache_key]
        
        filename = f"Rotinas - {skin_type} - {routine_type} - {age_group}.csv"
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            print(f"⚠️ Arquivo não encontrado: {filename}")
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                products = self._parse_csv_content(content)
                self.products_cache[cache_key] = products
                return products
        except Exception as e:
            print(f"❌ Erro ao carregar {filename}: {e}")
            return []
    
    def get_products_by_category(self, products: List[Dict]) -> Dict[str, List[Dict]]:
        """Organiza produtos por categoria"""
        categorized = {}
        
        for product in products:
            category = product.get('category', 'Outros')
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(product)
        
        return categorized
    
    def format_products_for_ai(self, products: List[Dict]) -> str:
        """Formata a lista de produtos para enviar à IA"""
        if not products:
            return "# NENHUM PRODUTO DISPONÍVEL\n"
        
        categorized = self.get_products_by_category(products)
        
        formatted = "# PRODUTOS DISPONÍVEIS PARA RECOMENDAÇÃO\n\n"
        formatted += "Use APENAS estes produtos nas suas recomendações.\n"
        formatted += "Para cada produto, use exatamente as informações fornecidas abaixo.\n\n"
        
        for category, items in categorized.items():
            formatted += f"## {category}\n\n"
            for product in items:
                formatted += f"**{product.get('name', 'N/A')}**\n"
                formatted += f"- SKU: {product.get('sku', 'N/A')}\n"
                formatted += f"- Descrição: {product.get('description', 'N/A')}\n"
                formatted += f"- URL: {product.get('url', 'N/A')}\n"
                formatted += f"- Imagem: {product.get('image', 'N/A')}\n\n"
        
        return formatted
    
    def get_recommendation_info(self, user_responses: str) -> Dict:
        """
        Analisa as respostas do usuário e retorna informações sobre a recomendação
        """
        age_group = self.determine_age_group(user_responses)
        routine_type = self.determine_routine_complexity(user_responses)
        
        age_descriptions = {
            1: "até 30 anos (foco em prevenção)",
            2: "30-45 anos (primeiros sinais de envelhecimento)",
            3: "45+ anos (tratamento anti-idade intensivo)"
        }
        
        return {
            "age_group": age_group,
            "age_description": age_descriptions[age_group],
            "routine_type": routine_type
        }

# Instância singleton
product_service = ProductRecommendationService()
