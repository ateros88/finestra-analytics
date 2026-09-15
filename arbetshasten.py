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
    """Hämtar historisk dagsdata (5 år) för sektor-ETF:er via EODHD och sparar i Supabase."""
    print("--- Startar historisk sektor-uppdatering via EODHD ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariabler.")
        return

    # Standardiserade ticker-format för ETF:er i USA hos EODHD (t.ex. XLK.US)
    etf_tickers = [
        "XLK.US",
        "XLF.US",
        "XLV.US",
        "XLY.US",
        "XLP.US",
        "XLI.US",
        "XLE.US",
        "XLU.US",
        "XLB.US",
        "XLRE.US",
    ]
    
    idag = datetime.now().strftime("%Y-%m-%d")
    poster_att_spara = []

    for ticker in etf_tickers:
        try:
            # EODHD Endpoint för historisk dagsdata
            url = f"https://eodhd.com/api/eod/{ticker}?api_token={EODHD_API_KEY}&fmt=json&period=d"
            response = requests.get(url)

            if response.status_code != 200:
                print(f"Kunde inte hämta historik för sektor {ticker}. Statuskod: {response.status_code}")
                continue

            history_data = response.json()
            if not isinstance(history_data, list):
                continue

            # Vi kan begränsa till t.ex. de senaste 5 åren eller ta alla som kommer
            for row in history_data:
                datum_str = row.get("date")
                pris = row.get("adjusted_close") or row.get("close")

                if not datum_str or not pris:
                    continue

                poster_att_spara.append({
                    "datum": datum_str,
                    "ticker": ticker.replace(".US", ""), # Sparar utan .US om din tabell vill ha det rent
                    "pris": float(pris)
                })

            print(f"Hämtade {len(history_data)} punkter för {ticker}")
            time.sleep(0.2)

        except Exception as sub_e:
            print(f"Kunde inte bearbeta sektor {ticker}: {sub_e}")

    # Skicka in allt i Supabase i batchar med upsert
    if poster_att_spara:
        batch_storlek = 500
        for i in range(0, len(poster_att_spara), batch_storlek):
            batch = poster_att_spara[i:i + batch_storlek]
            supabase.table("sektor_historik").upsert(
                batch, on_conflict="datum,ticker"
            ).execute()
        
        print(f"Sparade/uppdaterade totalt {len(poster_att_spara)} rader i 'sektor_historik'.")

    print("--- Sektor-uppdatering klar ---")


def kör_eod_analys():
    """Hämtar kurser, målkurser och rekar från EODHD och uppdaterar 'analyser_eod'."""
    print("--- Startar EODHD aktieanalys & uppdatering ---")

    if not EODHD_API_KEY:
        print("FEL: EODHD_API_KEY saknas i miljövariablerna.")
        return

    try:
        response = supabase.table("analyser_eod").select("*").execute()
        analyser = response.data

        if not analyser:
            print("Inga aktier hittades i 'analyser_eod'-tabellen.")
            return

        nu_tid = datetime.now().isoformat()

        for row in analyser:
            raw_ticker = row["ticker"]
            if not raw_ticker:
                continue
            ticker = str(raw_ticker).strip().upper()

            try:
                url = f"https://eodhd.com/api/fundamentals/{ticker}?api_token={EODHD_API_KEY}&fmt=json"
                response = requests.get(url)

                if response.status_code != 200:
                    print(f"Kunde inte hämta data för {ticker} från EODHD. Statuskod: {response.status_code}")
                    continue

                data = response.json()
                if not data or "General" not in data:
                    print(f"VARNING: Hittade ingen giltig data för {ticker} hos EODHD.")
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
                    print(f"Hittade inget giltigt pris för {ticker}.")
                    continue

                gammalt_pris = float(row.get("nuvarande", 0) or 0)

                # Sanity Check (40% spärren)
                if gammalt_pris > 0:
                    procentuell_forandring = (abs(nuvarande_pris - gammalt_pris) / gammalt_pris) * 100
                    if procentuell_forandring > 40:
                        print(f"STOPP: Extrem prisavvikelse för {ticker}! Gammalt: {gammalt_pris}, Nytt: {nuvarande_pris}. Blockerad.")
                        continue

                target = float(analyst_ratings.get("TargetPrice", 0) or 0)
                strong_buy = int(analyst_ratings.get("StrongBuy", 0) or 0)
                buy = int(analyst_ratings.get("Buy", 0) or 0)
                antal_koprek = strong_buy + buy

                namn = general.get("Name", row.get("name"))
                sektor = general.get("Sector", row.get("sektor"))
                valuta = general.get("Currency", row.get("valuta", "SEK"))

                if target > 0 and nuvarande_pris > 0:
                    potential = round(((target - nuvarande_pris) / nuvarande_pris) * 100, 2)
                else:
                    target = 0.0
                    potential = 0.0

                supabase.table("analyser_eod").update({
                    "nuvarande": nuvarande_pris,
                    "target": target,
                    "potential": potential,
                    "antal_koprek": antal_koprek,
                    "name": namn,
                    "sektor": sektor,
                    "valuta": valuta,
                    "senast_uppdaterad": nu_tid,
                }).eq("ticker", ticker).execute()

                print(f"Uppdaterade {ticker}: Kurs {nuvarande_pris:.2f}, Riktkurs {target:.2f}, Potential {potential:.1f}%, Köprekar: {antal_koprek}")
                time.sleep(0.3)

            except Exception as sub_e:
                print(f"Kunde inte bearbeta aktie {ticker}: {sub_e}")

    except Exception as e:
        print(f"Fel vid hämtning från tabellen 'analyser_eod': {e}")

    print("--- EODHD aktieanalys klar ---")


if __name__ == "__main__":
    uppdatera_sektor_historik_eod()
    kör_eod_analys()