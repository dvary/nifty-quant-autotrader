from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.broker.kite_broker import broker as kite_broker
from app.core.engine import engine
from app.models.trade import Trade

router = APIRouter()

class TokenRequest(BaseModel):
    request_token: str

@router.get("/broker/login-url")
def get_login_url():
    """Returns the Zerodha login URL"""
    return {"url": kite_broker.get_login_url()}

@router.post("/broker/set-token")
def set_access_token(data: TokenRequest):
    """Sets the access token after manual login"""
    success = kite_broker.set_access_token(data.request_token)
    if success:
        return {"status": "success", "message": "Access token generated"}
    return {"status": "failed", "message": "Could not generate access token"}

@router.post("/engine/start")
def start_engine():
    success = engine.start()
    if success:
        return {"status": "success", "message": "Engine started"}
    return {"status": "failed", "message": "Engine failed to start (Check Token)"}

@router.post("/engine/stop")
def stop_engine():
    engine.stop()
    return {"status": "success", "message": "Engine stopped"}

@router.post("/engine/kill-switch")
def toggle_kill_switch(active: bool):
    if active:
        engine.risk_manager.activate_kill_switch()
    else:
        engine.risk_manager.deactivate_kill_switch()
    return {"status": "success", "kill_switch": engine.risk_manager.kill_switch_active}

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Returns aggregated stats for the dashboard"""
    today = datetime.utcnow().date()
    
    # Calculate today's PnL
    trades_today = db.query(Trade).filter(
        Trade.entry_time >= datetime.combine(today, datetime.min.time())
    ).all()
    
    total_pnl = sum([t.pnl for t in trades_today if t.pnl is not None])
    
    # Get active positions
    active_trades = [t for t in trades_today if t.status == "OPEN"]
    
    # Format active positions suitable for UI
    positions = []
    for t in active_trades:
        # Get live LTP if running, else use entry
        ltp = t.entry_price
        if engine.is_running and engine.strategy.symbol == t.symbol:
            # We don't have direct LTP fetching in engine synced, but we can query Kite
            # Or just show 0 PnL for live (in a real system we'd use websocket LTP cache)
            pass
            
        live_pnl = (ltp - t.entry_price) * t.quantity if t.side == "BUY" else (t.entry_price - ltp) * t.quantity
        
        positions.append({
            "id": t.id,
            "symbol": t.symbol,
            "type": t.side,
            "qty": t.quantity,
            "entry_price": round(t.entry_price, 2),
            "ltp": round(ltp, 2),
            "pnl": round(live_pnl, 2)
        })

    return {
        "pnl": round(total_pnl, 2),
        "active_count": len(active_trades),
        "engine_status": "RUNNING" if engine.is_running else "STOPPED",
        "positions": positions
    }

@router.get("/dashboard/tracking")
def get_tracking_status():
    """Returns the live status of all tracked strategies"""
    import pandas as pd
    tracking = []
    
    if not engine.is_running:
        return {"tracking": tracking}
        
    for symbol, strategy in engine.strategies.items():
        hist = engine.aggregator.candles.get(symbol)
        ltp = 0.0
        ma = 0.0
        if hist is not None and not hist.empty:
            last_candle = hist.iloc[-1]
            ltp = float(last_candle['close'])
            if 'ma_44' in last_candle and not pd.isna(last_candle['ma_44']):
                ma = float(last_candle['ma_44'])
                
        dist = 0.0
        if ma > 0:
            dist = round(((ltp - ma) / ma) * 100, 2)
            
        tracking.append({
            "symbol": symbol.split(':')[-1],
            "ltp": round(ltp, 2),
            "ma_44": round(ma, 2),
            "distance_pct": dist,
            "status": "IN POSITION" if strategy.position else ("NEAR CROSSOVER" if -1.0 < dist < 0 else "TRACKING")
        })
        
    # Sort by distance closest to 0 from below (nearing a golden crossover)
    tracking.sort(key=lambda x: abs(x['distance_pct']))
    
    return {"tracking": tracking}

@router.get("/charts/{symbol}")
def get_chart_data(symbol: str):
    """Returns OHLC + EMA history for charting"""
    import pandas as pd
    from ta.trend import EMAIndicator
    
    # Try with and without exchange prefix
    full_symbol = f"NSE:{symbol}" if ":" not in symbol else symbol
    
    hist = engine.aggregator.get_history(full_symbol)
    if hist.empty:
        return {"status": "error", "message": f"No data found for {full_symbol}"}
        
    df = hist.copy()
    
    # Ensure EMAs are calculated for the full history
    if len(df) >= 44:
        df['ma_44'] = EMAIndicator(close=df['close'], window=44).ema_indicator()
    if len(df) >= 200:
        df['ma_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
        
    # Format for Lightweight Charts (timestamp needs to be unix)
    data = []
    for idx, row in df.iterrows():
        item = {
            "time": int(idx.timestamp()),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
        }
        if 'ma_44' in row and not pd.isna(row['ma_44']):
            item['ma_44'] = float(row['ma_44'])
        if 'ma_200' in row and not pd.isna(row['ma_200']):
            item['ma_200'] = float(row['ma_200'])
        data.append(item)
        
    return {
        "symbol": symbol,
        "timeframe": engine.aggregator.timeframe,
        "candles": data
    }
