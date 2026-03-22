# Nifty 50 algorithmic Auto-Trader (Zerodha + 44 MA)

A fully automated algorithmic trading bot designed specifically for the Indian Stock Market (Nifty 50). This bot uses a highly customized version of Siddharth Bhanushali's 44 Moving Average strategy, heavily reinforced with a 200 EMA trend confirmation filter.

It connects to Zerodha's Kite Connect API for live trade execution and dynamically fetches real-time prices for all 50 Nifty index stocks completely free using Yahoo Finance.

## Core Features
* **Nifty 50 Multi-Tracking:** Simultaneously monitors all Nifty 50 stocks in real-time.
* **Intelligent Strategy Engine:** 
  * 44-Period EMA Crossover Detection.
  * 200-Period EMA Macro-Trend Confirmation.
  * Strong Bullish Volume Candlestick checks.
* **Auto-Execution:** Zero-touch order placement (Buy/Sell) directly on Zerodha Kite.
* **Advanced Risk Management:** Built-in Kill Switch, configurable Stop-Losses, and strict Risk-to-Reward ratio targets.
* **Beautiful Dashboard:** Clean, live-updating web interface mapping the real-time distance-to-crossover for every Nifty 50 stock.

## Quickstart

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Setup your `.env` file with your `KITE_API_KEY` and `KITE_API_SECRET`.
4. Run the Uvicorn engine: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env`
5. Navigate to `http://localhost:8000/dashboard/` to login to Kite and start the Engine.
