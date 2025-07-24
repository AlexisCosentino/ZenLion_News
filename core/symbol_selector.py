import MetaTrader5 as mt5
import pandas as pd
import logging

class SymbolSelector:
    def __init__(self):

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
    

    def detect_trend(self, symbol, timeframe=mt5.TIMEFRAME_M1, lookback=3):
        """Détecte la tendance sur les dernières 'lookback' bougies M1."""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            logging.error("Erreur : Données MT5 insuffisantes.")
            return False
        
        df = pd.DataFrame(rates)
        df['bullish'] = df['close'] > df['open']
        df['bearish'] = df['close'] < df['open']
        
        # Règle de tendance : 2/3 bougies dans la même direction + momentum
        if df['bullish'].sum() >= 2 and (df['close'].iloc[-1] > df['high'].iloc[:-1].mean()):
            return "buy"
        elif df['bearish'].sum() >= 2 and (df['close'].iloc[-1] < df['low'].iloc[:-1].mean()):
            return "sell"
        return False
    
    def detect_trend_multi_timeframe(self, symbol):
        m5_data = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50))
        m1_data = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 50))
        m5_data['time'] = pd.to_datetime(m5_data['time'], unit='s')
        m1_data['time'] = pd.to_datetime(m1_data['time'], unit='s')

         # 2) Calcul des indicateurs M5 pour filtrer la tendance macro
        m5_data['MA20'] = m5_data['close'].rolling(20).mean()
        m5_data['MA50'] = m5_data['close'].rolling(50).mean()
        m5_data['MA20_slope'] = m5_data['MA20'].diff()

        # 3) Calcul des indicateurs M1 pour confirmer le momentum
        m1_data['MA10'] = m1_data['close'].rolling(10).mean()
        m1_data['MA30'] = m1_data['close'].rolling(30).mean()
        m1_data['RSI']  = ta.rsi(m1_data['close'], length=14)

        # 4) Détermine la tendance M5
        last_m5 = m5_data.iloc[-1]
        if last_m5['MA20'] > last_m5['MA50'] and last_m5['MA20_slope'] > 0:
            trend_m5 = "buy"
        elif last_m5['MA20'] < last_m5['MA50'] and last_m5['MA20_slope'] < 0:
            trend_m5 = "sell"
        else:
            trend_m5 = None

        # 5) Confirmation M1 + RSI
        last_m1 = m1_data.iloc[-1]
        signal_m1 = None
        if trend_m5 == "buy":
            if last_m1['close'] > last_m1['open'] and 40 < last_m1['RSI'] < 75:
                signal_m1 = "buy"
        elif trend_m5 == "sell":
            if last_m1['close'] < last_m1['open'] and 25 < last_m1['RSI'] < 60:
                signal_m1 = "sell"

        # 6) Décision finale
        if signal_m1 == trend_m5:
            return trend_m5    # "buy" ou "sell"
        else:
            return None  # on passe son tour
    

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

                # Vérifie qu'un trade est détecté par la stratégie
                trend = self.detect_trend(symbol)
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


    def get_symbol_from_news_currency(self, news_currency):
        mapping = {
            'USD': 'EURUSD',
            'EUR': 'EURUSD',
            'GBP': 'GBPUSD',
            'JPY': 'USDJPY',
            'CHF': 'USDCHF',
            'AUD': 'AUDUSD',
            'CAD': 'USDCAD',
            'NZD': 'NZDUSD',
            'CNY': 'USDCNH',  # souvent nommée comme ça chez les brokers
        }
        
        symbol = mapping.get(news_currency.upper())
        if symbol is None:
            raise ValueError(f"Devise non supportée : {news_currency}")
        return symbol
