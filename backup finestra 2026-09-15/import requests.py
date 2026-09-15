import requests

# Din API-nyckel
api_key = '6a244666476a74.09380176'
ticker = 'AAPL.US' # Vi testar med Apple

# URL för att hämta fundamentala data
url = f'https://eodhd.com/api/fundamentals/{ticker}?api_token={api_key}&fmt=json'

# Anropa API:et
response = requests.get(url)

# Kolla om det fungerade
if response.status_code == 200:
    data = response.json()
    
    # Här plockar vi ut lite info
    name = data.get('General', {}).get('Name')
    target_price = data.get('AnalystRatings', {}).get('TargetPrice')
    
    print(f"Hämtade data för: {name}")
    print(f"Analytikernas riktkurs: {target_price}")
else:
    print(f"Det blev fel! Statuskod: {response.status_code}")