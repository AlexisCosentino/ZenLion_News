import pandas as pd
import os
import json
import pandas_ta as ta
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
from core.trading_engine import TradingEngine
import logging

symbol_list = [
  {
    "symbol": "[SP500]",
    "open_utc_hour": 14,
    "open_utc_minutes":30,
    "range_minutes": 30,
    "volatilite": "élevée",
    "notes": "L'ouverture US est très significative. Les 30 premières minutes souvent explosives. Gap fréquents sur news."
  },
  {
    "symbol": "[NQ100]",
    "open_utc_hour": 14,
    "open_utc_minutes":30,
    "range_minutes": 30,
    "volatilite": "très élevée",
    "notes": "Très nerveux, mouvements rapides. Attention aux faux départs."
  },
  {
    "symbol": "[DJI30]",
    "open_utc_hour": 14,
    "open_utc_minutes":30,
    "range_minutes": 20,
    "volatilite": "élevée",
    "notes": "Moins volatil que Nasdaq mais solide pour trend follow. Gap et news US impactent fort."
  },
  {
    "symbol": "GERMANY40",
    "open_utc_hour": 7,
    "open_utc_minutes":0,
    "range_minutes": 20,
    "volatilite": "modérée à élevée",
    "notes": "L'ouverture européenne définit souvent le ton de la session européenne. Bon pour les gaps sur news macro."
  },
  {
    "symbol": "[CAC40]",
    "open_utc_hour": 7,
    "open_utc_minutes":0,
    "range_minutes": 20,
    "volatilite": "modérée",
    "notes": "Ouverture moins nerveuse que DAX, mais intéressante si news EU/FR importantes."
  },
  {
    "symbol": "[FTSE100]",
    "open_utc_hour": 8,
    "open_utc_minutes":0,
    "range_minutes": 20,
    "volatilite": "modérée",
    "notes": "Moins influent que DAX/CAC pour la liquidité globale, mais solide pour GBP et secteurs UK."
  },
  {
    "symbol": "[JP225]",
    "open_utc_hour": 0,
    "open_utc_minutes":1,
    "range_minutes": 20,
    "volatilite": "modérée",
    "notes": "Ouverture asiatique, moins liquide que US/EU, mais intéressant pour trading pré-US."
  }
]


class TradingStrategyOrb:
    def __init__(self):
        self.engine = TradingEngine()
        self.symbol = None


        
    def trade_already_open(self, symbol):
        positions = mt5.positions_get()
        if positions is None:
            return False
        return any(pos.symbol == symbol for pos in positions)


    def get_server_offset(self, symbol):
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
        server_time = datetime.fromtimestamp(rates[0]['time'], tz=timezone.utc)
        utc_now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        offset_hours = round((server_time - utc_now).total_seconds() / 3600)
        return offset_hours


    def get_trend(self, df):
        df['ma50'] = df['close'].rolling(window=50).mean()
        df['ma100'] = df['close'].rolling(window=100).mean()

        if df['ma50'].iloc[-1] > df['ma100'].iloc[-1]:
            return "bullish"
        elif df['ma50'].iloc[-1] < df['ma100'].iloc[-1]:
            return "bearish"
        else:
            return "range"
    

    def breakout_volume_confirm(df, lookback=10, factor=1.2):
        """
        Vérifie si la bougie de cassure a un volume supérieur à la moyenne des 'lookback' bougies.
        
        df : DataFrame avec colonnes 'tick_volume'
        lookback : nombre de bougies pour calculer le volume moyen
        factor : multiplicateur pour décider si le breakout est significatif
        return : True si cassure valide, False sinon
        """
        volume_avg = df['tick_volume'].tail(lookback).mean()
        last_volume = df['tick_volume'].iloc[-1]
        return last_volume > volume_avg * factor
    
        
    def get_range(self, m1_data, range_minute):
        filename = "daily_range.json"
        range_name = f"{datetime.now().strftime('%Y-%m-%d')}_{self.symbol}_ORB"
        ranges = []

        # Charger l'existant
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    ranges = json.load(f)
            except json.JSONDecodeError:
                logging.error("Erreur lors de l'ouverture de JSON")
        else:
            logging.error("Fichier json de range inexistant")

        # Chercher si déjà stocké
        for r in ranges:
            if r["name"] == range_name:
                return r["low"], r["high"]
        
        segment = m1_data.tail(range_minute)
        high = segment['high'].max()
        low = segment['low'].min()

        # Sinon on ajoute
        new_range = {"name": range_name, "low": low, "high": high, "time_recorded_utc": datetime.now(timezone.utc).strftime('%H-%M')}
        ranges.append(new_range)
        with open(filename, "w") as f:
            json.dump(ranges, f, indent=4)
        return low, high


    def news_soon(self):
        now = datetime.now(timezone.utc)   # toujours en UTC
        sunday = now - timedelta(days=(now.weekday() + 1) % 7)
        news_filename = f"forex_{sunday.strftime('%Y-%m-%d')}.json"
        filename = f"weekly_news_json/{news_filename}"
        if not os.path.exists(filename):
            logging.error(f"Fichier non trouvé: {filename}")
            return False
        with open(filename, 'r') as f:
            data = json.load(f)
        for news in data:
            news_time = datetime.fromisoformat(news["date_utc"])  # déjà en UTC
            if now <= news_time <= now + timedelta(hours=1):
                logging.info(f"News dans 1h: {news['title']} ({news['country']}, impact={news['impact']})")
                return True
        return False
    

    def execute_strategy(self):

        for data in symbol_list:
            signal = None
            self.symbol = data["symbol"]
            now = datetime.now(timezone.utc)
            server_offset = self.get_server_offset(self.symbol)
            # reconstruire datetime du jour pour l'ouverture
            open_utc = now.replace(
                hour=data["open_utc_hour"], 
                minute=data["open_utc_minutes"], 
                second=0, 
                microsecond=0
            )
            start = open_utc + timedelta(minutes=data["range_minutes"])
            end = start + timedelta(hours=1)

            if start < now < end:
                # On est dans la fenetre post range
                if self.trade_already_open(self.symbol):
                    continue
                m1_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, 100))
                h4_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H4, 0, 105))

                # Conversion des timestamps
                for df in [m1_data, h4_data]:
                    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True )
                    df['time'] = df['time']- timedelta(hours=server_offset)

                # --- Détermination de la tendance ---
                h4_trend = self.get_trend(h4_data)
                high, low = self.get_range(m1_data, data["range_minutes"])

                # Calcul ATR sur les données M1
                m1_data['atr'] = ta.atr(high=m1_data['high'], low=m1_data['low'], close=m1_data['close'], length=14)
                atr_value = m1_data['atr'].iloc[-1]

                most_recent_candle = m1_data.iloc[-1]
                range_size = abs(high - low) * 2
                if most_recent_candle['close'] > high and not self.news_soon() and h4_trend == 'bullish' and self.breakout_volume_confirm(h4_data):
                    signal = "buy"
                    sl = low - atr_value
                    tp = most_recent_candle['close'] + (2 * atr_value)
                elif most_recent_candle['close'] < low and not self.news_soon() and h4_trend == 'bearish' and self.breakout_volume_confirm(h4_data):
                    signal = "sell"
                    sl = high + atr_value
                    tp = most_recent_candle['close'] - (2 * atr_value)
                
                if signal is not None:
                    logging.info(f">>> Executing ORB strategy {signal} --> {self.symbol}")
                    logging.info(f">>> Stop-Loss: {sl}, Take-Profit: {tp}, ATR Value: {atr_value}")
                    trade = self.engine.place_order(self.symbol, signal, 0.1, sl, tp, "ORB")
            else:
                print(f"{data['symbol']} -> Pas encore dans la fenêtre")





