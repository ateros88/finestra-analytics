from datetime import datetime
import io
import os
import time
from dotenv import load_dotenv
from supabase import create_client
import requests
import yfinance as yf
import pandas as pd

# Ladda miljövariabler (.env)
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
EODHD_API_KEY = os.getenv("EODHD_API_KEY")

def hämta_us500_tickers():
    """Hämtar den aktuella listan på alla S&P 500-bolag från Wikipedia."""
    print("-> Hämtar US500 (S&P 500) aktielista...")
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        # Custom User-Agent header för att undvika HTTP 403 Forbidden
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers)
        
        if res.status_code == 200:
            tables = pd.read_html(io.StringIO(res.text))
            df = tables[0]
            tickers = df['Symbol'].tolist()
            print(f"-> Hittade {len(tickers)} bolag i S&P 500.")
            return tickers
        else:
            raise Exception(f"HTTP Status {res.status_code}")
            
    except Exception as e:
        print(f"FEL vid hämtning av S&P 500-lista: {e}")
        return ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK.B", "JNJ", "V"]

def kör_us500_pipeline():
    print("=== Startar Finestra Analytics US500 Pipeline ===")
    start_tid = time.time()

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariablerna.")
        return

    raw_tickers = hämta_us500_tickers()
    nu_tid = datetime.now().isoformat()

    batch_buffer = []
    totalt_sparade = 0
    BATCH_SIZE = 50

    for i, symbol in enumerate(raw_tickers, 1):
        # Formatkonvertering (t.ex. BRK.B -> BRK-B för Yahoo, BRK-B.US för EODHD)
        clean_symbol = symbol.replace(".", "-")
        yahoo_symbol = clean_symbol
        eod_symbol = f"{clean_symbol}.US"

        try:
            # 1. Hämta exakt ojusterad slutkurs via Yahoo Finance fast_info
            ticker_yf = yf.Ticker(yahoo_symbol)
            nuvarande_pris = 0.0

            try:
                fast_info = ticker_yf.fast_info
                nuvarande_pris = float(fast_info.get("lastPrice", 0) or fast_info.get("previousClose", 0) or 0)
            except Exception:
                pass

            # Fallback till history om fast_info saknar data
            if nuvarande_pris <= 0:
                try:
                    hist = ticker_yf.history(period="1d", auto_adjust=False)
                    if not hist.empty:
                        nuvarande_pris = float(hist["Close"].iloc[-1])
                except Exception:
                    pass

            if nuvarande_pris <= 0:
                print(f"[{i}/{len(raw_tickers)}] Hoppar över {eod_symbol}: Inget giltigt pris från Yahoo Finance.")
                continue

            # 2. Hämta Fundamenta & Target Price från EODHD
            namn = yahoo_symbol
            sektor = "Okänd"
            valuta = "USD"
            target = 0.0
            antal_koprek = 0

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

            # Fallback till Yahoo Info om EODHD saknar data
            if target == 0.0 or namn == yahoo_symbol:
                try:
                    yf_info = ticker_yf.info
                    if target == 0.0:
                        target = float(yf_info.get("targetMeanPrice", 0) or 0)
                    if namn == yahoo_symbol:
                        namn = yf_info.get("shortName", yahoo_symbol)
                        sektor = yf_info.get("sector", sektor)
                except Exception:
                    pass

            potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2) if (target > 0 and nuvarande_pris > 0) else 0.0

            # Lägg till i batch
            batch_buffer.append({
                "ticker": eod_symbol,
                "nuvarande": round(nuvarande_pris, 2),
                "target": round(target, 2),
                "potential": potential,
                "antal_koprek": antal_koprek,
                "name": namn,
                "sektor": sektor,
                "valuta": valuta,
                "senast_uppdaterad": nu_tid,
            })

            print(f"[{i}/{len(raw_tickers)}] {eod_symbol} ({namn}) | Pris: {nuvarande_pris:.2f} | Target: {target:.2f} | Potential: {potential}%")

            # Sänd till Supabase i grupper om 50
            if len(batch_buffer) >= BATCH_SIZE:
                supabase.table("analyser_eod").upsert(batch_buffer, on_conflict="ticker").execute()
                totalt_sparade += len(batch_buffer)
                print(f"---> [SUPABASE] Sparade batch om {len(batch_buffer)} bolag! (Totalt sparade: {totalt_sparade})")
                batch_buffer = []

            time.sleep(0.05)

        except Exception as e:
            print(f"[{i}/{len(raw_tickers)}] FEL vid bearbetning av {eod_symbol}: {e}")

    # Sänd sista batchen om det finns kvarvarande rader
    if batch_buffer:
        supabase.table("analyser_eod").upsert(batch_buffer, on_conflict="ticker").execute()
        totalt_sparade += len(batch_buffer)
        print(f"---> [SUPABASE] Sparade sista batch om {len(batch_buffer)} bolag!")

    tidsatgang = round(time.time() - start_tid, 1)
    print(f"\n==========================================")
    print(f"   US500 KÖRNING KLAR!")
    print(f"   Totalt uppdaterade bolag i Supabase: {totalt_sparade}")
    print(f"   Tidsatgång: {tidsatgang} sekunder")
    print(f"==========================================")

if __name__ == "__main__":
    kör_us500_pipeline()