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


def uppdatera_sektor_historik_eod():
    """Hämtar historisk dagsdata för marknadsindex via EODHD och sparar i Supabase."""
    print("--- Startar historisk sektor-uppdatering via EODHD ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    index_tickers = ["GSPC.INDX", "IXIC.INDX", "STOXX50E.INDX"]
    poster_att_spara = []

    for ticker in index_tickers:
        try:
            url = f"https://eodhd.com/api/eod/{ticker}?api_token={EODHD_API_KEY}&fmt=json&period=d"
            response = requests.get(url)

            if response.status_code != 200:
                print(f"Kunde inte hämta historik för {ticker}. Statuskod: {response.status_code}")
                continue

            history_data = response.json()
            if not isinstance(history_data, list):
                continue

            for row in history_data:
                datum_str = row.get("date")
                pris = row.get("adjusted_close") or row.get("close")

                if not datum_str or not pris:
                    continue

                poster_att_spara.append({
                    "datum": datum_str,
                    "ticker": ticker.replace(".INDX", ""),
                    "pris": float(pris)
                })

            print(f"Hämtade {len(history_data)} punkter för {ticker}")
            time.sleep(0.2)

        except Exception as sub_e:
            print(f"Kunde inte bearbeta index {ticker}: {sub_e}")

    if poster_att_spara:
        batch_storlek = 500
        for i in range(0, len(poster_att_spara), batch_storlek):
            batch = poster_att_spara[i:i + batch_storlek]
            supabase.table("sektor_historik").upsert(
                batch, on_conflict="datum,ticker"
            ).execute()
        print(f"Sparade totalt {len(poster_att_spara)} rader i 'sektor_historik'.")

    print("--- Sektor-uppdatering klar ---")


def hamta_tickers_fran_bors(exchange_code):
    """Hämtar aktiva vanliga aktier från EODHD för en specifik börs."""
    url = f"https://eodhd.com/api/exchange-symbol-list/{exchange_code}?api_token={EODHD_API_KEY}&fmt=json&type=common_stock"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        tickers = []
        for item in data:
            code = item.get("Code")
            exchange = item.get("Exchange")
            if code and exchange:
                tickers.append(f"{code}.{exchange}")
        return tickers
    else:
        print(f"Kunde inte hämta ticker-lista för {exchange_code}. Statuskod: {response.status_code}")
        return []


def kör_eod_analys():
    """Hämtar marknader/tickers dynamiskt och sparar/uppdaterar 'analyser_eod'."""
    print("--- Startar dynamisk EODHD aktieanalys & uppdatering ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    # Uppdaterade och korrekta börskoder för Norden, Europa, USA och Kanada (gruvbolag)
    borser = [
        "ST",      # Sverige (Stockholm)
        "HE",      # Finland (Helsingfors)
        "CO",      # Danmark (Köpenhamn)
        "OL",      # Norge (Oslo)
        "XETRA",   # Tyskland
        "PA",      # Frankrike (Paris)
        "LSE",     # Storbritannien (London)
        "US",      # USA
        "TO"       # Kanada (Toronto - gruvbolag)
    ]
    
    alla_tickers_raw = []

    for bors in borser:
        print(f"Hämtar tickers för börs: {bors}...")
        tickers = hamta_tickers_fran_bors(bors)
        print(f"Hittade {len(tickers)} st för {bors}")
        alla_tickers_raw.extend(tickers)

    # Rensa dubbletter om ett bolag finns på flera ställen
    alla_tickers = list(set(alla_tickers_raw))

    if not alla_tickers:
        print("Inga tickers hittades från börserna.")
        return

    print(f"Totalt {len(alla_tickers)} unika tickers att bearbeta. Startar analys...")
    nu_tid = datetime.now().isoformat()

    for raw_ticker in alla_tickers:
        ticker = str(raw_ticker).strip().upper()

        try:
            url = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
            response = requests.get(url)

            if response.status_code != 200:
                continue

            data = response.json()
            if not data or "General" not in data:
                continue

            general = data.get("General", {})
            highlights = data.get("Highlights", {})
            analyst_ratings = data.get("AnalystRatings", {})

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
            valuta = general.get("Currency", "SEK")

            if target > 0 and nuvarande_pris > 0:
                potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2)
            else:
                target = 0.0
                potential = 0.0

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

            print(f"Sparade/Uppdaterade {ticker} ({namn}): Kurs {nuvarande_pris:.2f}")
            time.sleep(0.1)

        except Exception as sub_e:
            print(f"Kunde inte bearbeta aktie {ticker}: {sub_e}")

    print("--- EODHD aktieanalys klar ---")


if __name__ == "__main__":
    uppdatera_sektor_historik_eod()
    kör_eod_analys()