import requests
from bs4 import BeautifulSoup
import re

class StockDataScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _get_soup(self, url: str):
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _from_investidor10(self, ticker: str):
        try:
            soup = self._get_soup(f"https://investidor10.com.br/acoes/{ticker.lower()}/")
            boxes = soup.find_all("div", class_="indicators-box")
            lpa = payout = None
            for box in boxes:
                text = box.get_text().lower()
                if "lpa" in text:
                    val = box.text.strip().split()[-1].replace(",", ".")
                    lpa = float(val)
                elif "payout" in text:
                    val = box.text.strip().split()[-1].replace("%", "").replace(",", ".")
                    payout = float(val)
            return {"lpa": lpa, "payout": payout}
        except Exception:
            return {"lpa": None, "payout": None}

    def _from_statusinvest(self, ticker: str):
        try:
            soup = self._get_soup(f"https://statusinvest.com.br/acoes/{ticker.lower()}")
            def _extract(label):
                tag = soup.find("h3", string=re.compile(label, re.IGNORECASE))
                if tag:
                    strong = tag.find_next("strong")
                    if strong:
                        value = strong.text.strip().replace(".", "").replace(",", ".").replace("%", "")
                        return float(value)
                return None
            return {
                "lpa": _extract("lpa"),
                "payout": _extract("payout")
            }
        except Exception:
            return {"lpa": None, "payout": None}

    def _from_fundamentus(self, ticker: str):
        try:
            soup = self._get_soup(f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}")
            lpa = payout = None
            for td in soup.find_all("td"):
                text = td.get_text(strip=True).lower()
                if text == "lpa":
                    try:
                        lpa = float(td.find_next("td").text.strip().replace(",", "."))
                    except:
                        pass
                elif text == "div. líquida / patrimonio":
                    try:
                        payout = float(td.find_next("td").text.strip().replace("%", "").replace(",", "."))
                    except:
                        pass
            return {"lpa": lpa, "payout": payout}
        except Exception:
            return {"lpa": None, "payout": None}

    def get_lpa_payout(self, ticker: str) -> dict:
        resultado = {"lpa": None, "payout": None}
        for extractor in [self._from_investidor10, self._from_statusinvest, self._from_fundamentus]:
            try:
                res = extractor(ticker)
                if resultado["lpa"] is None and res["lpa"] is not None:
                    resultado["lpa"] = res["lpa"]
                if resultado["payout"] is None and res["payout"] is not None:
                    resultado["payout"] = res["payout"]
                if all(v is not None for v in resultado.values()):
                    break
            except Exception:
                continue
        return resultado

    def get_financial_history(self, ticker: str) -> dict:
        try:
            soup = self._get_soup(f"https://statusinvest.com.br/acoes/{ticker.lower()}")
            lucros_anuais = []
            lucro_ultimo_trimestre = None

            annual_results_section = soup.find('h2', string=re.compile(r'Resultados Históricos', re.IGNORECASE))
            if annual_results_section:
                table = annual_results_section.find_next('table')
                if table:
                    for row in table.find_all('tr'):
                        header = row.find('th')
                        if header and re.search(r'(lucro|resultado) líquido', header.text, re.IGNORECASE):
                            values = [td.text.strip().replace('.', '').replace(',', '.') for td in row.find_all('td')]
                            parsed_values = []
                            for val in reversed(values):
                                try:
                                    parsed_values.append(float(val))
                                    if len(parsed_values) == 3:
                                        break
                                except ValueError:
                                    continue
                            lucros_anuais = list(reversed(parsed_values))
                            break

            quarterly_results_section = soup.find('h3', string=re.compile(r'Resultados Trimestrais', re.IGNORECASE))
            if quarterly_results_section:
                table = quarterly_results_section.find_next('table')
                if table:
                    for row in table.find_all('tr'):
                        header = row.find('th')
                        if header and re.search(r'(lucro|resultado) líquido', header.text, re.IGNORECASE):
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