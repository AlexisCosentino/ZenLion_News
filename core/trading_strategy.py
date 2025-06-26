import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from core.trading_engine import TradingEngine


class TradingStrategy:
    def __init__(self, symbol, comment):
        self.engine = TradingEngine()
        self.symbol = symbol
        self.news_data = None
        self.comment = comment
        self.initial_direction = None
        self.initial_price = None
        self.hedge_active = False
        self.grid_trades_done = []
        self.grid_levels= [20, 40, 60]  # Pips entre chaque grid
        self.max_drawdown = 50            # Pips avant hedge



    def detect_trend(self, symbol, timeframe=mt5.TIMEFRAME_M1, lookback=3):
        """Détecte la tendance sur les dernières 'lookback' bougies M1."""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            print("Erreur : Données MT5 insuffisantes.")
            return None
        
        df = pd.DataFrame(rates)
        df['bullish'] = df['close'] > df['open']
        df['bearish'] = df['close'] < df['open']
        
        # Règle de tendance : 2/3 bougies dans la même direction + momentum
        if df['bullish'].sum() >= 2 and (df['close'].iloc[-1] > df['high'].iloc[:-1].mean()):
            return "buy"
        elif df['bearish'].sum() >= 2 and (df['close'].iloc[-1] < df['low'].iloc[:-1].mean()):
            return "sell"
        return None


    def get_volatility(self, symbol, timeframe=mt5.TIMEFRAME_M1, lookback=3):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            print("Erreur : données de volatilité insuffisantes.")
            return 0
        highs = [bar['high'] for bar in rates]
        lows = [bar['low'] for bar in rates]
        return max(highs) - min(lows)


    def calculate_sl_tp(self, direction, volatility_multiplier=1.5, tp_ratio=2):
        """
        Calcule les prix de SL et TP basés sur la volatilité récente.
        
        :param direction: "buy" ou "sell"
        :param volatility_multiplier: Multiplicateur de la volatilité (ex: 1.5x)
        :param tp_ratio: Ratio TP/SL (ex: 2 pour un RR 1:2)
        :return: (sl_price, tp_price)
        """
        volatility = self.get_volatility(self.symbol)  # Volatilité en pips
        pip_size = self.get_pip_size(self.symbol)
        volatility_in_pips = volatility / pip_size
        sl_pips = volatility_in_pips * volatility_multiplier
        tp_pips = sl_pips * tp_ratio

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            print(f"Erreur : pas de tick pour {self.symbol}")
            return (None, None, None)
        entry_price = tick.ask if direction == "buy" else tick.bid
        
        if direction == "buy":
            sl_price = entry_price - (sl_pips * pip_size)  # SL en dessous du prix
            tp_price = entry_price + (tp_pips * pip_size)  # TP au-dessus
        elif direction == "sell":
            sl_price = entry_price + (sl_pips * pip_size)  # SL au-dessus du prix
            tp_price = entry_price - (tp_pips * pip_size)  # TP en dessous
        
        return (sl_price, tp_price, entry_price)
    

    def calculate_sl_tp_from_price(self, direction, entry_price, volatility_multiplier=1.5, tp_ratio=2):
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
            print(f"Erreur : pas d'info pour {symbol}")
            return 0.0001  # Valeur par défaut
        digits = info.digits
        return 0.01 if digits == 3 or digits == 2 else 0.0001
    

    def place_pending_grid_orders(self):
        pip_size = self.get_pip_size(self.symbol)
        for level in self.grid_levels:
            grid_price = self.initial_price - (level * pip_size) if self.initial_direction == "buy" else self.initial_price + (level * pip_size)
            sl, tp = self.calculate_sl_tp_from_price(self.initial_direction, grid_price)

            self.engine.place_pending_order(self.symbol, self.initial_direction, 0.01, sl, tp, f"grid_{level}", grid_price, self.initial_price)

            print(f"[GRID] Pending order placé à {grid_price:.5f} ({level} pips)")
            self.grid_trades_done.append(level)


    def place_pending_hedge_order(self):
        pip_size = self.get_pip_size(self.symbol)
        direction = "sell" if self.initial_direction == "buy" else "buy"
        hedge_price = self.initial_price - (self.max_drawdown * pip_size) if self.initial_direction == "buy" else self.initial_price + (self.max_drawdown * pip_size)
        sl_pips = 10
        tp_pips = 50
        sl = hedge_price + sl_pips * pip_size if direction == "sell" else hedge_price - sl_pips * pip_size
        tp = hedge_price - tp_pips * pip_size if direction == "sell" else hedge_price + tp_pips * pip_size

        self.engine.place_pending_order(self.symbol, direction, 0.01, sl, tp, "hedge", hedge_price, self.initial_price)
        print(f"[HEDGE] Pending hedge order placé à {hedge_price:.5f}")
        

    def execute_strategy(self):
        trend = self.detect_trend(self.symbol)

        if not trend:
            return

        sl, tp, price = self.calculate_sl_tp(self.symbol, trend)
        initial_trade = self.engine.place_order(self.symbol, trend, 0.01, sl, tp, self.comment)

        if initial_trade:
            self.initial_direction = trend
            self.initial_price = price
            self.hedge_active = False
            print("✅ Trade initial placé avec succès.")

            # Placer les pending orders directement après
            self.place_pending_grid_orders()
            self.place_pending_hedge_order()
        else:
            print("❌ Erreur lors du placement du trade initial.")
