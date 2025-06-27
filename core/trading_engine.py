import MetaTrader5 as mt5
import logging
from datetime import datetime, timedelta, timezone

class TradingEngine:
    def __init__(self):
        """
        Initialise le moteur de trading avec des paramètres par défaut.
        
        Args:
            magic_number (int): Identifiant magique pour les ordres
            deviation (int): Déviation maximale autorisée en points
        """
        self.magic_number = 234000
        self.deviation = 20
        

    
    def _get_price(self, symbol: str, order_type: str):
        """
        Récupère le prix actuel selon le type d'ordre.
        
        Args:
            symbol: Le symbole du trading
            order_type: Type d'ordre ('buy' ou 'sell')
            
        Returns:
            float: Le prix actuel ou None en cas d'erreur
        """
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Impossible de récupérer le tick pour {symbol}")
            return None
            
        return tick.ask if order_type == "buy" else tick.bid
    
    def _prepare_order_request(
        self,
        symbol: str,
        order_type: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str,
        price: float,
        reduced_lot: bool = False
    ) -> dict:
        """
        Prépare le dictionnaire de requête pour l'ordre.
        
        Args:
            symbol: Symbole du trading
            order_type: Type d'ordre ('buy' ou 'sell')
            lot_size: Taille du lot
            stop_loss: Niveau de stop loss
            take_profit: Niveau de take profit
            comment: Nom de la stratégie
            price: Prix d'exécution
            reduced_lot: Si c'est un lot réduit
            
        Returns:
            dict: La requête d'ordre formatée
        """
        action = mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL
        
        return {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": action,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": self.deviation,
            "magic": self.magic_number,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_IOC,
            "type_time": mt5.ORDER_TIME_GTC,
        }
    

    def _prepare_pending_order_request(
        self,
        symbol: str,
        order_type: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str,
        price: float,
        current_price: float,
        reduced_lot: bool = False
    ) -> dict:
        """
        Prépare le dictionnaire de requête pour l'ordre.
        
        Args:
            symbol: Symbole du trading
            order_type: Type d'ordre ('buy' ou 'sell')
            lot_size: Taille du lot
            stop_loss: Niveau de stop loss
            take_profit: Niveau de take profit
            comment: Nom de la stratégie
            price: Prix d'exécution
            reduced_lot: Si c'est un lot réduit
            
        Returns:
            dict: La requête d'ordre formatée
        """

         # Choix du type d'ordre pending selon le contexte
        if order_type == "buy":
            action = mt5.ORDER_TYPE_BUY_LIMIT if price < current_price else mt5.ORDER_TYPE_BUY_STOP
        elif order_type == "sell":
            action = mt5.ORDER_TYPE_SELL_LIMIT if price > current_price else mt5.ORDER_TYPE_SELL_STOP
        else:
            raise ValueError("order_type doit être 'buy' ou 'sell'")

        
        tick = mt5.symbol_info_tick(symbol)
        server_now = datetime.fromtimestamp(tick.time)

        expiration_time = server_now + timedelta(minutes=30)
        expiration_timestamp = int(expiration_time.timestamp())

        
        return {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot_size,
            "type": action,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": self.deviation,
            "magic": self.magic_number,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_SPECIFIED,
            "expiration": expiration_timestamp,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
    

    def _process_order_result(
        self,
        result: mt5.OrderSendResult,
        symbol: str,
        order_type: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str,
        reduced_lot: bool = False
    ) -> bool:
        """
        Traite le résultat de l'ordre et log les informations appropriées.
        
        Args:
            result: Résultat de l'ordre envoyé
            symbol: Symbole du trading
            order_type: Type d'ordre
            lot_size: Taille du lot
            stop_loss: Niveau de stop loss
            take_profit: Niveau de take profit
            comment: Nom de la stratégie
            reduced_lot: Si c'est un lot réduit
            
        Returns:
            bool: True si l'ordre a réussi, False sinon
        """
        if result is None:
            logging.error(f'Erreur lors de l\'envoi de la requête : {mt5.last_error()}')
            return False
            
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            lot_info = f"lot REDUIT: {lot_size}" if reduced_lot else f"lot: {lot_size}"
            logging.info(
                f"{order_type} Trade exécuté pour {symbol}, "
                f"TP: {take_profit} & SL: {stop_loss}, "
                f"{lot_info} via la stratégie {comment} !"
            )
            return True
            
        elif result.retcode == 10019:  # Pas assez de marge
            logging.warning(f"Erreur: Pas assez de marge pour ouvrir l'ordre sur {symbol}. Tentative avec un lot réduit.")
            return False
            
        else:
            logging.error(
                f'Erreur lors de l\'envoi de la requête : {result.retcode}, '
                f'{result.comment}, prix: {result.price}'
            )
            return False
    
    def place_order(
        self,
        symbol: str,
        order_type: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str
    ) -> bool:
        """
        Place un ordre sur le marché avec gestion des erreurs et tentative de lot réduit.
        
        Args:
            symbol: Symbole du trading
            order_type: Type d'ordre ('buy' ou 'sell')
            lot_size: Taille du lot
            stop_loss: Niveau de stop loss
            take_profit: Niveau de take profit
            comment: Nom de la stratégie
            
        Returns:
            bool: True si l'ordre a réussi, False sinon
        """
        if order_type not in ("buy", "sell"):
            logging.warning("Type d'ordre invalide.")
            return False
            
        price = self._get_price(symbol, order_type)
        if price is None:
            return False
            
        # Préparation de la requête initiale
        request = self._prepare_order_request(
            symbol, order_type, lot_size, stop_loss, take_profit, comment, price
        )
        
        print(request)
        
        # Envoi de l'ordre initial
        result = mt5.order_send(request)
        
        # Traitement du résultat
        success = self._process_order_result(
            result, symbol, order_type, lot_size, stop_loss, take_profit, comment
        )
        
        # Si échec dû à un manque de marge, on tente avec un lot réduit
        if not success and result is not None and result.retcode == 10019:
            reduced_lot_size = max(0.01, round((lot_size / 2), 2))
            request["volume"] = reduced_lot_size
            
            # Nouvel essai avec lot réduit
            result = mt5.order_send(request)
            
            # Traitement du résultat avec lot réduit
            return self._process_order_result(
                result, symbol, order_type, reduced_lot_size, 
                stop_loss, take_profit, comment, True
            )
            
        return success
    

    def place_pending_order(
        self,
        symbol: str,
        order_type: str,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str,
        price: float,
        current_price: float
    ) -> bool:
        """
        Place un ordre sur le marché avec gestion des erreurs et tentative de lot réduit.
        
        Args:
            symbol: Symbole du trading
            order_type: Type d'ordre ('buy' ou 'sell')
            lot_size: Taille du lot
            stop_loss: Niveau de stop loss
            take_profit: Niveau de take profit
            comment: Nom de la stratégie
            
        Returns:
            bool: True si l'ordre a réussi, False sinon
        """
        if order_type not in ("buy", "sell"):
            logging.warning("Type d'ordre invalide.")
            return False
            
        # Préparation de la requête initiale
        request = self._prepare_pending_order_request(
            symbol, order_type, lot_size, stop_loss, take_profit, comment, price, current_price
        )
        
        print(request)
        
        # Envoi de l'ordre initial
        result = mt5.order_send(request)
        
        # Traitement du résultat
        success = self._process_order_result(
            result, symbol, order_type, lot_size, stop_loss, take_profit, comment
        )
        
        # Si échec dû à un manque de marge, on tente avec un lot réduit
        if not success and result is not None and result.retcode == 10019:
            reduced_lot_size = max(0.01, round((lot_size / 2), 2))
            request["volume"] = reduced_lot_size
            
            # Nouvel essai avec lot réduit
            result = mt5.order_send(request)
            
            # Traitement du résultat avec lot réduit
            return self._process_order_result(
                result, symbol, order_type, reduced_lot_size, 
                stop_loss, take_profit, comment, True
            )
            
        return success
    
    
    def close_position(self, symbol_to_close: str, comment: str = "16h") -> bool:
        """
        Ferme toutes les positions pour un symbole donné.
        
        Args:
            symbol_to_close: Symbole à fermer
            comment: Commentaire pour l'ordre de fermeture
            
        Returns:
            bool: True si toutes les positions ont été fermées avec succès, False sinon
        """
        positions = mt5.positions_get(symbol=symbol_to_close)
        if positions is None:
            logging.error(f"Aucune position trouvée pour {symbol_to_close} ou erreur de récupération")
            return False
            
        if len(positions) == 0:
            logging.warning(f"Aucune position ouverte pour {symbol_to_close}")
            return True
            
        all_closed = True
        for position in positions:
            symbol = position.symbol
            volume = position.volume
            ticket = position.ticket
            position_type = position.type
            
            # Détermination du type d'ordre de fermeture
            close_type = mt5.ORDER_TYPE_SELL if position_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Récupération du prix actuel
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logging.error(f"Impossible de récupérer le prix pour {symbol}")
                all_closed = False
                continue
                
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            
            # Préparation de la requête de fermeture
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Envoi de l'ordre de fermeture
            result = mt5.order_send(close_request)
            
            # Traitement du résultat
            if result is None:
                logging.error(f"Erreur lors de la fermeture de la position {ticket}. Erreur: {mt5.last_error()}")
                all_closed = False
            elif result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Échec de la fermeture de la position {ticket}. Code: {result.retcode}, Comment: {result.comment}")
                all_closed = False
            else:
                logging.info(f"Position {ticket} ({symbol}) fermée avec succès.")
                
        return all_closed
    
    def get_open_positions(self):
        positions = mt5.positions_get()
        return positions
    
    
    def get_pip_size(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            print(f"Erreur : pas d'info pour {symbol}")
            return 0.0001  # Valeur par défaut
        digits = info.digits
        return 0.01 if digits == 3 or digits == 2 else 0.0001


