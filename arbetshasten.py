from datetime import datetime
import os
import time
from dotenv import load_dotenv
from supabase import create_client
import requests

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
EODHD_API_KEY = os.getenv("EODHD_API_KEY")

def kör_us500_test():
    print("--- Startar test med EOD stängningskurs och Fundamentals ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    test_tickers = ["AAPL.US", "MSFT.US", "NVDA.US", "GOOGL.US", "AMZN.US"]
    nu_tid = datetime.now().isoformat()
    sparade = 0

    for ticker in test_tickers:
        print(f"\nUndersöker ticker: {ticker}")

        try:
            # 1. Hämta senaste stängningskurs (EOD) - ingår i din prenumeration
            url_eod = f"https://eodhd.com/api/eod/{ticker}?api_token={EODHD_API_KEY}&fmt=json&limit=1"
            res_eod = requests.get(url_eod)
            
            print(f"  - EOD Statuskod: {res_eod.status_code}")
            
            nuvarande_pris = 0.0
            if res_eod.status_code == 200:
                eod_data = res_eod.json()
                # EOD returnerar en lista med objekt, vi vill åt den senaste ('close')
                if isinstance(eod_data, list) and len(eod_data) > 0:
                    nuvarande_pris = float(eod_data[-1].get("close", 0) or 0)

            print(f"  - Senaste stängningskurs (EOD): {nuvarande_pris}")

            if nuvarande_pris <= 0:
                print("  -> Hoppar över: Kunde inte hämta giltig stängningskurs")
                continue

            # 2. Hämta fundamenta för namn, sektor och analytikerbetyg
            url_fund = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
            res_fund = requests.get(url_fund)
            
            namn = ticker
            sektor = "Okänd"
            valuta = "USD"
            target = 0.0
            antal_koprek = 0

            if res_fund.status_code == 200:
                fund_data = res_fund.json()
                if fund_data and "General" in fund_data:
                    general = fund_data.get("General", {})
                    analyst_ratings = fund_data.get("AnalystRatings", {})

                    namn = general.get("Name", ticker)
                    sektor = general.get("Sector", "Okänd")
                    valuta = general.get("Currency", "USD")
                    target = float(analyst_ratings.get("TargetPrice", 0) or 0)
                    
                    strong_buy = int(analyst_ratings.get("StrongBuy", 0) or 0)
                    buy = int(analyst_ratings.get("Buy", 0) or 0)
                    antal_koprek = strong_buy + buy

            potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2) if (target > 0 and nuvarande_pris > 0) else 0.0

            print(f"  -> Sparar till Supabase: {ticker} ({namn}) | Pris: {nuvarande_pris} | Target: {target} | Potential: {potential}%")
            
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
            time.sleep(0.2)

        except Exception as sub_e:
            print(f"  -> FEL vid bearbetning av {ticker}: {sub_e}")

    print(f"\n--- Test klart! Sparade rader: {sparade} ---")

if __name__ == "__main__":
    kör_us500_test()