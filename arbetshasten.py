from datetime import datetime
import os
import time
from dotenv import load_dotenv
from supabase import create_client
import requests

# Ladda miljövariabler
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
EODHD_API_KEY = os.getenv("EODHD_API_KEY")

def kör_us500_test():
    print("--- Startar fokuserat US-test via EODHD ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    # Hämtar endast från US-börsen med common_stock för att hålla det relevant
    exchange_code = "US"
    url = f"https://eodhd.com/api/exchange-symbol-list/{exchange_code}?api_token={EODHD_API_KEY}&fmt=json&type=common_stock"
    
    print(f"Hämtar ticker-lista för {exchange_code}...")
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Kunde inte hämta ticker-lista för {exchange_code}. Statuskod: {response.status_code}")
        return

    data = response.json()
    tickers = []
    for item in data:
        code = item.get("Code")
        exchange = item.get("Exchange")
        if code and exchange:
            tickers.append(f"{code}.{exchange}")

    print(f"Hittade {len(tickers)} st aktier för US. Bearbetar en begränsad test-batch (t.ex. de första 100 för att verifiera)...")
    
    # Vi begränsar till 100 st under testet för att inte slösa onödiga anrop innan vi ser att databasen fylls
    test_batch = tickers[:100]
    nu_tid = datetime.now().isoformat()
    sparade = 0

    for raw_ticker in test_batch:
        ticker = str(raw_ticker).strip().upper()

        try:
            url_fund = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
            res_fund = requests.get(url_fund)

            if res_fund.status_code != 200:
                continue

            fund_data = res_fund.json()
            if not fund_data or "General" not in fund_data:
                continue

            general = fund_data.get("General", {})
            highlights = fund_data.get("Highlights", {})
            analyst_ratings = fund_data.get("AnalystRatings", {})

            nuvarande_pris = float(highlights.get("LatestPrice", 0) or 0)
            
            if nuvarande_pris <= 0:
                rt_url = f"https://eodhd.com/api/real-time/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
                rt_res = requests.get(rt_url)
                if rt_res.status_code == 200:
                    rt_data = rt_res.json()
                    nuvarande_pris = float(rt_data.get("close", 0) or 0)

            if nuvarande_pris <= 0:
                continue

            target = float(analyst_ratings.get("TargetPrice", 0) or 0)
            strong_buy = int(analyst_ratings.get("StrongBuy", 0) or 0)
            buy = int(analyst_ratings.get("Buy", 0) or 0)
            antal_koprek = strong_buy + buy

            namn = general.get("Name", ticker)
            sektor = general.get("Sector", "Okänd")
            valuta = general.get("Currency", "USD")

            if target > 0 and nuvarande_pris > 0:
                potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2)
            else:
                target = 0.0
                potential = 0.0

            # Spara direkt till Supabase
            supabase.table("analyser_eod").upsert({
                "ticker": ticker,
                "nuvarande": nuvarande_pris,
                "target": target,
                "potential": potential,
                "antal_koprek": antal_koprek,
                "name": namn,
                "sektor": sektor,
                "valuta": valuta,
                "senast_uppdaterad": nu_tid,
            }, on_conflict="ticker").execute()

            sparade += 1
            print(f"Sparat [{sparade}]: {ticker} ({namn}) - Kurs: {nuvarande_pris}")
            time.sleep(0.1)

        except Exception as sub_e:
            print(f"Kunde inte bearbeta {ticker}: {sub_e}")

    print(f"--- US-test klart! Totalt sparade rader i Supabase: {sparade} ---")


if __name__ == "__main__":
    kör_us500_test()