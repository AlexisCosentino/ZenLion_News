import pandas as pd
import pandas_ta as ta
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from core.trading_engine import TradingEngine
import logging



class TradingStrategyMultiTimeframeV2:
    def __init__(self, comment, news_country):
        self.engine = TradingEngine()
        self.symbol
        self.news_country = news_country
        self.news_data = None
        self.comment = comment
        self.symbol_priority = {
            'USD': ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD'],
            'EUR': ['EURUSD', 'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD', 'EURCAD', 'EURNZD'],
            'GBP': ['GBPUSD', 'EURGBP', 'GBPJPY', 'GBPCHF', 'GBPAUD', 'GBPCAD'],
            'JPY': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY', 'CADJPY', 'NZDJPY'],
            'CHF': ['USDCHF', 'EURCHF', 'GBPCHF'],
            'AUD': ['AUDUSD', 'EURAUD', 'AUDJPY', 'GBPAUD'],
            'CAD': ['USDCAD', 'EURCAD', 'CADJPY', 'GBPCAD'],
            'NZD': ['NZDUSD', 'EURNZD', 'NZDJPY'],
            'CNY': ['USDCNH', 'AUDUSD'] 
        }

        
    def check_if_open_position(self, symbol):
        positions = mt5.positions_get()
        if positions is None:
            return False
        return any(pos.symbol == symbol for pos in positions)
    
    
    def get_best_symbol_multi_timeframe(self, country_news):
        """Retourne le meilleur symbole à trader selon la news (pays concerné)."""
        country = country_news.upper()  # Exemple : 'USD', 'EUR', etc.

        # 1. Vérifie si on a une liste prioritaire de symboles pour ce pays
        if country in self.symbol_priority:
            for symbol in self.symbol_priority[country]:
                # Vérifie que le symbole existe
                if mt5.symbol_info(symbol) is None:
                    logging.debug(f"[{country}] Symbole non disponible sur MT5 : {symbol}")
                    continue

                
                # Vérifie qu'aucune position n'est déjà ouverte
                open_position = self.check_if_open_position(symbol)
                if open_position:
                    logging.debug(f"[{country}] Position déjà ouverte sur {symbol}, skip.")
                    continue

                # Vérifie qu'un trade est détecté par la stratégie
                trend = self.detect_trend_multi_timeframe(symbol)
                if not trend:
                    logging.debug(f"[{country}] Pas de trend détecté sur {symbol}, skip.")
                    continue

                # Tout est bon, on retourne ce symbole et sa trend
                logging.info(f"[{country}] Symbole sélectionné : {symbol}, trend : {trend}")
                return symbol, trend

            # Aucun symbole n’a satisfait les conditions
            logging.warning(f"[{country}] Aucun symbole éligible (position ouverte ou pas de trend).")
            return None

        else:
            logging.warning(f'{country} pas supporté par ZenLion !')
            return None



    def get_trend(self, df):
        df['ma50'] = df['close'].rolling(window=50).mean()
        df['ma100'] = df['close'].rolling(window=100).mean()

        if df['ma50'].iloc[-1] > df['ma100'].iloc[-1]:
            return "bullish"
        elif df['ma50'].iloc[-1] < df['ma100'].iloc[-1]:
            return "bearish"
        else:
            return "range"
    
    def detect_range(self, df, window= 24):
        segment = df.tail(window)
        range_high = segment['high'].max()
        range_low = segment['low'].min()
        return range_high, range_low
    
    def get_best_symbol(self, country_news):
        """Retourne le meilleur symbole à trader selon la news (pays concerné)."""
        country = country_news.upper()  # Exemple : 'USD', 'EUR', etc.
        # 1. Vérifie si on a une liste prioritaire de symboles pour ce pays
        if country in self.symbol_priority:
            for symbol in self.symbol_priority[country]:
                # Vérifie que le symbole existe
                if mt5.symbol_info(symbol) is None:
                    logging.debug(f"[{country}] Symbole non disponible sur MT5 : {symbol}")
                    continue

                # Vérifie qu'aucune position n'est déjà ouverte
                open_position = self.check_if_open_position(symbol)
                if open_position:
                    logging.debug(f"[{country}] Position déjà ouverte sur {symbol}, skip.")
                    continue

                # Tout est bon, on retourne ce symbole
                logging.info(f"[{country}] Symbole sélectionné : {symbol}")
                return symbol

            # Aucun symbole n’a satisfait les conditions
            logging.warning(f"[{country}] Aucun symbole éligible (position ouverte ou pas de trend).")
            return None

        else:
            logging.warning(f'{country} pas supporté par ZenLion !')
            return None


    def execute_strategy(self, news_time):
        self.symbol = self.get_best_symbol(self.news_country)
        if self.symbol:
            m15_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M15, 0, 100))
            h4_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H4, 0, 105))
            d1_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_D1, 0, 105))

            # Conversion des timestamps
            for df in [m15_data, d1_data, h4_data]:
                df['time'] = pd.to_datetime(df['time'], unit='s', utc=True )
                df['time'] = df['time']- timedelta(hours=3)

            # --- Détermination de la tendance ---
            daily_trend = self.get_trend(d1_data)
            h4_trend = self.get_trend(h4_data)

            if daily_trend == h4_trend and daily_trend != "range":
                macro_bias = daily_trend
            else:
                logging.info(f"[{self.symbol}] Pas de trend aligné daily/h4.")
                return
            
            # --- Construction du range avant news ---
            range_end_time = news_time - timedelta(minutes=1)  # Dernière bougie avant la news
            pre_news_bars = m15_data[m15_data['time'] < news_time].tail(24) #6h de data avant la news (6x4 - 15min)
            if pre_news_bars.empty:
                logging.warning(f"[{self.symbol}] Pas assez de données avant la news.")
                return
            
            range_high = pre_news_bars['high'].max()
            range_low = pre_news_bars['low'].min()
            range_size = abs(range_high - range_low)
            # Calcul de l’amplitude
            #if range_size < threshold_min:  # trop serré, news potentiellement violente
            #    is_valid_range = True
            #else:
            #    is_valid_range = False

            # --- Bougie post-news ---
            post_news_candle_m15 = m15_data[m15_data['time'] >= news_time].iloc[0]


            logging.info(f'la bougie m15 suivant la news : {post_news_candle_m15}')


            post_news_close = post_news_candle_m15['close']

            # --- Détection du signal ---
            signal = None
            if macro_bias == "bullish" and post_news_close > range_high:
                signal = "buy"
                sl = range_low
                tp = post_news_close + range_size
            elif macro_bias == "bearish" and post_news_close < range_low:
                signal = "sell"
                sl = range_high
                tp = post_news_close - range_size

            logging.info(f"[{self.symbol}] Bias={macro_bias}, Signal={signal}, Close={post_news_close:.5f}, Range=({range_low:.5f}-{range_high:.5f})")
            #return signal, sl, tp

            if signal is not None:
                logging.info(f">>> Executing HIGH impact strategy --> {self.symbol}: {self.comment}")
                trade = self.engine.place_order(self.symbol, signal, 0.01, sl, tp, self.comment)

