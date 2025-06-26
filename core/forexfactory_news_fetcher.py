import requests
import json
from datetime import datetime, timedelta
import schedule
import time

def get_forex_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()  # Vérifie les erreurs HTTP
        
        data = response.json()
        
        # Sauvegarde dans un fichier avec timestamp
        filename = get_forex_week_filename()
        filename = f"weekly_news_json/{filename}"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
            
        print(f"Calendrier récupéré et sauvegardé dans {filename}")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération du calendrier: {e}")
        return None

def schedule_weekly_download():
    # Planifie l'exécution tous les dimanches à 8h du matin
    schedule.every().sunday.at("08:05").do(get_forex_calendar)
    
    print("Programmation activée - récupération tous les dimanches à 08:00")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Vérifie toutes les minutes


def get_forex_week_filename():
    """Retourne le nom du fichier pour la semaine Forex actuelle"""
    today = datetime.now()
    
    # Trouver le dimanche de la semaine courante (0=lundi en Python, donc ajustement)
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    
    # Format: forex_YYYY-MM-DD_semaine.json (où la date est le dimanche)
    return f"forex_{sunday.strftime('%Y-%m-%d')}.json"