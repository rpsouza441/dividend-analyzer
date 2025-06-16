import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class StockAnalyzer:
    """
    Classe para analisar dados de ações com base em critérios definidos.
    """
    
    B3_SUFFIX = ".SA" # Sufixo para ações da B3 (bolsa brasileira)

    def __init__(self):
        pass # Nenhuma inicialização específica necessária por enquanto

    def verificar_liquidez_minima(self, ticker: str, volume_minimo_diario_brl: float = 3_000_000) -> bool:
        """
        Verifica se a ação possui uma liquidez mínima diária (volume financeiro) nos últimos 3 meses.
        
        Args:
            ticker (str): O código do ticker da ação (ex: 'ITUB4').
            volume_minimo_diario_brl (float): O volume financeiro mínimo diário em BRL.
            
        Returns:
            bool: True se a liquidez for atendida, False caso contrário.
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90) # Aproximadamente 3 meses
            
            hist_data = yf.download(f"{ticker}{self.B3_SUFFIX}", start=start_date, end=end_date, progress=False)
            
            if hist_data.empty:
                print(f"    [Liquidez] Dados históricos não encontrados para {ticker}.")
                return False
            
            hist_data['Volume_Financeiro'] = hist_data['Close'] * hist_data['Volume']
            media_volume_financeiro = hist_data['Volume_Financeiro'].mean()
            
            liquidez_atendida = media_volume_financeiro >= volume_minimo_diario_brl
            
            print(f"    [Liquidez] Média Volume Financeiro (3m): R$ {media_volume_financeiro:,.2f}. Atende: {liquidez_atendida}")
            return liquidez_atendida
            
        except Exception as e:
            print(f"    [Liquidez] Erro ao verificar liquidez para {ticker}: {e}")
            return False

    def verificar_lucro_positivo_ultimo_trimestre(self, ticker: str, lucro_ultimo_trimestre: float) -> bool:
        """
        Verifica se a empresa teve lucro positivo no último trimestre reportado.
        
        Args:
            ticker (str): O código do ticker da ação.
            lucro_ultimo_trimestre (float): O valor do lucro líquido do último trimestre.
                                            Vem do StockDataScraper ou outra fonte.
                                            
        Returns:
            bool: True se o lucro for positivo, False caso contrário.
        """
        try:
            if lucro_ultimo_trimestre is None:
                print(f"    [Lucro Trimestral] Dados de lucro do último trimestre não disponíveis para {ticker}.")
                return False
                
            lucro_positivo = lucro_ultimo_trimestre > 0
            print(f"    [Lucro Trimestral] Lucro Último Trimestre: R$ {lucro_ultimo_trimestre:,.2f}. Positivo: {lucro_positivo}")
            return lucro_positivo
            
        except Exception as e:
            print(f"    [Lucro Trimestral] Erro ao verificar lucro do último trimestre para {ticker}: {e}")
            return False

    def verificar_lucros_crescentes_3_anos(self, ticker: str, lucros_anuais: list) -> bool:
        """
        Verifica se a empresa apresentou lucros crescentes nos últimos 3 anos.
        
        Args:
            ticker (str): O código do ticker da ação.
            lucros_anuais (list): Lista de lucros anuais nos últimos 3 anos (em ordem cronológica).
                                  Vem do StockDataScraper ou outra fonte.
        Returns:
            bool: True se os lucros forem crescentes, False caso contrário.
        """
        try:
            if not isinstance(lucros_anuais, list) or len(lucros_anuais) < 3:
                print(f"    [Lucros Crescentes] Dados de lucro anual insuficientes para os últimos 3 anos para {ticker}.")
                return False
            
            crescente = True
            for i in range(len(lucros_anuais) - 1):
                if lucros_anuais[i+1] <= lucros_anuais[i]:
                    crescente = False
                    break
            
            print(f"    [Lucros Crescentes] Lucros Anuais (3 anos): {lucros_anuais}. Crescentes: {crescente}")
            return crescente
            
        except Exception as e:
            print(f"    [Lucros Crescentes] Erro ao verificar lucros crescentes para {ticker}: {e}")
            return False

    def verificar_limites_payout(self, ticker: str, payout_valor: float) -> bool:
        """
        Verifica se o payout da empresa nos últimos 12 meses está entre 30% e 500%.
        
        Args:
            ticker (str): O código do ticker da ação.
            payout_valor (float): O valor do payout nos últimos 12 meses (em formato decimal, ex: 0.45).
                                  Vem do StockDataScraper ou outra fonte.
        Returns:
            bool: True se o payout estiver dentro dos limites, False caso contrário.
        """
        try:
            if payout_valor is None:
                print(f"    [Payout] Dados de payout dos últimos 12 meses não disponíveis para {ticker}.")
                return False
            
            payout_valido = (payout_valor >= 0.30) and (payout_valor <= 5.00)
            
            print(f"    [Payout] Payout (12 meses): {payout_valor*100:.2f}%. Dentro dos limites (30%-500%): {payout_valido}")
            return payout_valido
            
        except Exception as e:
            print(f"    [Payout] Erro ao verificar limites de payout para {ticker}: {e}")
            return False

    def verificar_menos_volatil(self, ticker: str, volatilidade_outras_acoes: pd.Series = None) -> bool:
        """
        Verifica se a ação é menos volátil, excluindo o primeiro décil de maior volatilidade.
        
        Args:
            ticker (str): O código do ticker da ação.
            volatilidade_outras_acoes (pd.Series, opcional): Uma série Pandas contendo a volatilidade
                                                             anualizada de várias outras ações (índice da volatilidade).
                                                             Se não fornecido, a função não pode determinar o décil
                                                             e falha o critério.
        Returns:
            bool: True se a ação for considerada menos volátil, False caso contrário.
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365) # Último ano para volatilidade
            
            hist_data = yf.download(f"{ticker}{self.B3_SUFFIX}", start=start_date, end=end_date, progress=False)
            
            if hist_data.empty or len(hist_data) < 2:
                print(f"    [Volatilidade] Dados históricos insuficientes para calcular volatilidade de {ticker}.")
                return False
                
            retornos_diarios = hist_data['Close'].pct_change().dropna()
            volatilidade_anualizada = retornos_diarios.std() * np.sqrt(252)
            
            print(f"    [Volatilidade] Volatilidade Anualizada: {volatilidade_anualizada*100:.2f}%")

            if volatilidade_outras_acoes is None or volatilidade_outras_acoes.empty:
                print(f"    [Volatilidade] Não foi fornecido um benchmark de volatilidade (outras ações) para determinar o décil. Critério não atendido por falta de dados comparativos.")
                return False
            
            # Calcula o limite do primeiro décil de maior volatilidade
            # Este é o valor de volatilidade abaixo do qual estão os 90% menos voláteis.
            limite_primeiro_decil = volatilidade_outras_acoes.quantile(0.90)
            
            criterio_volatil = volatilidade_anualizada < limite_primeiro_decil
            
            print(f"    [Volatilidade] Limite do 1º Décil (mais voláteis): {limite_primeiro_decil*100:.2f}%. Menos volátil que o 1º décil: {criterio_volatil}")
            return criterio_volatil
            
        except Exception as e:
            print(f"    [Volatilidade] Erro ao verificar volatilidade para {ticker}: {e}")
            return False

    def verificar_altos_dividendos_ponderados(self, ticker: str, pesos: dict = None, dy_minimo_ponderado: float = 0.04) -> bool:
        """
        Verifica se a empresa pagou altos dividendos nos últimos 36 meses,
        usando um modelo ponderado. O critério "altos" é definido por um DY médio ponderado.
        
        Args:
            ticker (str): O código do ticker da ação.
            pesos (dict): Dicionário com pesos para os períodos: {'12m': float, '24m': float, '36m': float}.
                          A soma dos pesos deve ser 1.0. Ex: {'12m': 0.5, '24m': 0.3, '36m': 0.2}.
                          Se não especificado, usa pesos padrão.
            dy_minimo_ponderado (float): O Dividend Yield ponderado mínimo para ser considerado "alto".
                      
        Returns:
            bool: True se o Dividend Yield ponderado atender ao critério de "alto", False caso contrário.
        """
        if pesos is None:
            pesos = {'12m': 0.5, '24m': 0.3, '36m': 0.2} # Pesos padrão
        
        end_date = datetime.now()
        start_date_36m = end_date - timedelta(days=36 * 30 + 15) # 36 meses + uma margem para garantir dados

        try:
            hist_data = yf.download(f"{ticker}{self.B3_SUFFIX}", start=start_date_36m, end=end_date, progress=False)
            
            if hist_data.empty:
                print(f"    [Dividendos] Dados históricos não encontrados para {ticker}.")
                return False

            dividends = hist_data['Dividends'].fillna(0)
            
            current_price = hist_data['Close'].iloc[-1] if not hist_data['Close'].empty else 1.0
            if current_price == 0:
                print(f"    [Dividendos] Preço atual da ação é zero. Não é possível calcular DY.")
                return False

            # Calcular dividendos para cada período
            dividends_last_12m = dividends[dividends.index >= (end_date - timedelta(days=365))].sum()
            dividends_last_24m = dividends[(dividends.index >= (end_date - timedelta(days=2 * 365))) & 
                                            (dividends.index < (end_date - timedelta(days=365)))].sum()
            dividends_last_36m_rest = dividends[(dividends.index >= (end_date - timedelta(days=3 * 365))) & 
                                                (dividends.index < (end_date - timedelta(days=2 * 365)))].sum()
            
            # Calcular DY para cada período usando o preço atual (simplificação)
            dy_12m = (dividends_last_12m / current_price) if current_price > 0 else 0
            dy_24m = (dividends_last_24m / current_price) if current_price > 0 else 0
            dy_36m = (dividends_last_36m_rest / current_price) if current_price > 0 else 0
            
            dy_ponderado = (dy_12m * pesos.get('12m', 0)) + \
                           (dy_24m * pesos.get('24m', 0)) + \
                           (dy_36m * pesos.get('36m', 0))
            
            criterio_altos_dividendos = dy_ponderado >= dy_minimo_ponderado 
            
            print(f"    [Dividendos] DY Ponderado (12m: {dy_12m*100:.2f}%, 24m: {dy_24m*100:.2f}%, 36m: {dy_36m*100:.2f}%): {dy_ponderado*100:.2f}%. Alto: {criterio_altos_dividendos}")
            return criterio_altos_dividendos
            
        except Exception as e:
            print(f"    [Dividendos] Erro ao verificar altos dividendos para {ticker}: {e}")
            return False