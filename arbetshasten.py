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
    print("--- Startar detaljerad EOD-felsökning ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    test_tickers = ["AAPL.US", "MSFT.US", "NVDA.US"]
    nu_tid = datetime.now().isoformat()
    sparade = 0

    for ticker in test_tickers:
        print(f"\nUndersöker ticker: {ticker}")

        try:
            # Använd EODHD:s officiella filter för senaste slutpris
            url_eod = f"https://eodhd.com/api/eod/{ticker}?api_token={EODHD_API_KEY}&filter=last_close&fmt=json"
            res_eod = requests.get(url_eod)
            
            print(f"  - EOD Statuskod: {res_eod.status_code}")
            print(f"  - EOD Svarstext: {res_eod.text}")

            if res_eod.status_code != 200:
                print("  -> EOD-anropet misslyckades.")
                continue

            # Försök tolka värdet
            try:
                nuvarande_pris = float(res_eod.json() or 0)
            except Exception:
                # Om filter inte returnerar en ren float direkt utan struktur
                data = res_eod.json()
                if isinstance(data, list) and len(data) > 0:
                    nuvarande_pris = float(data[-1].get("close", 0) or 0)
                elif isinstance(data, dict):
                    nuvarande_pris = float(data.get("close", 0) or data.get("last_close", 0) or 0)
                else:
                    nuvarande_pris = 0.0

            print(f"  - Tolkat Pris: {nuvarande_pris}")

            if nuvarande_pris <= 0:
                print("  -> Hoppar över: Inget giltigt pris hittades")
                continue

            # Hämta fundamenta för namn och sektor
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

            print(f"  -> Sparar till Supabase: {ticker} ({namn}), Pris: {nuvarande_pris}")
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

    print(f"\n--- Test klart! Totalt sparade rader i Supabase: {sparade} ---")


if __name__ == "__main__":
    kör_us500_test()