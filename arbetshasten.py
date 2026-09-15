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

def hamta_valuta_fran_suffix(symbol):
    """Bestämmer reservvaluta baserat på aktiens börssuffix om API saknar valuta."""
    if symbol.endswith(".ST"): return "SEK"
    if symbol.endswith(".OL"): return "NOK"
    if symbol.endswith(".CO"): return "DKK"
    if symbol.endswith(".HE") or symbol.endswith(".DE"): return "EUR"
    if symbol.endswith(".L"): return "GBP"
    return "USD"

def hamta_alla_tickers():
    """Hämtar dynamiskt aktier från officiella index för USA, UK, Tyskland, Sverige, Norge, Danmark och Finland."""
    print("-> Hämtar globala aktielistor från nätet...")
    tickers = set()

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 1. USA (S&P 500)
    try:
        res = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=headers)
        if res.status_code == 200:
            df = pd.read_html(io.StringIO(res.text))[0]
            sp = df["Symbol"].astype(str).str.replace(".", "-", regex=False) + ".US"
            tickers.update(sp.tolist())
            print(f"   [USA] Hämtade {len(sp)} bolag från S&P 500")
    except Exception as e:
        print(f"   [USA] Fel vid hämtning: {e}")

    # 2. STORBRITANNIEN (FTSE 100)
    try:
        res = requests.get("https://en.wikipedia.org/wiki/FTSE_100_Index", headers=headers)
        if res.status_code == 200:
            tables = pd.read_html(io.StringIO(res.text))
            for df in tables:
                col = next((c for c in df.columns if str(c).upper() in ["EPIC", "TICKER", "HEADER"]), None)
                if col:
                    ftse = df[col].astype(str).str.strip().apply(lambda x: f"{x}.L" if not x.endswith(".L") else x)
                    tickers.update(ftse.tolist())
                    print(f"   [UK] Hämtade {len(ftse)} bolag från FTSE 100")
                    break
    except Exception as e:
        print(f"   [UK] Fel vid hämtning: {e}")

    # 3. TYSKLAND (DAX 40 & MDAX)
    for url, label in [("https://en.wikipedia.org/wiki/DAX", "DAX"), ("https://en.wikipedia.org/wiki/MDAX", "MDAX")]:
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                tables = pd.read_html(io.StringIO(res.text))
                for df in tables:
                    col = next((c for c in df.columns if any(k in str(c).lower() for k in ["ticker", "symbol"])), None)
                    if col:
                        de = df[col].astype(str).str.strip().apply(lambda x: x if "." in x else f"{x}.DE")
                        tickers.update(de.tolist())
                        print(f"   [DE] Hämtade {len(de)} bolag från {label}")
                        break
        except Exception as e:
            print(f"   [DE] Fel vid hämtning av {label}: {e}")

    # 4. SVERIGE (OMX Stockholm Large & Mid Cap)
    try:
        res = requests.get("https://sv.wikipedia.org/wiki/Nasdaq_Stockholm", headers=headers)
        if res.status_code == 200:
            tables = pd.read_html(io.StringIO(res.text))
            se_count = 0
            for df in tables:
                col = next((c for c in df.columns if any(k in str(c).lower() for k in ["kortnamn", "ticker", "symbol", "bolag"])), None)
                if col and len(df) > 5:
                    sample_val = str(df[col].iloc[0])
                    if len(sample_val) < 15 and not " " in sample_val.strip():
                        se_list = df[col].astype(str).str.strip().apply(lambda x: f"{x}.ST" if not x.endswith(".ST") else x)
                        tickers.update(se_list.tolist())
                        se_count += len(se_list)
            print(f"   [SE] Hämtade {se_count} bolag från Stockholm Large/Mid Cap")
    except Exception as e:
        print(f"   [SE] Fel vid hämtning: {e}")

    # 5. NORGE (OBX Index)
    try:
        res = requests.get("https://en.wikipedia.org/wiki/OBX_Index", headers=headers)
        if res.status_code == 200:
            tables = pd.read_html(io.StringIO(res.text))
            for df in tables:
                col = next((c for c in df.columns if any(k in str(c).lower() for k in ["ticker", "symbol", "code"])), None)
                if col:
                    obx = df[col].astype(str).str.strip().apply(lambda x: f"{x}.OL" if not x.endswith(".OL") else x)
                    tickers.update(obx.tolist())
                    print(f"   [NO] Hämtade {len(obx)} bolag från OBX")
                    break
    except Exception as e:
        print(f"   [NO] Fel vid hämtning: {e}")

    # 6. DANMARK (OMX Copenhagen 25)
    try:
        res = requests.get("https://en.wikipedia.org/wiki/OMX_Copenhagen_25", headers=headers)
        if res.status_code == 200:
            tables = pd.read_html(io.StringIO(res.text))
            for df in tables:
                col = next((c for c in df.columns if any(k in str(c).lower() for k in ["ticker", "symbol", "code"])), None)
                if col:
                    c25 = df[col].astype(str).str.strip().apply(lambda x: f"{x}.CO" if not x.endswith(".CO") else x)
                    tickers.update(c25.tolist())
                    print(f"   [DK] Hämtade {len(c25)} bolag från OMXC25")
                    break
    except Exception as e:
        print(f"   [DK] Fel vid hämtning: {e}")

    # 7. FINLAND (OMX Helsinki 25)
    try:
        res = requests.get("https://en.wikipedia.org/wiki/OMX_Helsinki_25", headers=headers)
        if res.status_code == 200:
            tables = pd.read_html(io.StringIO(res.text))
            for df in tables:
                col = next((c for c in df.columns if any(k in str(c).lower() for k in ["ticker", "symbol", "code"])), None)
                if col:
                    h25 = df[col].astype(str).str.strip().apply(lambda x: f"{x}.HE" if not x.endswith(".HE") else x)
                    tickers.update(h25.tolist())
                    print(f"   [FI] Hämtade {len(h25)} bolag från OMXH25")
                    break
    except Exception as e:
        print(f"   [FI] Fel vid hämtning: {e}")

    return sorted(list(tickers))

def kör_global_pipeline():
    print("=== Startar Finestra Analytics Global Pipeline ===")
    start_tid = time.time()

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariablerna.")
        return

    raw_tickers = hamta_alla_tickers()
    nu_tid = datetime.now().isoformat()

    batch_buffer = []
    totalt_sparade = 0
    BATCH_SIZE = 50

    for i, symbol in enumerate(raw_tickers, 1):
        eod_symbol = symbol
        
        # Yahoo Finance kräver ren symbol för USA (t.ex. AAPL), men behåller suffix för Europa (.ST, .DE, .L etc.)
        if symbol.endswith(".US"):
            yahoo_symbol = symbol.replace(".US", "")
        else:
            yahoo_symbol = symbol

        try:
            # 1. Hämta pris via Yahoo Finance fast_info
            ticker_yf = yf.Ticker(yahoo_symbol)
            nuvarande_pris = 0.0

            try:
                fast_info = ticker_yf.fast_info
                nuvarande_pris = float(fast_info.get("lastPrice", 0) or fast_info.get("previousClose", 0) or 0)
            except Exception:
                pass

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

            # Default-värden med säkerställd valuta utifrån börssuffix
            namn = yahoo_symbol
            sektor = "Okänd"
            valuta = hamta_valuta_fran_suffix(eod_symbol)
            target = 0.0
            antal_koprek = 0

            # 2. Hämta Fundamenta & Target Price från EODHD
            url_fund = f"https://eodhd.com/api/fundamentals/{eod_symbol}?api_token={EODHD_API_KEY}&fmt=json"
            res_fund = requests.get(url_fund)

            if res_fund.status_code == 200:
                fund_data = res_fund.json()
                if fund_data and "General" in fund_data:
                    general = fund_data.get("General", {})
                    analyst_ratings = fund_data.get("AnalystRatings", {})

                    namn = general.get("Name", yahoo_symbol)
                    sektor = general.get("Sector", "Okänd")
                    
                    eod_valuta = general.get("CurrencyCode", "") or general.get("Currency", "")
                    if eod_valuta:
                        valuta = eod_valuta

                    target = float(analyst_ratings.get("TargetPrice", 0) or 0)

                    strong_buy = int(analyst_ratings.get("StrongBuy", 0) or 0)
                    buy = int(analyst_ratings.get("Buy", 0) or 0)
                    antal_koprek = strong_buy + buy

            # 3. Fallback till Yahoo Info om EODHD saknar data / köprekommendationer
            try:
                yf_info = ticker_yf.info
                if target == 0.0:
                    target = float(yf_info.get("targetMeanPrice", 0) or 0)
                if namn == yahoo_symbol:
                    namn = yf_info.get("shortName", yahoo_symbol)
                    sektor = yf_info.get("sector", sektor)
                
                if antal_koprek == 0:
                    num_analysts = int(yf_info.get("numberOfAnalystOpinions", 0) or 0)
                    rec_key = str(yf_info.get("recommendationKey", "")).lower()
                    if rec_key in ["buy", "strong_buy"]:
                        antal_koprek = num_analysts if num_analysts > 0 else 1
            except Exception:
                pass

            # OMVANDLING: Omräkning från pence (GBp / GBX) till pund (GBP / £) för brittiska aktier (.L)
            if eod_symbol.endswith(".L") or valuta in ["GBp", "GBX"]:
                nuvarande_pris = nuvarande_pris / 100.0
                target = target / 100.0
                valuta = "GBP"

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

            print(f"[{i}/{len(raw_tickers)}] {eod_symbol} ({namn}) | Pris: {nuvarande_pris:.2f} {valuta} | Target: {target:.2f} | Potential: {potential}% | Köprek: {antal_koprek}")

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
    print(f"   GLOBAL KÖRNING KLAR!")
    print(f"   Totalt uppdaterade bolag i Supabase: {totalt_sparade}")
    print(f"   Tidsatgång: {tidsatgang} sekunder")
    print(f"==========================================")

if __name__ == "__main__":
    kör_global_pipeline()