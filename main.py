import json
import os
from datetime import datetime, timedelta, timezone
import time
import pytz
from core.forexfactory_news_fetcher import get_forex_week_filename, get_forex_calendar
from core.trading_strategy import TradingStrategy
from core.trading_strategy_sandwich import TradingStrategySandwich
from core.symbol_selector import SymbolSelector
from core.trading_engine import TradingEngine
from core.mt5_client import MT5Client
import logging

# Configuration
DATA_DIR = "weekly_news_json"
TIMEZONE_UTC = pytz.utc

# Crée le dossier logs s'il n'existe pas
os.makedirs('logs', exist_ok=True)
# Configuration des logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Ajoute un handler pour écrire dans un fichier
log_filename = f'logs/logfile_zenlion_news_{datetime.now().strftime("%d-%m-%Y_%H-%M")}.txt'
file_handler = logging.FileHandler(log_filename) 
file_handler.setLevel(logging.INFO)  # Niveau de log que tu veux enregistrer dans le fichier

# Crée un format pour le fichier de log (tu peux le personnaliser si besoin)
file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)

# Ajoute ce handler au root logger
logging.getLogger().addHandler(file_handler)


def get_last_sunday():
    """Retourne le dimanche dernier en UTC"""
    now = datetime.now(timezone.utc)
    return now - timedelta(days=(now.weekday() + 1) % 7)


def get_week_filename():
    """Génère le nom du fichier JSON pour la semaine courante"""
    sunday = get_last_sunday()
    return os.path.join(DATA_DIR, f"forex_{sunday.strftime('%Y-%m-%d')}.json")


def load_news_file(filename):
    """Charge le fichier JSON"""
    with open(filename, 'r') as f:
        data = json.load(f)
    return data

def news_processed(title, filename):
    """Marque une news comme traitée en ajoutant un champ 'processed'"""
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = False

    for news in data:
        if news.get('title') == title:
            news['processed'] = {
                'status': True,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            updated = True
            break

    if updated:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    else:
        logging.warning(f"[WARN] Titre '{title}' non trouvé dans le fichier '{filename}'")
    
    

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
    # print(f"{news['title']} et le temps écoulé : {elapsed}")
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
    tradingEngine = TradingEngine()
    

    try:
        while True:
            try:
                # Trade uniquement les jours de semaine
                now = datetime.now(timezone.utc)
                if now.weekday() not in [5, 6]:
                    # 1. Charger le fichier de la semaine
                    filename = get_forex_week_filename()
                    filename = f"weekly_news_json/{filename}"
                    if not os.path.exists(filename):
                        logging.error(f"Fichier non trouvé: {filename}")
                        continue
                    
                    news_data = load_news_file(filename)
                    
                    # 2. Filtrer les news d'aujourd'hui
                    todays_news = get_todays_news(news_data)
                    logging.info(f"Found {len(todays_news)} news today")

                    mock_data(todays_news)
                    
                    # 3. Vérifier les news à traiter
                    for news in todays_news:
                        if should_trigger(news):
                            logging.info(f"\n=== NEWS TRIGGER ===")
                            logging.info(f"Title: {news['title']}")
                            logging.info(f"Time (UTC): {news['date_utc']}")
                            logging.info(f"Country: {news['country']}")
                            logging.info(f"Impact: {news.get('impact', 'N/A')}")
                            
                            # Ici vous ajoutez votre logique de trading
                            if news['impact'] == 'High':
                                comment = news['title'][:10]
                                symbol, trend = symbolSelector.get_best_symbol(news['country'])
                                if symbol and trend:
                                    logging.info(f">>> Executing HIGH impact strategy --> {symbol}: {comment}")
                                    tradingStrategy = TradingStrategy(symbol, comment)
                                    result = tradingStrategy.execute_strategy(trend)
                                    if result:
                                        news_processed(news['title'], filename)


                            #launch sandwich strategy
                            symbol = symbolSelector.get_symbol_from_news_currency(news['country'])
                            if symbol:
                                logging.info(f">>> Executing Sandwich strategy --> {symbol}")
                                tradingStrategySandwich = TradingStrategySandwich(symbol, "sandwich")
                                result = tradingStrategySandwich.execute_strategy()
                            else:
                                logging.warning(f"No symbol found for country: {news['country']}")

                #Récupère le nouveau fichier de news le dimanche soir à 20H30 UTC
                if now.weekday() == 6 and now.hour == 20 and now.minute == 30:
                    get_forex_calendar()
                    logging.info(">>> Téléchargement du calendrier Forex hebdo")
                    time.sleep(90)

                tradingEngine.close_positions_after_45min()
                time.sleep(60)
            except Exception as e:
                logging.exception("Une erreur s'est produite dans la boucle principale.")
                time.sleep(60)
    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    main()

