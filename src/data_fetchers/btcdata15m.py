import pandas as pd
import time
from binance.client import Client
import sys
import os

# 📍 Dynamic path configuration
# current_dir: points to src/data_fetchers/
current_dir = os.path.dirname(os.path.abspath(__file__))
# base_dir: points to the Root directory (data_fetchers -> src -> root)
base_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))

# 🔑 Add root directory to sys.path to import config.py
sys.path.append(base_dir) 
import config 

# 🔐 Binance API connection
client = Client(config.api_key, config.api_secret)

def fetch_15m_data(symbol="BTCUSDT", days=180):
    """
    Fetch 15-minute kline data for the specified symbol from Binance.
    """
    interval = Client.KLINE_INTERVAL_15MINUTE
    ms_per_day = 24 * 60 * 60 * 1000
    end_time = int(time.time() * 1000)
    since = end_time - (days * ms_per_day)
    limit = 1000
    all_klines = []

    print(f"📡 Fetching 15m {symbol} data for the last {days} days...")

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
            print(f"⚠️ API error encountered: {e}")
            time.sleep(5)
            continue

        if not klines:
            print("🚫 No more data returned from API.")
            break

        all_klines.extend(klines)
        since = klines[-1][0] + 1 
        
        print(f"⏳ Progress: {len(all_klines)} candles collected...")
        time.sleep(0.5) # Anti-ban rate limit protection

        if klines[-1][0] >= end_time:
            break

    print(f"✅ Task Completed! Total {len(all_klines)} candles fetched.")  
    return all_klines

def save_to_csv(klines, full_path):
    """
    Process klines into a DataFrame and save to the specified CSV path.
    """
    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    
    # Select essential columns only
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    
    # Convert timestamp to human-readable datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    
    # Ensure the target directory exists dynamically
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    # Save the file
    df.to_csv(full_path, index=False)
    print(f"💾 Successfully saved to: {full_path} ({len(df)} rows)")

if __name__ == "__main__":
    # 🎯 Define dynamic target path pointing to root/data/
    data_dir = os.path.join(base_dir, 'data')
    target_file = os.path.join(data_dir, "btc_usdt_15m.csv")
    
    # Fetch data
    raw_data = fetch_15m_data("BTCUSDT", days=180)
    
    # Save to dynamic path
    save_to_csv(raw_data, target_file)