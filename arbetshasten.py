from datetime import datetime
import os
import time
from dotenv import load_dotenv
from supabase import create_client
import yfinance as yf

# Ladda miljövariabler
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def uppdatera_sektor_historik():
    """Hämtar historisk dagsdata (5 år) för sektor-ETF:erna och sparar/uppdaterar i Supabase."""
    etf_tickers = [
        "XLK",
        "XLF",
        "XLV",
        "XLY",
        "XLP",
        "XLI",
        "XLE",
        "XLU",
        "XLB",
        "XLRE",
    ]
    idag = datetime.now().strftime("%Y-%m-%d")

    print(f"--- Startar historisk sektor-uppdatering: {idag} ---")

    try:
        # Hämta 5 års historik för alla tickers på en gång
        df_all = yf.download(
            etf_tickers, period="5y", interval="1d", progress=False, group_by="ticker"
        )

        if df_all.empty:
            print("Kunde inte hämta data från yfinance för sektorer.")
            return

        poster_att_spara = []

        for t in etf_tickers:
            try:
                if len(etf_tickers) == 1:
                    df_t = df_all.copy()
                else:
                    df_t = df_all[t].copy()

                df_t = df_t.dropna(subset=["Close"])
                if df_t.empty:
                    continue

                # Loopa igenom varje dag i historiken
                for datum_index, row in df_t.iterrows():
                    datum_str = datum_index.strftime("%Y-%m-%d")
                    pris = float(row["Close"])

                    poster_att_spara.append({
                        "datum": datum_str,
                        "ticker": t,
                        "pris": pris
                    })

                print(f"Behandlat {t}: {len(df_t)} datapunkter")

            except Exception as sub_e:
                print(f"Kunde inte bearbeta sektor {t}: {sub_e}")

        # Skicka in allt i Supabase i batchar med upsert för att undvika dubbletter
        if poster_att_spara:
            batch_storlek = 500
            for i in range(0, len(poster_att_spara), batch_storlek):
                batch = poster_att_spara[i:i + batch_storlek]
                supabase.table("sektor_historik").upsert(
                    batch, on_conflict="datum,ticker"
                ).execute()
            
            print(f"Sparade/uppdaterade totalt {len(poster_att_spara)} rader i 'sektor_historik'.")

    except Exception as e:
        print(f"Fel vid sektor-uppdatering: {e}")

    print("--- Sektor-uppdatering klar ---")


def kör_analys():
    """Hämtar aktuella kurser och riktkurser, kollar avvikelser,

    hanterar saknade riktkurser, sätter tidsstämpel och uppdaterar Supabase.
    """
    print("--- Startar aktieanalys & uppdatering av kurser ---")

    try:
        response = supabase.table("analyser").select("*").execute()
        analyser = response.data

        if not analyser:
            print("Inga aktier hittades i 'analyser'-tabellen.")
            return

        nu_tid = datetime.now().isoformat()

        for row in analyser:
            raw_ticker = row["ticker"]
            if not raw_ticker:
                continue
            ticker = str(raw_ticker).strip().upper()

            try:
                t_obj = yf.Ticker(ticker)
                stock = t_obj.history(period="1d")

                if stock.empty:
                    print(
                        f"VARNING: Hittade ingen historik för {ticker}. Tar bort från databasen."
                    )
                    supabase.table("analyser").delete().eq("ticker", ticker).execute()
                    continue

                nuvarande_pris = float(stock["Close"].iloc[-1])
                gammalt_pris = float(row.get("nuvarande", 0))

                # Sanity Check: Prisavvikelse på över 40%
                if gammalt_pris > 0:
                    procentuell_forandring = (
                        abs(nuvarande_pris - gammalt_pris) / gammalt_pris
                    ) * 100
                    if procentuell_forandring > 40:
                        print(
                            f"STOPP: Extrem prisavvikelse för {ticker}! Gammalt: {gammalt_pris}, Nytt: {nuvarande_pris} ({procentuell_forandring:.1f}% förändring). Uppdatering blockerad."
                        )
                        continue

                # Hämta färsk riktkurs från yfinance info
                try:
                    info = t_obj.info
                    ny_target = info.get("targetMeanPrice")
                    if not ny_target or ny_target <= 0:
                        target = float(row.get("target", 0))
                    else:
                        target = float(ny_target)
                except Exception:
                    target = float(row.get("target", 0))

                # Säkerhetskontroll för riktkurs & potential
                if target > 0 and nuvarande_pris > 0:
                    potential = ((target - nuvarande_pris) / nuvarande_pris) * 100
                    potential = round(potential, 2)
                else:
                    target = 0.0
                    potential = 0.0
                    print(
                        f"OBS: Saknar giltig riktkurs för {ticker}. Sätter potential till 0."
                    )

                # Uppdatera i Supabase inklusive tidsstämpel
                supabase.table("analyser").update({
                    "nuvarande": nuvarande_pris,
                    "target": target,
                    "potential": potential,
                    "senast_uppdaterad": nu_tid,
                }).eq("ticker", ticker).execute()

                print(
                    f"Uppdaterade {ticker}: Kurs {nuvarande_pris:.2f}, Riktkurs {target:.2f}, Potential {potential:.1f}%"
                )

                # Liten paus för att inte trigga rate limits hos Yahoo Finance
                time.sleep(0.5)

            except Exception as e:
                print(f"Kunde inte uppdatera aktie {ticker}: {e}")

    except Exception as e:
        print(f"Fel vid hämtning från tabellen 'analyser': {e}")

    print("--- Aktieanalys klar ---")


if __name__ == "__main__":
    uppdatera_sektor_historik()
    kör_analys()