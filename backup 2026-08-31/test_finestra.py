import yfinance as yf
import pandas as pd
import time
import csv

# 1. Hämta alla S&P 500 tickers
table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
tickers = table[0]['Symbol'].tolist()

print(f"Startar analys av {len(tickers)} bolag...")

# 2. Öppna en fil för att spara resultaten
with open('analys_resultat.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Ticker', 'Potential', 'Nuvarande', 'Target', 'Sektor'])

    for t in tickers:
        try:
            stock = yf.Ticker(t)
            info = stock.info
            
            current = info.get('currentPrice')
            target = info.get('targetMeanPrice')
            sector = info.get('sector', 'N/A')
            
            if current and target:
                potential = ((target - current) / current) * 100
                writer.writerow([t, round(potential, 2), current, target, sector])
                print(f"Klar med {t}: {potential:.1f}%")
            
            # Pausa en sekund för att inte bli bannad
            time.sleep(1)
            
        except Exception as e:
            print(f"Kunde inte hämta {t}: {e}")

print("Analysen är klar! Filen 'analys_resultat.csv' har skapats.")