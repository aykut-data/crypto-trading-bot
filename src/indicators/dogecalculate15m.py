import pandas as pd
import numpy as np
import talib
import os

def calculate_indicators_15m(df):
    """
    Canlı bot ve Backtest ile %100 uyumlu indikatör hesaplama fonksiyonu.
    """
    df = df.copy()
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    
    # --- RSI ---
    df['RSI'] = talib.RSI(df['close'], timeperiod=14)
    
    # --- STOCHRSI (Canlı bot isimlendirmesiyle) ---
    df['stochrsi_k'], df['stochrsi_d'] = talib.STOCH(
        df['RSI'], df['RSI'], df['RSI'],
        fastk_period=14, slowk_period=3, slowk_matype=0,
        slowd_period=3, slowd_matype=0
    )
    
    # --- MACD A (8, 17, 9) - Sütun isimleri düzeltildi ---
    df['macdA_macd'], df['macdA_signal'], df['macdA_hist'] = talib.MACD(
        df['close'], fastperiod=8, slowperiod=17, signalperiod=9
    )
    
    # --- MACD B (12, 26, 9) - Sütun isimleri düzeltildi ---
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
    data_dir = r"C:\Users\aykta\Desktop\crypto\data"
    input_file = os.path.join(data_dir, "doge_usdt_15m.csv")
    
    if os.path.exists(input_file):
        print("📊 Loading raw 15m data...")
        df = pd.read_csv(input_file)
        
        # Temizlik: Eğer timestamp saniye cinsindeyse çevir
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        print("🔢 Calculating matching indicators...")
        df_indicators = calculate_indicators_15m(df)
        
        # NaN satırları temizle (Giriş mumları indikatör için yetersiz olanlar)
        df_indicators = df_indicators.dropna()
        
        output_file = os.path.join(data_dir, "doge_usdt_15m_indicators.csv")
        df_indicators.to_csv(output_file, index=False)
        
        print(f"✅ SUCCESS: {output_file} created with correct columns.")
        print(f"📉 Total data points: {len(df_indicators)}")
    else:
        print(f"❌ Error: {input_file} not found!")