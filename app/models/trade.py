from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
from app.core.database import Base

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String) # "BUY" or "SELL"
    quantity = Column(Integer)
    
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    
    status = Column(String) # "OPEN", "CLOSED", "FILLED", "REJECTED"
    
    pnl = Column(Float, default=0.0)
    
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    
    strategy = Column(String)
    
    order_id = Column(String, nullable=True)
    
    is_paper_trade = Column(Boolean, default=False)
