import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime, timedelta

class StockDataScraper:
    """
    Classe para realizar web scraping de dados de ações do Status Invest.
    """
    
    # URL base do Status Invest
    STATUS_INVEST_BASE_URL = "https://statusinvest.com.br/acoes/"
    
    def __init__(self):
        # Cabeçalhos HTTP para simular um navegador e evitar bloqueios
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _fetch_page(self, ticker: str) -> str:
        """
        Busca o conteúdo HTML da página do Status Invest para o ticker dado.
        
        Args:
            ticker (str): O código do ticker da ação (ex: 'ITUB4').
            
        Returns:
            str: O conteúdo HTML da página.
            
        Raises:
            Exception: Se houver um erro ao acessar a página.
        """
        url = f"{self.STATUS_INVEST_BASE_URL}{ticker.lower()}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10) # Adiciona timeout
            response.raise_for_status() # Lança um erro para códigos de status HTTP ruins (4xx ou 5xx)
            return response.text
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro ao acessar o Status Invest para {ticker}: {e}")

    def get_lpa_payout(self, ticker: str) -> dict:
        """
        Extrai o LPA (Lucro Por Ação) e o Payout de uma ação do Status Invest.
        
        Args:
            ticker (str): O código do ticker da ação.
            
        Returns:
            dict: Um dicionário com 'lpa' e 'payout'. Retorna None para valores não encontrados.
        """
        try:
            html_content = self._fetch_page(ticker)
            soup = BeautifulSoup(html_content, "html.parser")
            
            def _extract_value_from_h3(label: str):
                """
                Função auxiliar para extrair valores de tags strong que seguem um h3 com a label.
                """
                tag = soup.find("h3", string=re.compile(label, re.IGNORECASE))
                if not tag:
                    return None
                valor_span = tag.find_next("strong")
                if valor_span:
                    valor_str = valor_span.text.strip().replace(".", "").replace(",", ".").replace("%", "")
                    try:
                        return float(valor_str)
                    except ValueError:
                        return None
                return None

            lpa = _extract_value_from_h3("LPA")
            payout = _extract_value_from_h3("PAYOUT")

            return {
                "lpa": lpa,
                "payout": payout
            }
        except Exception as e:
            print(f"Erro ao extrair LPA/Payout para {ticker}: {e}")
            return {"lpa": None, "payout": None}

    def get_financial_history(self, ticker: str) -> dict:
        """
        Tenta extrair o histórico de lucros anuais e lucros trimestrais do Status Invest.
        NOTA: Esta é a parte MAIS FRÁGIL do web scraping. O Status Invest
        pode mudar a estrutura das tabelas ou usar JavaScript para carregar dados,
        dificultando a extração direta.

        Para lucros trimestrais/anuais, o Status Invest frequentemente usa tabelas complexas
        ou gráficos. Raspar esses dados é propenso a erros. Uma API seria muito melhor.
        Para a demonstração, vamos tentar extrair de uma tabela específica, mas esteja ciente
        de que pode não funcionar para todos os tickers ou pode quebrar no futuro.

        Args:
            ticker (str): O código do ticker da ação.

        Returns:
            dict: Um dicionário com 'lucros_anuais' (últimos 3) e 'lucros_trimestrais' (último).
                  Retorna None ou lista vazia se não puder extrair.
        """
        try:
            html_content = self._fetch_page(ticker)
            soup = BeautifulSoup(html_content, "html.parser")

            lucros_anuais = []
            lucro_ultimo_trimestre = None

            # Tentativa de raspar lucros anuais (Exemplo: Tabela de resultados)
            # Pode variar muito dependendo da estrutura da página.
            # Este seletor é um CHUTE baseado em como as tabelas podem ser nomeadas.
            # Você precisaria inspecionar o HTML da página do Status Invest para ITUB4 para achar o correto.
            annual_results_section = soup.find('h2', string=re.compile(r'Resultados Históricos', re.IGNORECASE))
            if annual_results_section:
                table = annual_results_section.find_next('table')
                if table:
                    # Encontrar a linha que contém "Lucro Líquido" ou "Resultado Líquido"
                    for row in table.find_all('tr'):
                        header = row.find('th')
                        if header and re.search(r'(lucro|resultado) líquido', header.text, re.IGNORECASE):
                            # Pegar os últimos 3 anos, se disponíveis
                            values = [td.text.strip().replace('.', '').replace(',', '.') for td in row.find_all('td')]
                            # Converter para float e pegar os 3 últimos valores que sejam numéricos
                            parsed_values = []
                            for val in reversed(values): # Reverte para pegar os mais recentes primeiro
                                try:
                                    parsed_values.append(float(val))
                                    if len(parsed_values) == 3:
                                        break
                                except ValueError:
                                    continue
                            lucros_anuais = list(reversed(parsed_values)) # Coloca de volta em ordem cronológica
                            break
            
            # Tentativa de raspar lucro do último trimestre
            # Novamente, um CHUTE. Pode ser em uma tabela de DRE trimestral.
            # Procure uma tabela ou seção com dados trimestrais.
            quarterly_results_section = soup.find('h3', string=re.compile(r'Resultados Trimestrais', re.IGNORECASE))
            if quarterly_results_section:
                table = quarterly_results_section.find_next('table')
                if table:
                    # Supondo que a primeira coluna é o período e há uma linha de Lucro Líquido
                    # Esta é uma lógica MUITO frágil. Você precisa ajustar para o HTML real.
                    for row in table.find_all('tr'):
                        header = row.find('th')
                        if header and re.search(r'(lucro|resultado) líquido', header.text, re.IGNORECASE):
                            # O último trimestre geralmente é o primeiro td após o th em tabelas trimestrais (se ordenado do mais recente para o mais antigo)
                            last_quarter_value_tag = row.find('td') 
                            if last_quarter_value_tag:
                                value_str = last_quarter_value_tag.text.strip().replace('.', '').replace(',', '.')
                                try:
                                    lucro_ultimo_trimestre = float(value_str)
                                except ValueError:
                                    lucro_ultimo_trimestre = None
                            break


            return {
                "lucros_anuais": lucros_anuais,
                "lucro_ultimo_trimestre": lucro_ultimo_trimestre
            }

        except Exception as e:
            print(f"Erro ao extrair histórico financeiro para {ticker}: {e}")
            return {"lucros_anuais": [], "lucro_ultimo_trimestre": None}