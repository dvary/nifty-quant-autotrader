from abc import ABC, abstractmethod
import pandas as pd
from app.core.logger import logger
from app.broker.kite_broker import broker as kite_broker
from app.core.risk_manager import RiskManager
from sqlalchemy.orm import Session

class BaseStrategy(ABC):
    def __init__(self, name: str, symbol: str, db: Session, risk_manager: RiskManager):
        self.name = name
        self.symbol = symbol
        self.db = db
        self.risk_manager = risk_manager
        self.is_running = False
        
        # Current active position: {'side': 'BUY', 'qty': 100, 'entry': 150.5, 'sl': 149.0, 'target': 154.0}
        self.position = None 
        
    def start(self):
        self.is_running = True
        logger.info(f"Strategy {self.name} started for {self.symbol}")
        
    def stop(self):
        self.is_running = False
        logger.info(f"Strategy {self.name} stopped for {self.symbol}")
        
    def on_tick(self, tick: dict):
        """Called on every live tick. Useful for trailing SL or target checking."""
        if not self.is_running or not self.position:
            return
            
        last_price = tick['last_price']
        
        # Check Stop Loss / Target if position exists
        if self.position['side'] == 'BUY':
            if last_price <= self.position['sl']:
                logger.info(f"[{self.symbol}] Stop Loss hit at {last_price}")
                self.close_position(last_price, reason="SL")
            elif last_price >= self.position['target']:
                logger.info(f"[{self.symbol}] Target hit at {last_price}")
                self.close_position(last_price, reason="TARGET")
                
        elif self.position['side'] == 'SELL':
            if last_price >= self.position['sl']:
                logger.info(f"[{self.symbol}] Stop Loss hit at {last_price}")
                self.close_position(last_price, reason="SL")
            elif last_price <= self.position['target']:
                logger.info(f"[{self.symbol}] Target hit at {last_price}")
                self.close_position(last_price, reason="TARGET")

    @abstractmethod
    def on_candle(self, candle: dict, history: pd.DataFrame):
        """Called when a new timeframe candle is formed."""
        pass
        
    def execute_trade(self, side: str, price: float, sl: float, target: float):
        if not self.risk_manager.check_trade_allowed():
            return
            
        qty = self.risk_manager.calculate_position_size(price, sl)
        
        # Execute via broker
        order_id = kite_broker.place_order(
            symbol=self.symbol,
            transaction_type=side,
            quantity=qty,
            order_type="MARKET"
        )
        
        if order_id:
            logger.info(f"[{self.symbol}] Executed {side} order. Qty: {qty}. SL: {sl}. TGT: {target}")
            self.position = {
                'side': side,
                'qty': qty,
                'entry': price,
                'sl': sl,
                'target': target,
                'order_id': order_id
            }
            # Record in DB (async/background is better, but doing it sync for now)
            from app.models.trade import Trade
            from datetime import datetime
            
            new_trade = Trade(
                symbol=self.symbol,
                side=side,
                quantity=qty,
                entry_price=price,
                stop_loss=sl,
                target=target,
                status="OPEN",
                entry_time=datetime.utcnow(),
                strategy=self.name,
                order_id=order_id,
                is_paper_trade=False
            )
            self.db.add(new_trade)
            self.db.commit()
            
    def close_position(self, exit_price: float, reason: str = "SIGNAL"):
        if not self.position:
            return
            
        exit_side = "SELL" if self.position['side'] == "BUY" else "BUY"
        qty = self.position['qty']
        
        order_id = kite_broker.place_order(
            symbol=self.symbol,
            transaction_type=exit_side,
            quantity=qty,
            order_type="MARKET"
        )
        
        if order_id:
            logger.info(f"[{self.symbol}] Closed position ({reason}). Exit price: {exit_price}")
            
            # Update DB
            from app.models.trade import Trade
            from datetime import datetime
            
            trade = self.db.query(Trade).filter(
                Trade.symbol == self.symbol,
                Trade.status == "OPEN",
                Trade.order_id == self.position['order_id']
            ).first()
            
            if trade:
                trade.exit_price = exit_price
                trade.exit_time = datetime.utcnow()
                trade.status = "CLOSED"
                
                # Calculate simple PnL (excluding broker charges)
                if self.position['side'] == 'BUY':
                    trade.pnl = (exit_price - trade.entry_price) * qty
                else:
                    trade.pnl = (trade.entry_price - exit_price) * qty
                    
                self.db.commit()
                
            self.position = None
