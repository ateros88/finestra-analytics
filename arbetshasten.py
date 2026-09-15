from datetime import datetime
import os
import time
from dotenv import load_dotenv
from supabase import create_client
import requests
import yfinance as yf

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
EODHD_API_KEY = os.getenv("EODHD_API_KEY")

def kör_us500_test():
    print("--- Startar analys med Yahoo Finance (Pris) + EODHD (Fundamenta) ---")

    # US-tickers (utan .US-suffix för Yahoo, vi lägger till .US för EODHD om det behövs)
    test_tickers = [
        {"yahoo": "AAPL", "eodhd": "AAPL.US"},
        {"yahoo": "MSFT", "eodhd": "MSFT.US"},
        {"yahoo": "NVDA", "eodhd": "NVDA.US"},
        {"yahoo": "GOOGL", "eodhd": "GOOGL.US"},
        {"yahoo": "AMZN", "eodhd": "AMZN.US"},
    ]
    
    nu_tid = datetime.now().isoformat()
    sparade = 0

    for t_info in test_tickers:
        yahoo_symbol = t_info["yahoo"]
        eod_symbol = t_info["eodhd"]
        print(f"\nUndersöker ticker: {eod_symbol}")

        try:
            # 1. Hämta SENASTE PRIS från Yahoo Finance (Gratis, stabilt, inga 403)
            ticker_yf = yf.Ticker(yahoo_symbol)
            hist = ticker_yf.history(period="1d")
            
            nuvarande_pris = 0.0
            if not hist.empty:
                nuvarande_pris = float(hist["Close"].iloc[-1])

            print(f"  - Yahoo Finance Pris: {nuvarande_pris:.2f} USD")

            if nuvarande_pris <= 0:
                print("  -> Hoppar över: Kunde inte hämta giltigt pris från Yahoo Finance")
                continue

            # 2. Hämta TARGET PRICE och Analytikerdata från EODHD Fundamentals
            namn = yahoo_symbol
            sektor = "Okänd"
            valuta = "USD"
            target = 0.0
            antal_koprek = 0

            if EODHD_API_KEY:
                url_fund = f"https://eodhd.com/api/fundamentals/{eod_symbol}?api_token={EODHD_API_KEY}&fmt=json"
                res_fund = requests.get(url_fund)
                
                if res_fund.status_code == 200:
                    fund_data = res_fund.json()
                    if fund_data and "General" in fund_data:
                        general = fund_data.get("General", {})
                        analyst_ratings = fund_data.get("AnalystRatings", {})

                        namn = general.get("Name", yahoo_symbol)
                        sektor = general.get("Sector", "Okänd")
                        valuta = general.get("Currency", "USD")
                        target = float(analyst_ratings.get("TargetPrice", 0) or 0)
                        
                        strong_buy = int(analyst_ratings.get("StrongBuy", 0) or 0)
                        buy = int(analyst_ratings.get("Buy", 0) or 0)
                        antal_koprek = strong_buy + buy

            # Fallback på Target Price från Yahoo om EODHD saknas/är 0
            if target == 0.0:
                yf_info = ticker_yf.info
                target = float(yf_info.get("targetMeanPrice", 0) or 0)
                if namn == yahoo_symbol:
                    namn = yf_info.get("shortName", yahoo_symbol)
                    sektor = yf_info.get("sector", "Okänd")

            potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2) if (target > 0 and nuvarande_pris > 0) else 0.0

            print(f"  -> Sparar till Supabase: {eod_symbol} ({namn}) | Pris: {nuvarande_pris:.2f} | Target: {target:.2f} | Potential: {potential}%")
            
            supabase.table("analyser_eod").upsert({
                "ticker": eod_symbol,
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
            print(f"  -> FEL vid bearbetning av {eod_symbol}: {sub_e}")

    print(f"\n--- Test klart! Sparade rader: {sparade} ---")

if __name__ == "__main__":
    kör_us500_test()