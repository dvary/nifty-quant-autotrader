import pandas as pd
from datetime import datetime, timedelta
from app.core.logger import logger

class CandleAggregator:
    def __init__(self, timeframe_minutes: int = 5):
        self.timeframe = f"{timeframe_minutes}min" # pandas offset string
        # Store raw ticks per symbol: dict[symbol] -> list of dicts
        self.ticks_buffer = {}
        # Store complete candles per symbol: dict[symbol] -> pd.DataFrame
        self.candles = {}
        # Callbacks for when a new candle is formed
        self.on_candle_callbacks = []
        
    def register_callback(self, callback):
        self.on_candle_callbacks.append(callback)

    def process_tick(self, tick: dict):
        """Process incoming tick and build candles"""
        symbol = tick.get('symbol')
        if not symbol:
            return

        if symbol not in self.ticks_buffer:
            self.ticks_buffer[symbol] = []
            
        tick_time = tick.get('exchange_timestamp', datetime.now())
        price = tick.get('last_price')
        volume = tick.get('volume_traded', 0)
        
        if not price:
            return
            
        self.ticks_buffer[symbol].append({
            'timestamp': tick_time,
            'price': price,
            'volume': volume
        })
        
        # Check if we should aggregate (e.g., every minute or based on strict time boundaries)
        # For a robust system, we aggregate based on the clock
        self._check_and_aggregate(symbol, tick_time)
        
    def _check_and_aggregate(self, symbol: str, current_time: datetime):
        if symbol not in self.ticks_buffer or not self.ticks_buffer[symbol]:
            return
            
        df = pd.DataFrame(self.ticks_buffer[symbol])
        df.set_index('timestamp', inplace=True)
        
        # Resample using the configured timeframe
        # We use label='left' and closed='left' to match standard charting
        ohlcv = df['price'].resample(self.timeframe, label='left', closed='left').ohlc()
        volume = df['volume'].resample(self.timeframe, label='left', closed='left').sum()
        
        ohlcv['volume'] = volume
        ohlcv.dropna(inplace=True)
        
        if ohlcv.empty:
            return
            
        # If we have completed a candle (i.e. we have a candle for a period strictly before current_time's period)
        current_period_start = pd.Timestamp(current_time).floor(self.timeframe)
        
        completed_candles = ohlcv[ohlcv.index < current_period_start]
        
        if not completed_candles.empty:
            if symbol not in self.candles:
                self.candles[symbol] = completed_candles
                self._notify_new_candles(symbol, completed_candles)
            else:
                # Find new candles that aren't in our history yet
                existing_index = self.candles[symbol].index
                new_ones = completed_candles[~completed_candles.index.isin(existing_index)]
                
                if not new_ones.empty:
                    self.candles[symbol] = pd.concat([self.candles[symbol], new_ones])
                    self._notify_new_candles(symbol, new_ones)
                    
            # Clear buffer of ticks older than the last completed candle
            last_completed = completed_candles.index[-1]
            self.ticks_buffer[symbol] = [
                t for t in self.ticks_buffer[symbol] 
                if pd.Timestamp(t['timestamp']) >= current_period_start
            ]
            
    def _notify_new_candles(self, symbol: str, new_candles: pd.DataFrame):
        logger.debug(f"[{symbol}] New {self.timeframe} candles completed: {len(new_candles)}")
        for callback in self.on_candle_callbacks:
            try:
                # Pass the latest completed candle
                latest = new_candles.iloc[-1]
                candle_dict = {
                    'symbol': symbol,
                    'timestamp': latest.name,
                    'open': latest['open'],
                    'high': latest['high'],
                    'low': latest['low'],
                    'close': latest['close'],
                    'volume': latest['volume']
                }
                callback(candle_dict, self.candles[symbol])
            except Exception as e:
                logger.error(f"Error in candle callback: {e}")
                
    def get_history(self, symbol: str) -> pd.DataFrame:
        if symbol in self.candles:
            return self.candles[symbol]
        return pd.DataFrame()

    def load_historical_data(self, symbol: str, df: pd.DataFrame):
        """Method to prepopulate df with historical candles from broker API"""
        if df.empty:
            return
        df.set_index('timestamp', inplace=True, drop=False) if 'timestamp' in df.columns else None
        self.candles[symbol] = df
        logger.info(f"Loaded {len(df)} historical candles for {symbol}")
