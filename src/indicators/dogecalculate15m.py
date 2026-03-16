import pandas as pd
import numpy as np
import talib
import os
import sys

def calculate_indicators_15m(df):
    """
    Indicator calculation function 100% compatible with Live Bot and Backtest.
    """
    df = df.copy()
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # --- RSI ---
    df['RSI'] = talib.RSI(df['close'], timeperiod=14)
    
    # --- STOCHRSI ---
    df['stochrsi_k'], df['stochrsi_d'] = talib.STOCH(
        df['RSI'], df['RSI'], df['RSI'],
        fastk_period=14, slowk_period=3, slowk_matype=0,
        slowd_period=3, slowd_matype=0
    )
    
    # --- MACD A (8, 17, 9) ---
    df['macdA_macd'], df['macdA_signal'], df['macdA_hist'] = talib.MACD(
        df['close'], fastperiod=8, slowperiod=17, signalperiod=9
    )
    
    # --- MACD B (12, 26, 9) ---
    df['macdB_macd'], df['macdB_signal'], df['macdB_hist'] = talib.MACD(
        df['close'], fastperiod=12, slowperiod=26, signalperiod=9
    )
    
    # --- EMAs ---
    df['EMA_5'] = talib.EMA(df['close'], timeperiod=5)
    df['EMA_10'] = talib.EMA(df['close'], timeperiod=10)
    df['EMA_20'] = talib.EMA(df['close'], timeperiod=20)
    df['EMA_50'] = talib.EMA(df['close'], timeperiod=50)
    df['EMA_200'] = talib.EMA(df['close'], timeperiod=200)
    
    # --- ATR ---
    df['ATR'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    
    # --- Bollinger Bands ---
    df['Bollinger_upper'], df['Bollinger_middle'], df['Bollinger_lower'] = talib.BBANDS(df['close'], timeperiod=20)
    
    # --- ADX ---
    df['ADX'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
    
    return df

if __name__ == "__main__":
    # 📍 Dynamic path configuration
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
    data_dir = os.path.join(base_dir, 'data')
    
    input_file = os.path.join(data_dir, "doge_usdt_15m.csv")
    output_file = os.path.join(data_dir, "doge_usdt_15m_indicators.csv")
    
    if os.path.exists(input_file):
        print(f"📊 Loading raw 15m data from: {input_file}")
        df = pd.read_csv(input_file)
        
        # Data cleaning
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        print("🔢 Calculating indicators...")
        df_indicators = calculate_indicators_15m(df)
        
        # Drop NaN rows (initial candles needed for calculation)
        df_indicators = df_indicators.dropna()
        
        df_indicators.to_csv(output_file, index=False)
        
        print(f"✅ SUCCESS: {output_file} created.")
        print(f"📉 Total data points: {len(df_indicators)}")
    else:
        print(f"❌ Error: {input_file} not found!")