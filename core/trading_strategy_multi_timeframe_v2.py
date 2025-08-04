import pandas as pd
import pandas_ta as ta
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from core.trading_engine import TradingEngine
import logging



class TradingStrategyMultiTimeframeV2:
    def __init__(self, symbol, comment):
        self.engine = TradingEngine()
        self.symbol = symbol
        self.news_data = None
        self.comment = comment


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

    def execute_strategy(self, news_time):
        m15_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M15, 0, 100))
        h4_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H4, 0, 105))
        d1_data = pd.DataFrame(mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_D1, 0, 105))

        # Conversion des timestamps
        for df in [m15_data, d1_data, h4_data]:
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True )

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
        pre_news_bars = m15_data[m15_data['time'] < news_time].tail(24)
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
        post_news_time = news_time + timedelta(minutes=15)  # 1 bougie M15 après la news
        post_news_candle = m15_data[(m15_data['time'] == post_news_time)]
        if post_news_candle.empty:
            logging.warning(f"[{self.symbol}] Bougie post-news manquante.")
            return

        post_news_close = post_news_candle.iloc[0]['close']

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
        return signal, sl, tp
