from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client
import yfinance as yf

# Ladda miljövariabler
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def uppdatera_sektor_historik():
  """Hämtar dagens kurs för de viktigaste sektor-ETF:erna och sparar/uppdaterar i Supabase."""
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

  print(f"--- Startar sektor-uppdatering: {idag} ---")

  for t in etf_tickers:
    try:
      ticker_obj = yf.Ticker(t)
      data = ticker_obj.history(period="1d")

      if not data.empty:
        pris = float(data["Close"].iloc[-1])

        befintlig = (
            supabase.table("sektor_historik")
            .select("id")
            .eq("datum", idag)
            .eq("ticker", t)
            .execute()
        )

        if befintlig.data:
          supabase.table("sektor_historik").update({"pris": pris}).eq(
              "datum", idag
          ).eq("ticker", t).execute()
          print(f"Uppdaterade {t}: {pris:.2f}")
        else:
          supabase.table("sektor_historik").insert(
              {"datum": idag, "ticker": t, "pris": pris}
          ).execute()
          print(f"Sparade ny {t}: {pris:.2f}")
      else:
        print(f"Kunde inte hämta data för {t}")
    except Exception as e:
      print(f"Fel vid uppdatering av {t}: {e}")

  print("--- Sektor-uppdatering klar ---")


def kör_analys():
  """Hämtar aktuella kurser och riktkurser för dina aktier från yfinance,

  kollar avvikelser, rensar döda tickers och uppdaterar Supabase.
  """
  print("--- Startar aktieanalys & uppdatering av kurser ---")

  try:
    response = supabase.table("analyser").select("*").execute()
    analyser = response.data

    if not analyser:
      print("Inga aktier hittades i 'analyser'-tabellen.")
      return

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
              f"VARNING: Hittade ingen historik för {ticker}. Tar bort från"
              " databasen."
          )
          supabase.table("analyser").delete().eq("ticker", ticker).execute()
          continue

        nuvarande_pris = float(stock["Close"].iloc[-1])
        gammalt_pris = float(row.get("nuvarande", 0))

        if gammalt_pris > 0:
          procentuell_forandring = (
              abs(nuvarande_pris - gammalt_pris) / gammalt_pris
          ) * 100
          if procentuell_forandring > 40:
            print(
                f"STOPP: Extrem prisavvikelse för {ticker}! Gammalt:"
                f" {gammalt_pris}, Nytt: {nuvarande_pris}"
                f" ({procentuell_forandring:.1f}% förändring). Uppdatering"
                " blockerad."
            )
            continue

        try:
          info = t_obj.info
          ny_target = info.get("targetMeanPrice")
          if not ny_target or ny_target <= 0:
            target = float(row.get("target", 0))
          else:
            target = float(ny_target)
        except Exception:
          target = float(row.get("target", 0))

        if target > 0:
          potential = ((target - nuvarande_pris) / nuvarande_pris) * 100
        else:
          potential = float(row.get("potential", 0))

        supabase.table("analyser").update({
            "nuvarande": nuvarande_pris,
            "target": round(target, 2),
            "potential": round(potential, 2),
        }).eq("ticker", ticker).execute()

        print(
            f"Uppdaterade {ticker}: Kurs {nuvarande_pris:.2f}, Riktkurs"
            f" {target:.2f}, Potential {potential:.1f}%"
        )

      except Exception as e:
        print(f"Kunde inte uppdatera aktie {ticker}: {e}")

  except Exception as e:
    print(f"Fel vid hämtning från tabellen 'analyser': {e}")

  print("--- Aktieanalys klar ---")


if __name__ == "__main__":
  uppdatera_sektor_historik()
  kör_analys()