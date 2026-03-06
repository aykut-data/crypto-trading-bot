import pandas as pd
import numpy as np
import talib
import os

def calculate_indicators(df):
    """
    Calculate professional technical indicators using TA-Lib
    Input: DataFrame with 'open', 'high', 'low', 'close', 'volume' columns
    """
    # Ensure float dtypes for TA-Lib
    df = df.copy()
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # RSI (14-period)
    df['RSI'] = talib.RSI(df['close'], timeperiod=14)
    
    # MACD A (Fast: 8,17,9) 
    df['macdA_fast'], _, df['macdA_signal'] = talib.MACD(df['close'], fastperiod=8, slowperiod=17, signalperiod=9)
    
    # MACD B (Standard: 12,26,9)
    df['macdB_fast'], _, df['macdB_signal'] = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
    
    # Stochastic Oscillator (5,3,3,3)
    df['slowk'], df['slowd'] = talib.STOCH(
        df['high'], df['low'], df['close'], 
        fastk_period=5, slowk_period=3, slowd_period=3
    )
    
    # EMAs
    df['EMA_5'] = talib.EMA(df['close'], timeperiod=5)
    df['EMA_10'] = talib.EMA(df['close'], timeperiod=10)
    
    # ATR (Average True Range)
    df['ATR'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    
    # Bollinger Bands (20-period, 2 std)
    df['Bollinger_upper'], _, df['Bollinger_lower'] = talib.BBANDS(df['close'], timeperiod=20)
    
    # ADX (Average Directional Index)
    df['ADX'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
    
    return df.dropna()

if __name__ == "__main__":
    # Data directory
    data_dir = r"C:\Users\aykta\Desktop\crypto\data"
    
    # Load 4-hour data
    input_file = f"{data_dir}/btc_usdt_4h.csv"
    print("📊 Loading 4h BTCUSDT data...")
    
    df = pd.read_csv(input_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate indicators
    print("🔢 Calculating TA-Lib indicators...")
    df_indicators = calculate_indicators(df)
    
    # Save to data folder
    output_file = f"{data_dir}/btc_usdt_4h_indicators.csv"
    df_indicators.to_csv(output_file, index=False)
    
    print("✅ 4h indicators saved:", output_file)
