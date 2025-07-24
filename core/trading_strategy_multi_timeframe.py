import pandas as pd
import pandas_ta as ta
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime
from core.trading_engine import TradingEngine
import logging



class TradingStrategyMultiTimeframe:
    def __init__(self, symbol, comment):
        self.engine = TradingEngine()
        self.symbol = symbol
        self.news_data = None
        self.comment = comment


    def detect_trend(self, symbol):
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


    def calculate_sl_tp(self, direction, volatility_multiplier=1, tp_ratio=1.2):
        """
        Calcule les prix de SL et TP basés sur la volatilité récente.
        
        :param direction: "buy" ou "sell"
        :param volatility_multiplier: Multiplicateur de la volatilité (ex: 1.5x)
        :param tp_ratio: Ratio TP/SL (ex: 2 pour un RR 1:2)
        :return: (sl_price, tp_price)
        """
        volatility = self.get_volatility(self.symbol)  # Volatilité en pips
        pip_size = self.get_pip_size(self.symbol)

        #min_distance = self.get_minimum_distance(self.symbol, pip_size)

        volatility_in_pips = volatility / pip_size
        sl_pips = volatility_in_pips * volatility_multiplier
        tp_pips = sl_pips * tp_ratio

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logging.error(f"Erreur : pas de tick pour {self.symbol}")
            return (None, None, None)
        entry_price = tick.ask if direction == "buy" else tick.bid
        
        if direction == "buy":
            sl_price = entry_price - (sl_pips * pip_size)  # SL en dessous du prix
            tp_price = entry_price + (tp_pips * pip_size)  # TP au-dessus
        elif direction == "sell":
            sl_price = entry_price + (sl_pips * pip_size)  # SL au-dessus du prix
            tp_price = entry_price - (tp_pips * pip_size)  # TP en dessous
        
        return (sl_price, tp_price, entry_price)
    

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

        return (sl_price, tp_price)


    
    
    def get_pip_size(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            logging.error(f"Erreur : pas d'info pour {symbol}")
            return 0.0001  # Valeur par défaut
        digits = info.digits
        return 0.01 if digits == 3 or digits == 2 else 0.0001
    

    def execute_strategy(self, trend):
        ################################################ DEV ##################################################
        #trend="buy" 
        ################################################ DEV ##################################################
        if not trend:
           logging.info(f"Pas de trend détecté sur {self.symbol}")
           return
        sl, tp, price = self.calculate_sl_tp(trend)
        initial_trade = self.engine.place_order(self.symbol, trend, 0.01, sl, tp, self.comment)
        if initial_trade:
            return True
        else:
            logging.error("FAIL - Erreur lors du placement du trade initial.")
            logging.warning(f"SL: {sl}, TP: {tp}, Price: {price}")
            return False
