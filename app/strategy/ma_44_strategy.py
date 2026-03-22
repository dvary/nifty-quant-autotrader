import pandas as pd
from ta.trend import EMAIndicator, SMAIndicator
from app.strategy.base_strategy import BaseStrategy
from app.core.logger import logger

class MovingAverage44Strategy(BaseStrategy):
    def __init__(self, symbol: str, db, risk_manager, ma_type: str = "EMA"):
        super().__init__(name="44_MA_Strategy", symbol=symbol, db=db, risk_manager=risk_manager)
        self.ma_period = 44
        self.trend_ma_period = 200
        self.ma_type = ma_type.upper() # "EMA" or "SMA"
        self.reward_risk_ratio = 2.0
        
    def on_candle(self, candle: dict, history: pd.DataFrame):
        if not self.is_running:
            return
            
        # We need at least 'trend_ma_period' candles to calculate the 200 MA
        if len(history) < self.trend_ma_period:
            return
            
        # Add 44 MA to history
        if self.ma_type == "EMA":
            indicator_44 = EMAIndicator(close=history["close"], window=self.ma_period)
            indicator_200 = EMAIndicator(close=history["close"], window=self.trend_ma_period)
        else:
            indicator_44 = SMAIndicator(close=history["close"], window=self.ma_period)
            indicator_200 = SMAIndicator(close=history["close"], window=self.trend_ma_period)
            
        history["ma_44"] = indicator_44.ema_indicator() if self.ma_type == "EMA" else indicator_44.sma_indicator()
        history["ma_200"] = indicator_200.ema_indicator() if self.ma_type == "EMA" else indicator_200.sma_indicator()
        
        # We need the last two candles to check for crossover and slope
        if len(history) < 2:
            return
            
        last_candle = history.iloc[-2]  # The candle before the one that just formed
        current_candle = history.iloc[-1] # The newly formed candle
        
        ma_val = current_candle["ma_44"]
        ma_200_val = current_candle["ma_200"]
        
        if pd.isna(ma_val) or pd.isna(ma_200_val):
            return
            
        # If we already have a position, check if we need to close it
        if self.position:
            if self.position['side'] == 'BUY' and current_candle['close'] < ma_val:
                logger.info(f"[{self.symbol}] Price crossed below 44 MA. Closing BUY position.")
                self.close_position(current_candle['close'], reason="MA_CROSS_DOWN")
            return 
            
        # Check BUY condition: Price crosses above 44 MA
        crossed_above = (last_candle['close'] < last_candle['ma_44']) and (current_candle['close'] > current_candle['ma_44'])
        
        # Trend Confirmation: 200 MA is rising (current > last) AND price is > 200 MA
        ma_200_rising = current_candle['ma_200'] >= last_candle['ma_200']
        price_above_200 = current_candle['close'] > current_candle['ma_200']
        
        # Condition: Strong bullish candle
        candle_body_size = current_candle['close'] - current_candle['open']
        is_bullish = candle_body_size > 0
        closes_near_high = (current_candle['high'] - current_candle['close']) <= (candle_body_size * 0.2) 
        
        if (crossed_above or (current_candle['low'] >= ma_val and last_candle['low'] < last_candle['ma_44'])) and is_bullish and closes_near_high:
            if ma_200_rising and price_above_200:
                logger.info(f"[{self.symbol}] BUY COND MET: Crossed 44 MA & 200 MA rising. Price: {current_candle['close']}")
            
            entry_price = current_candle['close']
            sl = current_candle['low'] - 0.05 * current_candle['low'] # Stop loss at recent candle low or slight buffer
            
            # Use RR ratio to set target
            risk = entry_price - sl
            target = entry_price + (risk * self.reward_risk_ratio)
            
            self.execute_trade(
                side="BUY", 
                price=entry_price, 
                sl=sl, 
                target=target
            )
