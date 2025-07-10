import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime
from core.trading_engine import TradingEngine
import logging



class TradingStrategySandwich:
    def __init__(self, symbol, comment):
        self.engine = TradingEngine()
        self.symbol = symbol
        self.news_data = None
        self.comment = comment



    
    def get_high_and_low(self, timeframe=mt5.TIMEFRAME_M1, lookback=5):
        # Récupération des dernières bougies
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            logging.error("Pas assez de données pour calculer high/low")
            return None, None

        # Calcul du plus haut et plus bas
        highs = [bar['high'] for bar in rates]
        lows = [bar['low'] for bar in rates]
        highest = max(highs)
        lowest = min(lows)

        # Taille du pip
        pip_size = self.get_pip_size(self.symbol)

        # Application du buffer de 3 pips
        breakout_high = highest + (3 * pip_size)
        breakout_low = lowest - (3 * pip_size)

        return breakout_high, breakout_low


    def get_volatility(self, symbol, timeframe=mt5.TIMEFRAME_M1, lookback=3):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            logging.error("Erreur : données de volatilité insuffisantes.")
            return 0
        highs = rates['high']
        lows = rates['low']
        return float(np.max(highs) - np.min(lows))
    

    def get_minimum_distance(self, pip_size):
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logging.error(f"Erreur : symbol_info non trouvé pour {self.symbol}")
            return (None, None, None)
        return symbol_info.stops_level * pip_size

    

    def calculate_sl_tp_from_price(self, direction, entry_price, volatility_multiplier=1, tp_ratio=1.2):
        """
        Calcule les SL/TP à partir d’un prix donné, plutôt que du prix marché.
        """
        volatility = self.get_volatility(self.symbol)
        pip_size = self.get_pip_size(self.symbol)
        volatility_in_pips = volatility / pip_size
        sl_pips = volatility_in_pips * volatility_multiplier
        tp_pips = sl_pips * tp_ratio
    

        if direction == "buy":
            sl_price = entry_price - (sl_pips * pip_size)
            tp_price = entry_price + (tp_pips * pip_size)
        else:
            sl_price = entry_price + (sl_pips * pip_size)
            tp_price = entry_price - (tp_pips * pip_size)

        return sl_price, tp_price


    
    
    def get_pip_size(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            logging.error(f"Erreur : pas d'info pour {symbol}")
            return 0.0001  # Valeur par défaut
        digits = info.digits
        return 0.01 if digits == 3 or digits == 2 else 0.0001
    

    def execute_strategy(self):
        ################################################ DEV ##################################################
        #trend="buy" 
        ################################################ DEV ##################################################
        high, low = self.get_high_and_low(self.symbol)

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logging.error(f"Erreur : pas de tick pour {self.symbol}")
            return (None, None, None)


        sl_high, tp_high, price_high = self.calculate_sl_tp_from_price("buy", high)
        sl_low, tp_low, price_low = self.calculate_sl_tp_from_price("sell", low)


        low_trade = self.engine.place_pending_order(self.symbol, "sell", 0.01, sl_low, tp_low, f"{self.comment}-Low", low, tick.bid)
        high_trade = self.engine.place_pending_order(self.symbol, "buy", 0.01, sl_high, tp_high, f"{self.comment}-High", high, tick.ask)

        if low_trade:
            logging.info("OK - Low Trade placé avec succès.")
        else:
            logging.error("FAIL - Erreur lors du placement du low trade.")
            logging.warning(f"SL: {sl_low}, TP: {tp_low}, Price: {price_low}")
        
        if high_trade:
            logging.info("OK - High Trade placé avec succès.")
        else:
            logging.error("FAIL - Erreur lors du placement du high trade.")
            logging.warning(f"SL: {sl_high}, TP: {tp_high}, Price: {price_high}")
        return low_trade, high_trade
