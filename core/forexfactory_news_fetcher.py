import requests
import json
from datetime import datetime, timedelta
from tabulate import tabulate
import schedule
import time
import pytz
import logging


# Configuration
DATA_DIR = "weekly_news_json"
TIMEZONE_UTC = pytz.utc

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
            
        logging.info(f"Calendrier récupéré et sauvegardé dans {filename}")
        process_news(filename)
        save_pretty_news_table(filename)
        return data
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur lors de la récupération du calendrier: {e}")
        return None


def get_forex_week_filename():
    """Retourne le nom du fichier pour la semaine Forex actuelle"""
    today = datetime.now()
    
    # Trouver le dimanche de la semaine courante (0=lundi en Python, donc ajustement)
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    
    # Format: forex_YYYY-MM-DD_semaine.json (où la date est le dimanche)
    return f"forex_{sunday.strftime('%Y-%m-%d')}.json"


def add_utc_date_from_data(data):
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


def upgrade_impact_for_multiple_news(data):
    # Trie les news par pays puis par date
    sorted_news = sorted(data, key=lambda x: (x['country'], x['date_utc']))
    
    i = 0
    while i < len(sorted_news) - 2:
        current = sorted_news[i]
        next1 = sorted_news[i+1]
        next2 = sorted_news[i+2]
        
        # Vérifie si les 3 news suivantes concernent le même pays
        if (current['country'] == next1['country'] == next2['country']):
            dt_current = datetime.fromisoformat(current['date_utc'])
            dt_next1 = datetime.fromisoformat(next1['date_utc'])
            dt_next2 = datetime.fromisoformat(next2['date_utc'])
            
            # Vérifie l'intervalle de temps
            if (dt_next1 - dt_current <= timedelta(minutes=10) and 
                dt_next2 - dt_next1 <= timedelta(minutes=10)):
                
                # Met à jour l'impact pour les 3 news
                current['impact'] = 'High'
                next1['impact'] = 'High'
                next2['impact'] = 'High'
                i += 3  # Passe aux news suivantes
                continue
        i += 1
    return sorted_news


def filter_and_upgrade_special_news(data):
    keywords = ["Powell", "Lagarde", "FOMC", "ECB", "BOJ", "Rate Statement"]
    filtered_data = []
    
    for news in data:
        title = news['title']
        # Vérifie si le titre contient un mot-clé important
        has_keyword = any(keyword in title for keyword in keywords)
        
        if news['impact'] == 'High' or has_keyword:
            if has_keyword:
                news['impact'] = 'High'
            filtered_data.append(news)
    
    return filtered_data


def merge_close_news(data):
    if not data:
        return data
    
    # Trie les news par pays puis par date
    sorted_news = sorted(data, key=lambda x: (x['country'], x['date_utc']))
    merged_news = []
    
    i = 0
    while i < len(sorted_news):
        current = sorted_news[i]
        j = i + 1
        
        # Trouve les news à fusionner
        while j < len(sorted_news):
            next_news = sorted_news[j]
            if current['country'] != next_news['country']:
                break
                
            dt_current = datetime.fromisoformat(current['date_utc'])
            dt_next = datetime.fromisoformat(next_news['date_utc'])
            
            if dt_next - dt_current > timedelta(minutes=10):
                break
                
            # Fusionne les titres
            current['title'] = f"{current['title']} | {next_news['title']}"
            
            # Garde la date la plus récente
            if dt_next > dt_current:
                current['date'] = next_news['date']
                current['date_utc'] = next_news['date_utc']
            
            j += 1
        
        merged_news.append(current)
        i = j
    
    return merged_news


def process_news(filename):
    # Étape 1: Ajouter les dates UTC
    with open(filename, 'r') as f:
        data = json.load(f)
    
    data = add_utc_date_from_data(data)  # Modification ici
    
    # Étape 2: Mettre à jour l'impact pour les groupes de news
    data = upgrade_impact_for_multiple_news(data)
    
    # Étape 3: Filtrer et mettre à jour les news spéciales
    data = filter_and_upgrade_special_news(data)
    
    # Étape 4: Fusionner les news proches
    data = merge_close_news(data)
    
    # Écrire les modifications directement dans le fichier d'origine
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data


def save_pretty_news_table(filename_json):
    # Charger les données JSON

    output_txt = filename_json.replace(".json", ".txt")
    output_txt = output_txt.replace("weekly_news_json/", "weekly_news_pretty/")
    with open(filename_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Trier par date_utc (du plus ancien au plus récent)
    data_sorted = sorted(data, key=lambda x: datetime.fromisoformat(x["date_utc"]))

    # Préparer les lignes du tableau
    table = [
        [entry["title"], entry["country"], entry["impact"], entry["date_utc"]]
        for entry in data_sorted
    ]

    # Définir les en-têtes du tableau
    headers = ["Title", "Country", "Impact", "Date UTC"]

    # Générer le tableau au format texte
    pretty_table = tabulate(table, headers=headers, tablefmt="pretty")

    # Sauvegarder dans un fichier .txt
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(pretty_table)

    logging.info(f"OK - Tableau sauvegardé dans : {output_txt}")
    
    
if __name__ == "__main__":
    # Code à exécuter uniquement si le fichier est lancé directement
    get_forex_calendar()