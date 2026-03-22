import time
import threading
from datetime import datetime
import pandas as pd
import yfinance as yf
from app.core.logger import logger

class YFinanceFeed:
    def __init__(self):
        self.callbacks = []
        self.is_running = False
        self.thread = None
        
        self.symbols_to_track = []
        self.failed_symbols = {} # symbol -> last_log_time

    def register_callback(self, callback_func):
        """Register a function to be called on every tick"""
        self.callbacks.append(callback_func)
        
    def start(self, access_token=None):
        self.is_running = True
        self.thread = threading.Thread(target=self._poll_data, daemon=True)
        self.thread.start()
        logger.info("YFinance Market Data Feed started for Nifty 50.")
        
    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("YFinance Market Data Feed stopped.")
        
    def subscribe(self, instrument_token, symbol):
        if symbol not in self.symbols_to_track:
            self.symbols_to_track.append(symbol)
            logger.info(f"Subscribed to {symbol} via YFinance Feed")
            
    def _poll_data(self):
        while self.is_running:
            try:
                if self.symbols_to_track:
                    yf_symbols = []
                    symbol_map = {} # YF -> Zerodha
                    for s in self.symbols_to_track:
                        base = s.split(':')[-1]
                        yf_s = "^NSEI" if base == "NIFTY 50" else ("^NSEBANK" if base == "NIFTY BANK" else f"{base}.NS")
                        yf_symbols.append(yf_s)
                        symbol_map[yf_s] = s
                    
                    data = yf.download(tickers=" ".join(yf_symbols), period="1d", interval="1m", progress=False)
                    
                    if not data.empty and 'Close' in data.columns:
                        timestamp = datetime.now()
                        
                        last_row_close = data['Close'].iloc[-1]
                        last_row_vol = data['Volume'].iloc[-1] if 'Volume' in data.columns else None
                        
                        for yf_s in yf_symbols:
                            s = symbol_map[yf_s]
                            close_val = last_row_close[yf_s] if yf_s in last_row_close else None
                            
                            if pd.isna(close_val):
                                # Avoid log spam: only log once per hour for missing data
                                if s not in self.failed_symbols or (time.time() - self.failed_symbols[s]) > 3600:
                                    logger.warning(f"No price data found for {s} (possibly delisted or closed).")
                                    self.failed_symbols[s] = time.time()
                                continue
                                    
                            tick = {
                                'instrument_token': 0,
                                'symbol': s,
                                'last_price': float(close_val),
                                'volume_traded': int(last_row_vol[yf_s]) if last_row_vol is not None and not pd.isna(last_row_vol[yf_s]) else 0,
                                'exchange_timestamp': timestamp 
                            }
                            for cb in self.callbacks:
                                try: cb(tick)
                                except: pass
                                    
            except Exception as e:
                logger.error(f"Error fetching bulk YFinance data: {e}")
                
            time.sleep(15)
