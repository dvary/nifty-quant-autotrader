import os
from kiteconnect import KiteConnect
from app.core.logger import logger

class KiteBroker:
    def __init__(self):
        self.api_key = os.getenv("KITE_API_KEY")
        self.api_secret = os.getenv("KITE_API_SECRET")
        self.access_token = None
        self.kite = KiteConnect(api_key=self.api_key)
        
    def get_login_url(self):
        """Returns the login URL for manual token generation"""
        return self.kite.login_url()
        
    def set_access_token(self, request_token: str):
        """Exchange request token for access token"""
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            logger.info("Successfully generated Kite access token")
            return True
        except Exception as e:
            logger.error(f"Failed to generate access token: {e}")
            return False
            
    def place_order(self, symbol: str, transaction_type: str, quantity: int, order_type: str, price: float = None):
        """Places an order on Zerodha"""
        try:
            logger.info(f"Placing {transaction_type} order for {quantity} {symbol} at {price or 'MARKET'}")
            
            # Use appropriate transaction type constant
            t_type = self.kite.TRANSACTION_TYPE_BUY if transaction_type.upper() == "BUY" else self.kite.TRANSACTION_TYPE_SELL
            o_type = self.kite.ORDER_TYPE_MARKET if order_type.upper() == "MARKET" else self.kite.ORDER_TYPE_LIMIT
            
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange=self.kite.EXCHANGE_NSE,
                transaction_type=t_type,
                quantity=quantity,
                order_type=o_type,
                price=price,
                product=self.kite.PRODUCT_MIS, # Intraday by default for the bot
                validity=self.kite.VALIDITY_DAY
            )
            logger.info(f"Order placed successfully. ID: {order_id}")
            return order_id
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    def get_order_history(self, order_id: str):
        try:
            return self.kite.order_history(order_id=order_id)
        except Exception as e:
            logger.error(f"Failed to get order history: {e}")
            return None
            
    def get_positions(self):
        try:
            return self.kite.positions()
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return None

    def get_ltp(self, instruments):
        """Gets Last Traded Price for instruments like ['NSE:RELIANCE', 'NSE:INFY']"""
        try:
            return self.kite.ltp(instruments)
        except Exception as e:
            logger.error(f"Failed to get LTP: {e}")
            return None

# Singleton instance
broker = KiteBroker()
