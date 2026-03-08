import pandas as pd
import time
from binance.client import Client
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))  
import config  # config.py should contain api_key and api_secret


# 🔐 Binance API connection
client = Client(config.api_key, config.api_secret)


def fetch_15m_data(symbol="DOGEUSDT", days=180):
    """
    Fetch 15-minute kline data for specified symbol (180 days = ~6 months).
    Returns OHLCV data as list of lists.
    """
    interval = Client.KLINE_INTERVAL_15MINUTE
    ms_per_day = 24 * 60 * 60 * 1000
    end_time = int(time.time() * 1000)
    since = end_time - (days * ms_per_day)
    limit = 1000
    all_klines = []


    print(f"📡 Fetching 15m {symbol} data ({days} days)...")


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


    print(f"✅ Completed! {len(all_klines)} 15m {symbol} candles fetched.")  
    return all_klines


def save_to_csv(klines, filename="data/doge_usdt_15m.csv"):
    """
    Save kline data to CSV file in data/ folder.
    Keeps only: timestamp, open, high, low, close, volume
    """
    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.to_csv(filename, index=False)
    print(f"💾 Saved to {filename} ({len(df)} rows)")


if __name__ == "__main__":
    klines = fetch_15m_data("DOGEUSDT", days=180)
    data_dir = r"C:\Users\aykta\Desktop\crypto\data"
    os.makedirs(data_dir, exist_ok=True)
    save_to_csv(klines, os.path.join(data_dir, "doge_usdt_15m.csv"))
