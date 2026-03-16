import pandas as pd
import numpy as np
from datetime import datetime, timezone
import os
import sys

def run_backtest(symbol="DOGE", timeframe="15m"):
    """
    Professional Backtest Engine compatible with Golden Standard indicator files.
    """
    # 📍 Dynamic path configuration
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(current_dir, '..'))
    data_dir = os.path.join(base_dir, 'data')
    
    file_name = f"{symbol.lower()}_usdt_{timeframe}_indicators.csv"
    file_path = os.path.join(data_dir, file_name)

    if not os.path.exists(file_path):
        print(f"❌ ERROR: File not found at {file_path}")
        return

    print(f"📂 Loading data for {symbol} {timeframe}...")
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    # 🚀 PARAMETERS
    balance = 1000.0
    fixed_margin = 200.0
    leverage = 10
    fee = 0.00075
    cooldown_min = 150
    trailing_pct = 0.02
    
    sl_atr_mult = 1.5
    tp_atr_mult = 7
    
    # 📡 SIGNAL DEFINITIONS (Using Golden Standard Columns)
    df['Buy_Signal'] = (df['RSI'] < 29) & (df['macdA_macd'] < -0.0001) & (df['macdA_signal'] < -0.0001) & \
                       (df['stochrsi_k'] < 15) & (df['stochrsi_d'] < 25) & \
                       (df['close'] < df['Bollinger_lower']) & (df['ADX'] > 20)

    df['Sell_Signal'] = (df['RSI'] > 70) & (df['macdB_macd'] > 0.0001) & (df['macdB_signal'] > 0.0001) & \
                        (df['stochrsi_k'] > 85) & (df['stochrsi_d'] > 75) & \
                        (df['close'] > df['Bollinger_upper']) & (df['ADX'] > 23)

    # State Variables
    pos_type = None
    entry_price = 0
    sl_price = 0
    tp_price = 0
    last_trade_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    trades_count = 0

    print("\n" + "="*130)
    print(f"{'TIME':<22} | {'TYPE':<6} | {'STATUS':<10} | {'PRICE':<10} | {'SL (Active)':<10} | {'TP':<10} | {'PNL':<8} | {'BALANCE'}")
    print("="*130)

    for i in range(len(df)):
        row = df.iloc[i]
        curr_time = row['timestamp'].replace(tzinfo=timezone.utc) if row['timestamp'].tzinfo is None else row['timestamp']
        c_close = row['close']

        if pos_type:
            reason = None
            
            # --- LONG MONITORING ---
            if pos_type == 'long':
                if c_close >= tp_price: reason = "TP"
                elif c_close <= sl_price: reason = "SL"
                elif row['Sell_Signal']: reason = "REVERSE"
                
                if c_close > entry_price:
                    sl_price = max(sl_price, c_close * (1 - trailing_pct))

            # --- SHORT MONITORING ---
            elif pos_type == 'short':
                if c_close <= tp_price: reason = "TP"
                elif c_close >= sl_price: reason = "SL"
                elif row['Buy_Signal']: reason = "REVERSE"
                
                if c_close < entry_price:
                    sl_price = min(sl_price, c_close * (1 + trailing_pct))

            if reason:
                exit_price = c_close 
                final_exit = exit_price * (1 - fee) if pos_type == 'long' else exit_price * (1 + fee)
                
                profit = (final_exit - entry_price) * leverage * (fixed_margin / entry_price) if pos_type == 'long' else \
                         (entry_price - final_exit) * leverage * (fixed_margin / entry_price)
                
                balance += profit
                trades_count += 1
                print(f"{str(curr_time):<22} | {pos_type.upper():<6} | {reason:<10} | {exit_price:<10.6f} | {sl_price:<10.6f} | {tp_price:<10.6f} | {profit:<8.2f} | {balance:.2f} USDT")
                pos_type = None
                last_trade_time = curr_time

        else:
            # --- ENTRY CONTROL ---
            time_diff = (curr_time - last_trade_time).total_seconds() / 60
            if time_diff >= cooldown_min:
                if row['Buy_Signal'] or row['Sell_Signal']:
                    pos_type = 'long' if row['Buy_Signal'] else 'short'
                    entry_price = c_close * (1 + fee) if pos_type == 'long' else c_close * (1 - fee)
                    atr = row['ATR']
                    
                    sl_price = entry_price - (atr * sl_atr_mult) if pos_type == 'long' else entry_price + (atr * sl_atr_mult)
                    tp_price = entry_price + (atr * tp_atr_mult) if pos_type == 'long' else entry_price - (atr * tp_atr_mult)
                    
                    print(f"{str(curr_time):<22} | {pos_type.upper():<6} | {'ENTRY':<10} | {entry_price:<10.6f} | {sl_price:<10.6f} | {tp_price:<10.6f} | {'-':<8} | {'INITIAL'}")
                    last_trade_time = curr_time

    print("="*130)
    print(f"📉 TOTAL TRADES: {trades_count} | 💰 FINAL BALANCE: {balance:.2f} USDT")

if __name__ == "__main__":
    run_backtest("DOGE", "15m")