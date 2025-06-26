import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import threading
import time
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


    def calculate_sl_tp(self, symbol, direction, volatility_multiplier=1.5, tp_ratio=2):
        """
        Calcule les prix de SL et TP basés sur la volatilité récente.
        
        :param direction: "buy" ou "sell"
        :param volatility_multiplier: Multiplicateur de la volatilité (ex: 1.5x)
        :param tp_ratio: Ratio TP/SL (ex: 2 pour un RR 1:2)
        :return: (sl_price, tp_price)
        """
        volatility = self.get_volatility(symbol)  # Volatilité en pips
        pip_size = self.get_pip_size(self.symbol)
        volatility_in_pips = volatility / pip_size
        sl_pips = volatility_in_pips * volatility_multiplier
        tp_pips = sl_pips * tp_ratio

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print(f"Erreur : pas de tick pour {symbol}")
            return (None, None, None)
        entry_price = tick.ask if direction == "buy" else tick.bid
        
        if direction == "buy":
            sl_price = entry_price - (sl_pips * pip_size)  # SL en dessous du prix
            tp_price = entry_price + (tp_pips * pip_size)  # TP au-dessus
        elif direction == "sell":
            sl_price = entry_price + (sl_pips * pip_size)  # SL au-dessus du prix
            tp_price = entry_price - (tp_pips * pip_size)  # TP en dessous
        
        return (sl_price, tp_price, entry_price)
    


    def monitor_trades(self):
        while True:
            time.sleep(5)  # vérifie toutes les 5 secondes
            price = self.engine._get_price(self.symbol, self.initial_direction)

            # Drawdown
            pip_size = self.get_pip_size(self.symbol)
            drawdown = (self.initial_price - price) / pip_size if self.initial_direction == "buy" else (price - self.initial_price) / pip_size
            print(f"[{self.symbol}] Drawdown: {drawdown:.1f} pips")


            # Grid
            for level in self.grid_levels:
                if drawdown >= level and not self.grid_trade_exists(level):
                    self.place_grid_trade(level)

            # Hedge
            if drawdown >= self.max_drawdown and not self.hedge_active:
                self.place_hedge()

            # Check if all trades are closed
            if not self.has_open_trades():
                print(f"Suivi terminé pour {self.symbol} (plus aucun trade actif).")
                break


    def has_open_trades(self):
        positions = self.engine.get_open_positions()
        return any(pos["symbol"] == self.symbol for pos in positions)
    
    
    def grid_trade_exists(self, level):
        return level in self.grid_trades_done
    

    def place_grid_trade(self, level):
        grid_price = self.initial_price - (level * self.get_pip_size(self.symbol)) if self.initial_direction == "buy" else self.initial_price + (level * self.get_pip_size(self.symbol))
        direction = self.initial_direction
        sl, tp, price = self.calculate_sl_tp(self.symbol, direction)
        self.engine.place_order(self.symbol, direction, 0.01, sl, tp, f"grid_{level}")
        print(f"Placing grid trade at {grid_price:.5f} ({level} pips)")
        self.grid_trades_done.append(level)


    def place_hedge(self):
        direction = "sell" if self.initial_direction == "buy" else "buy"
        price = self.engine._get_price(self.symbol, direction)
        sl_pips = 10
        tp_pips = 50
        pip_size = self.get_pip_size(self.symbol)
        sl = price + sl_pips * pip_size if direction == "sell" else price - sl_pips * pip_size
        tp = price + tp_pips * pip_size if direction == "buy" else price - tp_pips * pip_size


        print(f"Placing hedge trade at {price:.5f}")
        self.engine.place_order(
            symbol=self.symbol,
            direction=direction,
            lot=0.01,
            sl=sl,
            tp=tp,
            comment="hedge"
        )
        self.hedge_active = True
    
    def get_pip_size(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            print(f"Erreur : pas d'info pour {symbol}")
            return 0.0001  # Valeur par défaut
        digits = info.digits
        return 0.01 if digits == 3 or digits == 2 else 0.0001
        

    def execute_strategy(self):
        """Exécute la stratégie complète."""
        
        trend = self.detect_trend(self.symbol)
        
        if not trend:
            return
        
        # 1. Trade initial
        sl, tp, price = self.calculate_sl_tp(self.symbol, trend)
        initial_trade = self.engine.place_order(self.symbol, trend, 0.01, sl, tp, self.comment)
        if initial_trade:
            self.initial_direction = trend
            self.initial_price = price
            self.hedge_active = False
            print("Trade initial placé avec succès.")
            monitor_thread = threading.Thread(target=self.monitor_trades, daemon=True)
            monitor_thread.start()
        else:
            print("Erreur lors du placement du trade initial.")