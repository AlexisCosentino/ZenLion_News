import json
import os
from datetime import datetime, timedelta, timezone
import time
import pytz
from core.forexfactory_news_fetcher import get_forex_week_filename, get_forex_calendar
from core.trading_strategy import TradingStrategy
from core.symbol_selector import SymbolSelector
from core.mt5_client import MT5Client

# Configuration
DATA_DIR = "weekly_news_json"
TIMEZONE_UTC = pytz.utc

def get_last_sunday():
    """Retourne le dimanche dernier en UTC"""
    now = datetime.now(timezone.utc)
    return now - timedelta(days=(now.weekday() + 1) % 7)


def get_week_filename():
    """Génère le nom du fichier JSON pour la semaine courante"""
    sunday = get_last_sunday()
    return os.path.join(DATA_DIR, f"forex_{sunday.strftime('%Y-%m-%d')}.json")


def load_news_file(filename):
    """Charge le fichier JSON et convertit les dates en UTC"""
    with open(filename, 'r') as f:
        data = json.load(f)
    
    for news in data:
        if 'date' in news:
            try:
                # Convertit la date en UTC
                dt = datetime.fromisoformat(news['date'])
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                else:
                    dt = dt.astimezone(TIMEZONE_UTC)
                news['date_utc'] = dt.isoformat()
            except ValueError:
                news['date_utc'] = None
    return data


def get_todays_news(news_data):
    """Filtre les news pour aujourd'hui en UTC"""
    today = datetime.now(timezone.utc).date()
    return [news for news in news_data 
            if news.get('date_utc') and 
            datetime.fromisoformat(news['date_utc']).date() == today]


def should_trigger(news, minutes=5):
    """Vérifie si on est dans la fenêtre de déclenchement"""
    now = datetime.now(timezone.utc)
    news_time = datetime.fromisoformat(news['date_utc']).astimezone(TIMEZONE_UTC)
    elapsed = (now - news_time).total_seconds() / 60
    print(f"{news['title']} et le temps écoulé : {elapsed}")
    return minutes <= elapsed < minutes+1


def mock_data(todays_news):
    # maintenant en UTC -4
    now_utc_minus_4 = datetime.now(timezone.utc) - timedelta(hours=4) + timedelta(minutes=5)

    mocked_news = {
        'title': 'mocked data test',
        'country': 'USD',
        'date': now_utc_minus_4.isoformat(timespec='seconds').replace('+00:00', '-04:00'),
        'impact': 'High',
        'forecast': '-1.2M',
        'previous': '-11.5M',
        'date_utc': (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec='seconds')
    }

    todays_news.append(mocked_news)
    return todays_news

def main():
    mt5 = MT5Client()
    mt5.initialize_mt5()
    symbolSelector = SymbolSelector()
    

    try:
        while True:
            # Trade uniquement les jours de semaine
            now = datetime.now(timezone.utc)
            if now.weekday != 5 or now.weekday != 6:
                # 1. Charger le fichier de la semaine
                filename = get_forex_week_filename()
                filename = f"weekly_news_json/{filename}"
                if not os.path.exists(filename):
                    print(f"Fichier non trouvé: {filename}")
                    return
                
                news_data = load_news_file(filename)
                
                # 2. Filtrer les news d'aujourd'hui
                todays_news = get_todays_news(news_data)
                print(f"Found {len(todays_news)} news today")

                mock_data(todays_news)
                
                # 3. Vérifier les news à traiter
                for news in todays_news:
                    if should_trigger(news):
                        print(f"\n=== NEWS TRIGGER ===")
                        print(f"Title: {news['title']}")
                        print(f"Time (UTC): {news['date_utc']}")
                        print(f"Country: {news['country']}")
                        print(f"Impact: {news.get('impact', 'N/A')}")
                        
                        # Ici vous ajoutez votre logique de trading
                        if news['impact'] == 'High':
                            comment = news['title'][:10]
                            symbol = symbolSelector.get_best_symbol(news['country'])
                            print(f">>> Executing HIGH impact strategy --> {symbol}: {comment}")
                            tradingStrategy = TradingStrategy(symbol, comment)
                            tradingStrategy.execute_strategy()
            #Récupère le nouveau fichier de news le dimanche soir à 20H30 UTC
            if now.weekday == 6 and now.hour == 20 and now.minute == 30:
                get_forex_calendar()
            time.sleep(60)

                
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

