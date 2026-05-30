import os
from dotenv import load_dotenv
import time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import pandas as pd

# ── Config ──────────────────────────────────────────
load_dotenv()

API_KEY    = os.getenv("PK3VRB3CMEECAO3VMKYSAK74TL")
SECRET_KEY = os.getenv("5HLBmHGBsCv2RiSz2XqzXirjCJDp93Q6tRxzbFSop7YJ")
SYMBOL     = "AAPL"
SHORT_MA   = 9
LONG_MA    = 21
POSITION_PCT = 0.20   # 20% of cash per trade
STOP_LOSS  = 0.03     # 3%
TAKE_PROFIT = 0.06    # 6%

# ── Clients (paper=True keeps it in paper market) ───
trade_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client  = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# ── Helpers ──────────────────────────────────────────
def get_prices(symbol, lookback_days=60):
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=datetime.now() - timedelta(days=lookback_days)
    )
    bars = data_client.get_stock_bars(req).df
    return bars["close"].values.tolist()

def sma(prices, period):
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def get_signal(prices):
    short = sma(prices, SHORT_MA)
    long_ = sma(prices, LONG_MA)
    if short is None or long_ is None:
        return 0
    if short > long_:
        return 1   # BUY
    elif short < long_:
        return -1  # SELL
    return 0

def get_position(symbol):
    try:
        return trade_client.get_open_position(symbol)
    except:
        return None

def get_cash():
    acct = trade_client.get_account()
    return float(acct.cash)

def place_order(symbol, side, qty):
    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,
        time_in_force=TimeInForce.DAY
    )
    trade_client.submit_order(order)
    print(f"[ORDER] {side.value} {qty} {symbol}")

# ── Main loop ────────────────────────────────────────
print("Bot started on Alpaca paper market...")

while True:
    try:
        prices = get_prices(SYMBOL)
        signal = get_signal(prices)
        position = get_position(SYMBOL)
        current_price = prices[-1]

        # Check stop loss / take profit on open position
        if position:
            entry = float(position.avg_entry_price)
            pct_chg = (current_price - entry) / entry
            if pct_chg <= -STOP_LOSS:
                print(f"Stop loss hit: {pct_chg:.2%}")
                place_order(SYMBOL, OrderSide.SELL, int(position.qty))
            elif pct_chg >= TAKE_PROFIT:
                print(f"Take profit hit: {pct_chg:.2%}")
                place_order(SYMBOL, OrderSide.SELL, int(position.qty))

        # Entry logic
        elif signal == 1 and not position:
            cash = get_cash()
            qty = int((cash * POSITION_PCT) / current_price)
            if qty > 0:
                place_order(SYMBOL, OrderSide.BUY, qty)

        # Exit logic
        elif signal == -1 and position:
            place_order(SYMBOL, OrderSide.SELL, int(position.qty))

        print(f"Price: ${current_price:.2f} | Signal: {signal} | Pos: {bool(position)}")
        time.sleep(60)  # runs every 1 minute

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(30)