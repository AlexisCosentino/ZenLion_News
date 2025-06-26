import MetaTrader5 as mt5
import logging
from config import ACCOUNT_NUMBER, PASSWORD, SERVER
import time
import pandas as pd


class MT5Client:
    """
    A class to handle MetaTrader 5 operations including connection, data fetching, and position management.
    
    Attributes:
        account_number (int): MT5 account number
        password (str): MT5 account password
        server (str): MT5 server name
        connected (bool): Connection status flag
    """
    
    def __init__(self, account_number=ACCOUNT_NUMBER, password=PASSWORD, server=SERVER):
        """
        Initialize the MT5Client with account credentials.
        
        Args:
            account_number (int): MT5 account number (default from config)
            password (str): MT5 account password (default from config)
            server (str): MT5 server name (default from config)
        """
        self.account_number = account_number
        self.password = password
        self.server = server
        self.connected = False
        
    def initialize_mt5(self):
        """
        Initialize and connect to MetaTrader 5 terminal.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if not mt5.initialize():
            logging.error("Failed to initialize MetaTrader 5")
            self.connected = False
            return False
            
        if not mt5.login(self.account_number, password=self.password, server=self.server):
            logging.error(f"Failed to connect to account {self.account_number}")
            self.connected = False
            return False
            
        self.connected = True
        logging.info(f"Successfully connected to account: {self.account_number}")
        return True
        
    def reconnect_mt5(self):
        """
        Attempt to reconnect to MetaTrader 5 terminal.
        
        Returns:
            bool: True if reconnection was successful, False otherwise
        """
        logging.info("Attempting to reconnect to MetaTrader 5...")
        mt5.shutdown()  # Close existing session
        time.sleep(5)  # Wait 5 seconds before reconnecting
        self.connected = False
        return self.initialize_mt5()
        
    def fetch_data(self, symbol, timeframe, count=100):
        """
        Fetch market data (candles) for the specified symbol and timeframe.
        
        Args:
            symbol (str): Trading symbol (e.g., "EURUSD")
            timeframe: MT5 timeframe constant (e.g., mt5.TIMEFRAME_M15)
            count (int): Number of candles to retrieve (default: 100)
            
        Returns:
            pd.DataFrame: DataFrame containing market data, or None if failed
        """
        if not self.connected:
            if not self.initialize_mt5():
                return None
                
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None:
            logging.warning(f"Failed to fetch data for {symbol}")
            return None
            
        data = pd.DataFrame(rates)
        data['time'] = pd.to_datetime(data['time'], unit='s')
        return data
        
    def check_existing_position(self, symbol):
        """
        Check if there's an existing position for the specified symbol.
        
        Args:
            symbol (str): Trading symbol to check
            
        Returns:
            bool: True if position exists, False otherwise
        """
        if not self.connected:
            if not self.initialize_mt5():
                return False
                
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            logging.error(f"Error checking positions for {symbol}: {mt5.last_error()}")
            return False
            
        return len(positions) > 0
        
    def shutdown(self):
        """
        Shutdown the MT5 connection.
        """
        mt5.shutdown()
        self.connected = False
        logging.info("MT5 connection closed")
        
    def __del__(self):
        """Destructor to ensure proper shutdown"""
        self.shutdown()