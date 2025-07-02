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
        return any(pos["symbol"] == symbol for pos in positions)
    

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
                logging.info(f"[{country}] Symbole sélectionné : {symbol}")
                return symbol, trend

            # Aucun symbole n’a satisfait les conditions
            logging.warning(f"[{country}] Aucun symbole éligible (position ouverte ou pas de trend).")
            return None

        else:
            logging.warning(f'{country} pas supporté par ZenLion !')
            return None