import os
from sqlalchemy.orm import Session
from app.core.logger import logger, alert
from app.models.trade import Trade
from datetime import datetime

class RiskManager:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.max_trades_per_day = int(os.getenv("MAX_TRADES_PER_DAY", 5))
        self.daily_loss_limit = float(os.getenv("DAILY_LOSS_LIMIT", 5000))
        self.capital_per_trade = float(os.getenv("CAPITAL_PER_TRADE", 50000))
        self.kill_switch_active = False
        
    def check_trade_allowed(self) -> bool:
        """Check if a new trade can be initiated based on risk limits"""
        if self.kill_switch_active:
            logger.warning("Trade rejected: Kill switch is active")
            return False
            
        today = datetime.utcnow().date()
        
        # Check max trades per day
        trades_today = self.db.query(Trade).filter(
            Trade.entry_time >= datetime.combine(today, datetime.min.time())
        ).count()
        
        if trades_today >= self.max_trades_per_day:
            logger.warning(f"Trade rejected: Max trades limit reached ({self.max_trades_per_day})")
            return False
            
        # Check daily loss limit
        pnl_today_records = self.db.query(Trade.pnl).filter(
            Trade.entry_time >= datetime.combine(today, datetime.min.time())
        ).all()
        
        total_pnl = sum([record[0] for record in pnl_today_records if record[0] is not None])
        if total_pnl <= -abs(self.daily_loss_limit):
            msg = f"Trade rejected: Daily loss limit hit! PnL: {total_pnl}"
            alert(msg)
            self.activate_kill_switch()
            return False
            
        return True
        
    def activate_kill_switch(self):
        """Activates the kill switch to stop all new trading"""
        self.kill_switch_active = True
        alert("KILL SWITCH ACTIVATED. Automated trading has been stopped.")
        
    def deactivate_kill_switch(self):
        """Deactivates the kill switch"""
        self.kill_switch_active = False
        logger.info("Kill switch deactivated. Resuming trading.")
        
    def calculate_position_size(self, current_price: float, stop_loss: float = None) -> int:
        """Calculates how much quantity to buy"""
        # Simple allocation based on capital per trade
        qty = int(self.capital_per_trade / current_price)
        return max(1, qty) # Minimum 1 qty
