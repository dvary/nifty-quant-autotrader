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
        
    def register_callback(self, callback_func):
        """Register a function to be called on every tick"""
        self.callbacks.append(callback_func)
        
    def start(self, access_token=None):
        self.is_running = True
        self.thread = threading.Thread(target=self._poll_data, daemon=True)
        self.thread.start()
        logger.info("YFinance Market Data Feed started for all tracked stocks.")
        
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
                    # Convert to YF format
                    for s in self.symbols_to_track:
                        base = s.split(':')[-1]
                        if base == "NIFTY 50": base = "^NSEI"
                        elif base == "NIFTY BANK": base = "^NSEBANK"
                        else: base = base + ".NS"
                        yf_symbols.append(base)
                    
                    # Fetch live tick data for ALL in one request using download
                    data = yf.download(tickers=" ".join(yf_symbols), period="1d", interval="1m", progress=False)
                    
                    if not data.empty and 'Close' in data.columns:
                        timestamp = datetime.now()
                        
                        # Handle single vs multiple ticker response format
                        if len(yf_symbols) == 1:
                            last_row = data.iloc[-1]
                            s = self.symbols_to_track[0]
                            tick = {
                                'instrument_token': 0,
                                'symbol': s,
                                'last_price': float(last_row['Close']),
                                'volume_traded': int(last_row['Volume']) if 'Volume' in last_row else 0,
                                'exchange_timestamp': timestamp 
                            }
                            for cb in self.callbacks: cb(tick)
                        else:
                            last_row_close = data['Close'].iloc[-1]
                            last_row_vol = data['Volume'].iloc[-1] if 'Volume' in data.columns else None
                            
                            for i, yf_s in enumerate(yf_symbols):
                                s = self.symbols_to_track[i]
                                close_val = last_row_close[yf_s] if yf_s in last_row_close else None
                                
                                if pd.isna(close_val):
                                    continue
                                    
                                vol_val = last_row_vol[yf_s] if last_row_vol is not None and yf_s in last_row_vol else 0
                                
                                tick = {
                                    'instrument_token': 0,
                                    'symbol': s,
                                    'last_price': float(close_val),
                                    'volume_traded': int(vol_val) if not pd.isna(vol_val) else 0,
                                    'exchange_timestamp': timestamp 
                                }
                                for cb in self.callbacks:
                                    try: cb(tick)
                                    except Exception: pass
                                    
            except Exception as e:
                logger.error(f"Error fetching bulk YFinance data: {e}")
                
            time.sleep(15) # Poll every 15 seconds to avoid breaking Yahoo rate limits and 5m candle isn't fast
