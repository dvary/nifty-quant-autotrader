from threading import Thread
import os
from app.core.logger import logger, alert
from app.broker.kite_broker import broker as kite_broker
from app.broker.yfinance_feed import YFinanceFeed
from app.data.aggregator import CandleAggregator
from app.core.risk_manager import RiskManager
from app.strategy.ma_44_strategy import MovingAverage44Strategy
from app.core.database import SessionLocal
import yfinance as yf
import pandas as pd
from datetime import timedelta

class TradingEngine:
    def __init__(self):
        self.db = SessionLocal()
        self.risk_manager = RiskManager(self.db)
        
        # Load configs
        self.timeframe = int(os.getenv("STRATEGY_TIMEFRAME", 5))
        
        self.nifty_50_symbols = [
            "NSE:ADANIENT", "NSE:ADANIPORTS", "NSE:APOLLOHOSP", "NSE:ASIANPAINT", "NSE:AXISBANK", 
            "NSE:BAJAJ-AUTO", "NSE:BAJFINANCE", "NSE:BAJAJFINSV", "NSE:BPCL", "NSE:BHARTIARTL", 
            "NSE:BRITANNIA", "NSE:CIPLA", "NSE:COALINDIA", "NSE:DIVISLAB", "NSE:DRREDDY", 
            "NSE:EICHERMOT", "NSE:GRASIM", "NSE:HCLTECH", "NSE:HDFCBANK", "NSE:HDFCLIFE", 
            "NSE:HEROMOTOCO", "NSE:HINDALCO", "NSE:HINDUNILVR", "NSE:ICICIBANK", "NSE:ITC", 
            "NSE:INDUSINDBK", "NSE:INFY", "NSE:JSWSTEEL", "NSE:KOTAKBANK", "NSE:LTIM", 
            "NSE:LT", "NSE:M&M", "NSE:MARUTI", "NSE:NTPC", "NSE:NESTLEIND", "NSE:ONGC", 
            "NSE:POWERGRID", "NSE:RELIANCE", "NSE:SBILIFE", "NSE:SBIN", "NSE:SUNPHARMA", 
            "NSE:TCS", "NSE:TATACONSUM", "NSE:TATAMOTORS", "NSE:TATASTEEL", "NSE:TECHM", 
            "NSE:TITAN", "NSE:UPL", "NSE:ULTRACEMCO", "NSE:WIPRO"
        ]
        
        self.aggregator = CandleAggregator(timeframe_minutes=self.timeframe)
        
        self.strategies = {}
        for symbol in self.nifty_50_symbols:
            self.strategies[symbol] = MovingAverage44Strategy(
                symbol=symbol, 
                db=self.db, 
                risk_manager=self.risk_manager
            )
        
        self.websocket = YFinanceFeed()
        self.is_running = False

    def on_candle(self, candle_dict, history):
        symbol = candle_dict['symbol']
        if symbol in self.strategies:
            self.strategies[symbol].on_candle(candle_dict, history)

    def on_tick(self, tick):
        symbol = tick['symbol']
        if symbol in self.strategies:
            self.strategies[symbol].on_tick(tick)

    def setup(self):
        # Register aggregator callback to engine dispatcher
        self.aggregator.register_callback(self.on_candle)
        
        # Register websocket callback to aggregator and engine dispatcher
        self.websocket.register_callback(self.aggregator.process_tick)
        self.websocket.register_callback(self.on_tick)

    def _load_historical_for_strategy(self, symbol):
        logger.info(f"Loading historical data for {symbol} via Yahoo Finance...")
        # Handled in bulk dynamically or skipped, wait we can just bulk download for 50
        yf_symbol = symbol.split(':')[-1] + ".NS"
        if "NIFTY 50" in symbol: yf_symbol = "^NSEI"
        
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="5d", interval=f"{self.timeframe}m")
        if df.empty: return
            
        df = df.reset_index()
        df.rename(columns={"Datetime": "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        self.aggregator.load_historical_data(symbol, df)

    def _load_all_historical(self):
        """Loads historical data for all tracked symbols using bulk fetching if possible"""
        # For simplicity in this method, we can just bulk download them in one shot then slice
        logger.info("Loading bulk historical data for all 50 Nifty stocks...")
        yf_symbols = [s.split(':')[-1] + ".NS" for s in self.nifty_50_symbols]
        data = yf.download(tickers=" ".join(yf_symbols), period="5d", interval=f"{self.timeframe}m", progress=False)
        
        if data.empty: return
        
        # Because we downloaded bulk, the columns are multi-index (Price, Ticker)
        for i, symbol in enumerate(self.nifty_50_symbols):
            try:
                yf_sym = yf_symbols[i]
                if yf_sym not in data['Close']: continue
                
                df = pd.DataFrame({
                    'timestamp': data.index,
                    'open': data['Open'][yf_sym].values,
                    'high': data['High'][yf_sym].values,
                    'low': data['Low'][yf_sym].values,
                    'close': data['Close'][yf_sym].values,
                    'volume': data['Volume'][yf_sym].values if 'Volume' in data.columns else 0
                }).dropna()
                
                if not df.empty:
                    self.aggregator.load_historical_data(symbol, df)
            except Exception as e:
                logger.error(f"Failed historical load for {symbol}: {e}")
                
    def start(self):
        if not kite_broker.access_token:
            logger.error("Cannot start engine: No Kite access token. Please login first.")
            return False
            
        logger.info("Starting Trading Engine Multi-Strategy...")
        self.setup()
        
        # Load historical data 
        self._load_all_historical()
        
        # Subscribe all to YFinance feed
        for symbol in self.nifty_50_symbols:
            self.websocket.subscribe(0, symbol)
            self.strategies[symbol].start()
            
        self.websocket.start(None)
        self.is_running = True
        return True
        
    def stop(self):
        logger.info("Stopping Trading Engine Multi-Strategy...")
        for symbol, strategy in self.strategies.items():
            strategy.stop()
        self.websocket.stop()
        self.is_running = False
        
    def get_status(self):
        return {
            "engine_running": self.is_running,
            "broker_authenticated": bool(kite_broker.access_token),
            "kill_switch_active": self.risk_manager.kill_switch_active,
            "active_strategies": len(self.strategies) if self.is_running else 0
        }

# Global singleton
engine = TradingEngine()
