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
    print("--- Startar test för att extrahera riktigt pris från Fundamentals ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    test_tickers = ["AAPL.US", "MSFT.US", "NVDA.US", "GOOGL.US", "AMZN.US"]
    nu_tid = datetime.now().isoformat()
    sparade = 0

    for ticker in test_tickers:
        print(f"\nUndersöker ticker: {ticker}")

        try:
            url_fund = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
            res_fund = requests.get(url_fund)
            
            if res_fund.status_code != 200:
                print(f"  -> Kunde inte hämta fundamenta (Status: {res_fund.status_code})")
                continue

            fund_data = res_fund.json()
            if not fund_data or "General" not in fund_data:
                print("  -> Hoppar över: Saknar 'General'")
                continue

            general = fund_data.get("General", {})
            highlights = fund_data.get("Highlights", {})
            valuation = fund_data.get("Valuation", {})
            analyst_ratings = fund_data.get("AnalystRatings", {})

            # Extrahera riktigt pris från Highlights eller Valuation
            nuvarande_pris = float(
                highlights.get("SharePrice", 0) or 
                highlights.get("PriceRelativeToSP500", 0) and 0 or # Fallback-säkring
                valuation.get("PriceBook", 0) and 0 or
                0
            )

            # Om SharePrice ligger under en annan nyckel i Highlights (t.ex. 'PERatio' etc., eller om vi kikar på valuation)
            if nuvarande_pris <= 0:
                # EODHD lägger ibland priset under Valuation -> PE / PEG eller direkt i Highlights som float
                # Låt oss söka säkert:
                nuvarande_pris = float(highlights.get("MarketCapitalization", 0) and 0 or highlights.get("PERatio", 0) and 0 or 0)
                
                # Om vi vill vara helt säkra på vad som finns i Highlights skriver vi ut nycklar om priset är 0
                # Men vi kan också kolla om det finns i General/Highlights:
                # Låt oss sätta en säker hämtning från Valuation om den finns
                pass

            # Alternativ metod för att hitta priset i Highlights om SharePrice är tomt i vissa JSON-strukturer:
            # EODHD har ibland priset under Highlights. 
            # Vi kan även kika om det finns i Valuation. Låt oss skriva ut vad Highlights innehåller för att verifiera direkt i loggen:
            print(f"  - Alla nycklar i Highlights: {list(highlights.keys())[:10]}")
            
            # Försök hämta 'SharePrice' eller liknande
            nuvarande_pris = float(highlights.get("SharePrice", 0) or 0)
            
            # Om det fortfarande är 0, kollar vi om det finns i någon annan känd nyckel
            if nuvarande_pris <= 0:
                # Ibland returneras priset under Valuation eller som 'EPSEstimateCurrentYear' etc., 
                # men låt oss se vad loggen säger för AAPL.US med detta tillägg.
                nuvarande_pris = float(highlights.get("EPSEstimateCurrentYear", 0) or 0) # Bara för test om SharePrice saknas i just detta schema

            target = float(analyst_ratings.get("TargetPrice", 0) or 0)
            strong_buy = int(analyst_ratings.get("StrongBuy", 0) or 0)
            buy = int(analyst_ratings.get("Buy", 0) or 0)
            antal_koprek = strong_buy + buy

            namn = general.get("Name", ticker)
            sektor = general.get("Sector", "Okänd")
            valuta = general.get("Currency", "USD")

            potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2) if (target > 0 and nuvarande_pris > 0) else 0.0

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
            print("  -> Sparat till Supabase!")
            time.sleep(0.1)

        except Exception as sub_e:
            print(f"  -> FEL vid bearbetning av {ticker}: {sub_e}")

    print(f"\n--- Test klart! Sparade rader: {sparade} ---")


if __name__ == "__main__":
    kör_us500_test()