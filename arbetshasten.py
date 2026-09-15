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
    print("--- Startar US-test med EOD-pris och Fundamentals ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    test_tickers = ["AAPL.US", "MSFT.US", "NVDA.US", "GOOGL.US", "AMZN.US", "META.US", "TSLA.US"]
    nu_tid = datetime.now().isoformat()
    sparade = 0

    for ticker in test_tickers:
        print(f"\nUndersöker ticker: {ticker}")

        try:
            # 1. Hämta senaste slutpris via EOD-endpointen (fungerar med standardpaketet)
            url_eod = f"https://eodhd.com/api/eod/{ticker}?api_token={EODHD_API_KEY}&fmt=json&limit=1"
            res_eod = requests.get(url_eod)
            
            nuvarande_pris = 0.0
            if res_eod.status_code == 200:
                eod_data = res_eod.json()
                if isinstance(eod_data, list) and len(eod_data) > 0:
                    nuvarande_pris = float(eod_data[-1].get("close", 0) or 0)
            
            print(f"  - EOD Pris (Close): {nuvarande_pris}")

            if nuvarande_pris <= 0:
                print("  -> Hoppar över: Inget giltigt pris hittades")
                continue

            # 2. Hämta fundamenta för namn, sektor och analyst target price
            url_fund = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
            res_fund = requests.get(url_fund)
            
            target = 0.0
            antal_koprek = 0
            namn = ticker
            sektor = "Okänd"
            valuta = "USD"

            if res_fund.status_code == 200:
                fund_data = res_fund.json()
                if fund_data and "General" in fund_data:
                    general = fund_data.get("General", {})
                    analyst_ratings = fund_data.get("AnalystRatings", {})
                    
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

            # 3. Spara direkt till Supabase
            print(f"  -> Sparar till Supabase: {ticker} ({namn}), Pris: {nuvarande_pris}, Target: {target}")
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
            print("  -> Sparat utan problem!")
            time.sleep(0.1)

        except Exception as sub_e:
            print(f"  -> FEL vid bearbetning av {ticker}: {sub_e}")

    print(f"\n--- US-test klart! Totalt sparade rader i Supabase: {sparade} ---")


if __name__ == "__main__":
    kör_us500_test()