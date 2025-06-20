from flask import Flask, request, jsonify
from services.stock_data_scraper import StockDataScraper
from services.stock_analyzer import StockAnalyzer
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import yfinance as yf

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
scraper = StockDataScraper()
analyzer = StockAnalyzer()

# Variável global para armazenar a volatilidade do mercado.
# Idealmente, isto seria cacheado e atualizado periodicamente
# para evitar recalcular em cada requisição.
global_volatilidade_mercado = None

# Flag para garantir que a inicialização rode apenas uma vez
setup_complete = False 


def calculate_market_volatility(tickers_to_benchmark: list):
    """
    Calcula a volatilidade de um conjunto de ações para servir de benchmark.
    Faz o download dos dados de múltiplos tickers em uma única requisição.
    """
    logging.info("Calculando volatilidade de um conjunto de ações para benchmark...")
    
    # Adiciona o sufixo .SA para todos os tickers do benchmark
    tickers_yf_format = [f"{t}{analyzer.B3_SUFFIX}" for t in tickers_to_benchmark]

    end_date_vol = datetime.now()
    start_date_vol = end_date_vol - timedelta(days=365) # Último ano para volatilidade
    
    volatilidades_do_mercado = {}

    try:
        # Baixa dados de TODOS os tickers em UMA ÚNICA REQUISIÇÃO
        # Isso é muito mais eficiente do que um loop com download individual
        data = yf.download(tickers_yf_format, start=start_date_vol, end=end_date_vol, progress=False)

        if data.empty:
            logging.warning("    [Benchmark Volatilidade] Nenhum dado de benchmark baixado. Pode ser problema de conexão ou tickers inválidos.")
            return pd.Series() # Retorna uma série vazia

        # Acessa os preços de fechamento ('Close')
        # 'data' terá múltiplos níveis de coluna se for mais de um ticker
        close_prices = data['Close']

        for t in tickers_to_benchmark:
            yf_ticker = f"{t}{analyzer.B3_SUFFIX}"
            if yf_ticker in close_prices.columns:
                # Retornos diários para este ticker específico
                returns = close_prices[yf_ticker].pct_change().dropna()
                if not returns.empty:
                    volatilidad_anualizada = returns.std() * np.sqrt(252)
                    volatilidades_do_mercado[t] = volatilidad_anualizada
                else:
                    logging.warning(f"    [Benchmark Volatilidade] Dados insuficientes ou sem variações para {t}.")
            else:
                logging.warning(f"    [Benchmark Volatilidade] Ticker {t} não encontrado nos dados baixados.")

    except Exception as e:
        # Captura erros que podem ocorrer no download em bloco
        logging.error(f"    [Benchmark Volatilidade] Erro geral ao obter volatilidade para o benchmark: {e}")

    return pd.Series(volatilidades_do_mercado)


# MODIFICAÇÃO AQUI: Usando @app.before_request com uma flag
@app.before_request
def setup_application():
    """
    Executa antes de cada requisição, mas o setup global só roda na primeira vez.
    """
    global setup_complete
    global global_volatilidade_mercado

    if not setup_complete:
        # Lista de tickers para calcular o benchmark de volatilidade.
        # EXPANDA ESTA LISTA COM MUITAS AÇÕES DO IBOVESPA OU RELEVANTES.
        tickers_para_benchmark = ["ITUB4", "BBDC4", "PETR4", "VALE3", "ABEV3", "WEGE3", "PRIO3", "MGLU3", "RENT3", "BPAC11"]
        
        global_volatilidade_mercado = calculate_market_volatility(tickers_para_benchmark)
        logging.info("Setup inicial da aplicação concluído.")
        setup_complete = True # Marca como completo para não rodar novamente


@app.route('/check_stock/<ticker>', methods=['GET'])
def check_stock(ticker):
    """
    Endpoint para verificar se uma ação atende a todos os critérios.
    
    Args:
        ticker (str): O código do ticker da ação a ser verificada.
        
    Returns:
        JSON: Um JSON contendo os resultados da verificação.
    """
    ticker_upper = ticker.upper()
    logging.info(f"Requisição para verificar ação: {ticker_upper}")

    resultados = {
        'ticker': ticker_upper,
        'liquidez_minima': False,
        'lucro_positivo_ult_trimestre': False,
        'lucros_crescentes_3_anos': False,
        'limites_payout': False,
        'menos_volatil': False,
        'altos_dividendos': False,
        'todos_criterios_atendidos': False,
        'erros': []
    }

    try:
        # 1. Obter dados de scraping (Lucro e Payout)
        logging.info(f"  Buscando dados de LPA/Payout e histórico financeiro para {ticker_upper} via scraping...")
        lpa_payout_data = scraper.get_lpa_payout(ticker_upper)
        financial_history_data = scraper.get_financial_history(ticker_upper)

        if not lpa_payout_data['lpa'] is None and not lpa_payout_data['payout'] is None:
            logging.info(f"  Dados de scraping obtidos: LPA={lpa_payout_data['lpa']}, Payout={lpa_payout_data['payout']}")
        else:
            logging.warning(f"  Não foi possível obter LPA/Payout completos via scraping para {ticker_upper}.")
            resultados['erros'].append("Não foi possível obter dados de LPA/Payout via scraping. Verifique a estrutura do site.")

        if financial_history_data['lucro_ultimo_trimestre'] is not None and financial_history_data['lucros_anuais']:
             logging.info(f"  Dados de histórico financeiro obtidos: Último Lucro={financial_history_data['lucro_ultimo_trimestre']}, Lucros Anuais={financial_history_data['lucros_anuais']}")
        else:
            logging.warning(f"  Não foi possível obter histórico financeiro completo via scraping para {ticker_upper}.")
            resultados['erros'].append("Não foi possível obter histórico de lucros via scraping. Verifique a estrutura do site.")

        # 2. Executar as verificações dos critérios
        resultados['liquidez_minima'] = analyzer.verificar_liquidez_minima(ticker_upper)
        
        # Passando os dados extraídos pelo scraper
        resultados['lucro_positivo_ult_trimestre'] = analyzer.verificar_lucro_positivo_ultimo_trimestre(
            ticker_upper, financial_history_data.get('lucro_ultimo_trimestre')
        )
        resultados['lucros_crescentes_3_anos'] = analyzer.verificar_lucros_crescentes_3_anos(
            ticker_upper, financial_history_data.get('lucros_anuais', [])
        )
        resultados['limites_payout'] = analyzer.verificar_limites_payout(
            ticker_upper, lpa_payout_data.get('payout')
        )
        
        # Passando a volatilidade de mercado pré-calculada
        # Garante que global_volatilidade_mercado não é None
        if global_volatilidade_mercado is not None:
            resultados['menos_volatil'] = analyzer.verificar_menos_volatil(
                ticker_upper, global_volatilidade_mercado
            )
        else:
            logging.error("  Global volatility market data not available.")
            resultados['erros'].append("Dados de volatilidade do mercado não disponíveis para comparação.")
            resultados['menos_volatil'] = False # Falha o critério se não há benchmark
            
        resultados['altos_dividendos'] = analyzer.verificar_altos_dividendos_ponderados(ticker_upper)
        
        resultados['todos_criterios_atendidos'] = all([
            resultados['liquidez_minima'],
            resultados['lucro_positivo_ult_trimestre'],
            resultados['lucros_crescentes_3_anos'],
            resultados['limites_payout'],
            resultados['menos_volatil'],
            resultados['altos_dividendos']
        ])
        
        logging.info(f"Verificação completa para {ticker_upper}. Todos os critérios atendidos: {resultados['todos_criterios_atendidos']}")
        # Convertendo todos os valores numpy.bool_ para bool
        resultados = {k: bool(v) if isinstance(v, np.bool_) else v for k, v in resultados.items()}
        return jsonify(resultados)

    except Exception as e:
        logging.exception(f"Erro inesperado ao processar {ticker_upper}: {e}")
        resultados['erros'].append(f"Erro inesperado no servidor: {str(e)}")
        return jsonify(resultados), 500 # Retorna 500 em caso de erro interno do servidor

@app.route('/')
def home():
    return "Bem-vindo à API de Análise de Ações! Use /check_stock/<ticker> para verificar uma ação."

if __name__ == '__main__':
    # Para rodar a aplicação em modo de desenvolvimento
    # Em produção, use um servidor WSGI como Gunicorn ou uWSGI
    app.run(debug=True, host='0.0.0.0', port=5000)