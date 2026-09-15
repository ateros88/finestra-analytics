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
    print("--- Hämtar riktiga kurser direkt från EODHD Fundamentals ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    test_tickers = ["AAPL.US", "MSFT.US", "NVDA.US", "GOOGL.US", "AMZN.US"]
    nu_tid = datetime.now().isoformat()
    sparade = 0

    for ticker in test_tickers:
        print(f"\nUndersöker ticker: {ticker}")

        try:
            # Hämta fundamenta för tickern
            url_fund = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
            res_fund = requests.get(url_fund)
            
            if res_fund.status_code != 200:
                print(f"  -> Kunde inte hämta (Status: {res_fund.status_code})")
                continue

            fund_data = res_fund.json()
            if not fund_data or "General" not in fund_data:
                continue

            general = fund_data.get("General", {})
            highlights = fund_data.get("Highlights", {})
            technical = fund_data.get("Technical", {})
            analyst_ratings = fund_data.get("AnalystRatings", {})

            # Hämta aktiekurs direkt från Highlights eller Technicals
            # EODHD lagrar ofta senaste slutpris i Highlights under 'SharePrice' eller liknande, 
            # alternativt kan vi läsa 50DayMA / nuvarande pris direkt från Technical om det finns.
            # Låt oss kolla om 'SharePrice' eller motsvarande finns i Highlights:
            nuvarande_pris = float(
                highlights.get("SharePrice", 0) or 
                technical.get("CurrentPrice", 0) or 
                highlights.get("MarketCapitalization", 0) and 0 or 
                0
            )

            # Om nyckeln heter något annat i just denna struktur, kika på Valuation eller Technical
            if nuvarande_pris <= 0:
                # Fallback: EODHD har ibland priset under Valuation eller som Close i tekniska data
                nuvarande_pris = float(technical.get("Price", 0) or 0)

            # Om vi vill ha exakt rätt slutpris via fundamentals filter kan vi även anropa med ?filter=Highlights::SharePrice
            target = float(analyst_ratings.get("TargetPrice", 0) or 0)
            strong_buy = int(analyst_ratings.get("StrongBuy", 0) or 0)
            buy = int(analyst_ratings.get("Buy", 0) or 0)
            antal_koprek = strong_buy + buy

            namn = general.get("Name", ticker)
            sektor = general.get("Sector", "Okänd")
            valuta = general.get("Currency", "USD")

            potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2) if (target > 0 and nuvarande_pris > 0) else 0.0

            print(f"  -> {ticker} ({namn}) | Pris: {nuvarande_pris} | Target: {target} | Potential: {potential}%")
            
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
            time.sleep(0.1)

        except Exception as sub_e:
            print(f"  -> FEL: {sub_e}")

    print(f"\n--- Klart! Sparade rader: {sparade} ---")

if __name__ == "__main__":
    kör_us500_test()