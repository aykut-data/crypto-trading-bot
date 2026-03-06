import pandas as pd
import time
from binance.client import Client
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))  
import config  # config.py should contain api_key and api_secret

# 🔐 Binance API connection
client = Client(config.api_key, config.api_secret)

def fetch_1d_data(symbol="BTCUSDT", days=365):
    """
    Fetch 1-day kline data for specified symbol (default 365 days = ~1 year).
    Returns OHLCV data as list of lists.
    """
    interval = Client.KLINE_INTERVAL_1DAY
    ms_per_day = 24 * 60 * 60 * 1000
    end_time = int(time.time() * 1000)
    since = end_time - (days * ms_per_day)
    limit = 1000
    all_klines = []

    print(f"📡 Fetching 1d {symbol} data ({days} days ≈ {days} candles)...")

    while since < end_time:
        try:
            klines = client.get_klines(
                symbol=symbol,
                interval=interval,
                startTime=since,
                endTime=end_time,
                limit=limit
            )
        except Exception as e:
            print(f"⚠️ API error: {e}")
            time.sleep(5)
            continue

        if not klines:
            print("🚫 No more data.")
            break

        all_klines.extend(klines)
        since = klines[-1][0] + 1  # Next candle after last
        
        print(f"⏳ Total: {len(all_klines)} candles...")
        time.sleep(0.8)  # Rate limit delay

        if klines[-1][0] >= end_time:
            break

    print(f"✅ Completed! {len(all_klines)} 1d {symbol} candles fetched.")
    return all_klines

def save_to_csv(klines, filename="btc_usdt_1d.csv"):
    """
    Save kline data to CSV file.
    Keeps only: timestamp, open, high, low, close, volume.
    """
    # 📁 Ensure data directory exists
    data_dir = r"C:\Users\aykta\Desktop\crypto\data"
    os.makedirs(data_dir, exist_ok=True)
    filepath = os.path.join(data_dir, filename)
    
    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.to_csv(filepath, index=False)
    print(f"💾 Saved to {filepath} ({len(df)} rows)")

if __name__ == "__main__":
    klines = fetch_1d_data("BTCUSDT", days=365)
    save_to_csv(klines, "btc_usdt_1d.csv")
