import MetaTrader5 as mt5

class SymbolSelector:
    def __init__(self):
        self.symbol_priority = {
            'USD': ['EURUSD', 'GBPUSD', 'USDJPY'],
            'EUR': ['EURUSD', 'EURGBP', 'EURJPY'],
            'GBP': ['GBPUSD', 'EURGBP', 'GBPJPY'],
            'JPY': ['USDJPY', 'EURJPY', 'GBPJPY'],
            'CHF': ['USDCHF', 'EURCHF', 'GBPCHF'],
            'AUD': ['AUDUSD', 'EURAUD', 'AUDJPY'],
            'CAD': ['USDCAD', 'EURCAD', 'CADJPY'],
            'NZD': ['NZDUSD', 'EURNZD', 'NZDJPY'],
        }

    def get_best_symbol(self, country_news):
        """Retourne le meilleur symbole pour la news."""
        country = country_news.upper()  # Ex: 'CHF' → 'USDCHF'
        
        # Cas spécial pour USD (éviter les paires comme USDCHF si CHF est la news)
        if country == 'USD':
            return 'EURUSD'  # Meilleure liquidité
        
        # Si la devise est dans la liste, on prend la paire la plus tradée
        if country in self.symbol_priority:
            for symbol in self.symbol_priority[country]:
                if mt5.symbol_info(symbol) is not None:
                    return symbol
        
        # Fallback : USD/XXX si la devise n'est pas majeure
        fallback_symbol = f"USD{country}"
        if mt5.symbol_info(fallback_symbol) is not None:
            return fallback_symbol
        
        # Si aucune paire n'est trouvée (ex: TRY, ZAR)
        return None  # À éviter dans la stratégie