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
    print("--- Startar fokuserat US-test med korrekt .US-format ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    exchange_code = "US"
    url = f"https://eodhd.com/api/exchange-symbol-list/{exchange_code}?api_token={EODHD_API_KEY}&fmt=json&type=common_stock"
    
    print(f"Hämtar ticker-lista för {exchange_code}...")
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Kunde inte hämta ticker-lista för {exchange_code}. Statuskod: {response.status_code}")
        return

    data = response.json()
    print(f"Hittade {len(data)} st råa objekt. Testar de första 5 st...")
    
    nu_tid = datetime.now().isoformat()
    sparade = 0

    # Vi loopar igenom de första 5 objekten direkt från listan för att få åtkomst till "Code"
    for item in data[:5]:
        code = item.get("Code")
        if not code:
            continue
            
        # EODHD kräver .US för amerikanska aktier i grunddata-endpoints
        ticker = f"{code}.US"
        print(f"\nUndersöker ticker: {ticker}")

        try:
            url_fund = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
            res_fund = requests.get(url_fund)
            print(f"  - Fundamentals statuskod: {res_fund.status_code}")

            if res_fund.status_code != 200:
                print(f"  -> Hoppar över p.g.a. statuskod {res_fund.status_code}")
                continue

            fund_data = res_fund.json()
            if not fund_data or "General" not in fund_data:
                print("  -> Hoppar över: Saknar 'General' i data")
                continue

            general = fund_data.get("General", {})
            highlights = fund_data.get("Highlights", {})
            analyst_ratings = fund_data.get("AnalystRatings", {})

            nuvarande_pris = float(highlights.get("LatestPrice", 0) or 0)
            print(f"  - LatestPrice från highlights: {nuvarande_pris}")
            
            if nuvarande_pris <= 0:
                rt_url = f"https://eodhd.com/api/real-time/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
                rt_res = requests.get(rt_url)
                print(f"  - Real-time statuskod: {rt_res.status_code}")
                if rt_res.status_code == 200:
                    rt_data = rt_res.json()
                    nuvarande_pris = float(rt_data.get("close", 0) or 0)
                    print(f"  - Pris från real-time: {nuvarande_pris}")

            if nuvarande_pris <= 0:
                print("  -> Hoppar över: Priset är fortfarande 0")
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

    print(f"\n--- US-test klart! Totalt sparade rader i Supabase: {sparade} ---")


if __name__ == "__main__":
    kör_us500_test()