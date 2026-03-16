import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import api_key, api_secret
import asyncio
import pandas as pd
import numpy as np
import talib
import logging
import random
import warnings
from datetime import datetime, timezone, timedelta
from bokeh.plotting import figure, curdoc
from bokeh.models import ColumnDataSource, DatetimeTickFormatter
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from binance import AsyncClient, BinanceSocketManager
from bokeh.server.server import Server


# Suppress Bokeh warnings for large integers (timestamps)
warnings.filterwarnings("ignore", category=UserWarning, module="bokeh")


# Logging configuration (extra handler for console as well)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('trading_bot.log', mode='a')]
)
file_handler = logging.FileHandler('trading_bot.log', mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)


# Reconnection attempt count and wait time
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_WAIT_TIME = 10


class BinanceClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None

    async def create(self):
        self.client = await AsyncClient.create(self.api_key, self.api_secret)

    async def get_symbol_info(self, symbol):
        try:
            info = await self.client.get_symbol_info(symbol)
            return info
        except Exception as e:
            logging.error(f"Error fetching symbol info: {e}")
            return None

    async def get_positions(self):
        try:
            positions = await self.client.futures_position_information()
            return positions
        except Exception as e:
            logging.error(f"Error fetching positions: {e}")
            return []

    async def buy(self, symbol, quantity):
        try:
            order = await self.client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity
            )
            logging.info(f"BUY order placed: {order}")
            print(f"[SUCCESS] BUY order ID: {order['orderId']}", file=sys.stderr)
        except Exception as e:
            logging.error(f"Error placing BUY order: {e}")
            print(f"[ERROR] BUY order error: {e}", file=sys.stderr)

    async def sell(self, symbol, quantity):
        try:
            order = await self.client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity
            )
            logging.info(f"SELL order placed: {order}")
            print(f"[SUCCESS] SELL order ID: {order['orderId']}", file=sys.stderr)
        except Exception as e:
            logging.error(f"Error placing SELL order: {e}")
            print(f"[ERROR] SELL order error: {e}", file=sys.stderr)


def determine_candle_color(open_price, close_price):
    """Determines the color of the candle."""
    return 'green' if close_price >= open_price else 'red'


def calculate_technical_indicators(df):
    """Calculates technical indicators in the given dataframe. Each indicator calculation is a single line."""
    try:
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        
        # --- INDICATOR CALCULATIONS (SINGLE LINE) ---
        df['RSI'] = talib.RSI(df['close'].values, timeperiod=14)
        df['stochrsi_k'], df['stochrsi_d'] = talib.STOCH(df['RSI'], df['RSI'], df['RSI'], fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
        df['macdA_macd'], df['macdA_signal'], df['macdA_hist'] = talib.MACD(df['close'], fastperiod=8, slowperiod=17, signalperiod=9)
        df['macdB_macd'], df['macdB_signal'], df['macdB_hist'] = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['EMA_5'] = talib.EMA(df['close'].values, timeperiod=5)
        df['EMA_10'] = talib.EMA(df['close'].values, timeperiod=10)
        df['OBV'] = talib.OBV(df['close'].values, df['volume'].values)
        df['OBV_diff'] = df['OBV'].diff()
        df['ATR'] = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
        df['Bollinger_upper'], df['Bollinger_middle'], df['Bollinger_lower'] = talib.BBANDS(df['close'], timeperiod=20)
        df['ADX'] = talib.ADX(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
        df['color'] = [determine_candle_color(o, c) for o, c in zip(df['open'], df['close'])]
        
        # NaN cleanup
        for col in df.select_dtypes(include=['float64', 'float32']).columns:
            df[col] = df[col].ffill().bfill().fillna(0)
            
    except Exception as e:
        logging.error(f"Error calculating indicators: {e}", exc_info=True)
    return df

def fill_missing_klines_data(df, freq='15min'):
    """Fills missing data and resamples the time series at the specified frequency."""
    try:
        df = df.drop_duplicates(subset='timestamp')
        df = df.set_index('timestamp').resample(freq).ffill().bfill().reset_index()
    except Exception as e:
        logging.error(f"Error filling missing data: {e}", exc_info=True)
    return df


def generate_trade_signals(df, print_details=True):
    """Determines buy and sell signals."""
    try:
        # --- CONDITION DEFINITIONS ---
        buy_cond_rsi = df['RSI'] < 29
        buy_cond_macd = (df['macdA_macd'] < -0.0001) & (df['macdA_signal'] < -0.0001)
        buy_cond_stoch = (df['stochrsi_k'] < 15) & (df['stochrsi_d'] < 25)
        buy_cond_boll = df['close'] < df['Bollinger_lower']
        buy_cond_adx = df['ADX'] > 20

        sell_cond_rsi = df['RSI'] > 70
        sell_cond_macd = (df['macdB_macd'] > 0.0001) & (df['macdB_signal'] > 0.0001)
        sell_cond_stoch = (df['stochrsi_k'] > 85) & (df['stochrsi_d'] > 75)
        sell_cond_boll = df['close'] > df['Bollinger_upper']
        sell_cond_adx = df['ADX'] > 23

        # --- SIGNAL ASSIGNMENTS ---
        df['Buy'] = buy_cond_rsi & buy_cond_macd & buy_cond_stoch & buy_cond_boll & buy_cond_adx
        df['Sell'] = sell_cond_rsi & sell_cond_macd & sell_cond_stoch & sell_cond_boll & sell_cond_adx

        # --- DETAILED TERMINAL OUTPUT ---
        last_idx = -1
        if len(df) > 0 and print_details:
            print("\n" + "="*85, file=sys.stderr)
            # Header line
            print(f"[CANDLE CLOSE DETAILS] Time: {df['timestamp'].iloc[last_idx]} | Close: {df['close'].iloc[last_idx]:.6f} | Volume: {df['volume'].iloc[last_idx]:.2f}", file=sys.stderr)
            
            # Indicator Values
            print(f"[VALUES] RSI: {df['RSI'].iloc[last_idx]:.2f} | ADX: {df['ADX'].iloc[last_idx]:.2f} | ATR: {df['ATR'].iloc[last_idx]:.6f}", file=sys.stderr)
            print(f"[MACD A] Macd: {df['macdA_macd'].iloc[last_idx]:.6f} | Sig: {df['macdA_signal'].iloc[last_idx]:.6f} | Hist: {df['macdA_hist'].iloc[last_idx]:.6f}", file=sys.stderr)
            print(f"[MACD B] Macd: {df['macdB_macd'].iloc[last_idx]:.6f} | Sig: {df['macdB_signal'].iloc[last_idx]:.6f} | Hist: {df['macdB_hist'].iloc[last_idx]:.6f}", file=sys.stderr)
            print(f"[STOCHRSI] K: {df['stochrsi_k'].iloc[last_idx]:.2f} | D: {df['stochrsi_d'].iloc[last_idx]:.2f}", file=sys.stderr)
            print(f"[BOLLINGER] Lower: {df['Bollinger_lower'].iloc[last_idx]:.6f} | Middle: {df['Bollinger_middle'].iloc[last_idx]:.6f} | Upper: {df['Bollinger_upper'].iloc[last_idx]:.6f}", file=sys.stderr)
            
            # Buy Condition Analysis
            print(f"[BUY CONDITIONS] "
                  f"RSI<29: {df['RSI'].iloc[last_idx] < 29} | "
                  f"MACDA_Neg: {buy_cond_macd.iloc[last_idx]} | "
                  f"K<15: {df['stochrsi_k'].iloc[last_idx] < 15} | "
                  f"D<25: {df['stochrsi_d'].iloc[last_idx] < 25} | "
                  f"Close<BolL: {buy_cond_boll.iloc[last_idx]} | "
                  f"ADX>20: {buy_cond_adx.iloc[last_idx]}", file=sys.stderr)
            
            # Sell Condition Analysis
            print(f"[SELL CONDITIONS] "
                  f"RSI>70: {df['RSI'].iloc[last_idx] > 70} | "
                  f"MACDB_Pos: {sell_cond_macd.iloc[last_idx]} | "
                  f"K>85: {df['stochrsi_k'].iloc[last_idx] > 85} | "
                  f"D>75: {df['stochrsi_d'].iloc[last_idx] > 75} | "
                  f"Close>BolU: {sell_cond_boll.iloc[last_idx]} | "
                  f"ADX>23: {sell_cond_adx.iloc[last_idx]}", file=sys.stderr)
            
            # Overall Status
            print(f"[SIGNAL STATUS] Buy: {df['Buy'].iloc[last_idx]} | Sell: {df['Sell'].iloc[last_idx]} | Total Buy: {df['Buy'].sum()} | Total Sell: {df['Sell'].sum()}", file=sys.stderr)
            print("="*85 + "\n", file=sys.stderr)
            
        logging.info(f"Generated signals: Buy: {df['Buy'].sum()}, Sell: {df['Sell'].sum()}")
    except Exception as e:
        logging.error(f"Error generating signals: {e}", exc_info=True)
        print(f"[ERROR] Signal calculation failed: {e}", file=sys.stderr)
    return df

async def fetch_initial_klines(client, symbol, interval='15m', limit=500):
    """Fetches initial data from Binance API. Set print_details=False for initial load."""
    try:
        klines = await client.get_historical_klines(symbol, interval, f'{limit * 15} minutes ago UTC')
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
        df = pd.DataFrame(klines, columns=columns)
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Europe/Dublin')

        df = fill_missing_klines_data(df, freq='15min')
        df = calculate_technical_indicators(df)
        df = generate_trade_signals(df, print_details=False)  # Do not print during initial load
        logging.info(f"Fetched initial data for {symbol}: {df.shape[0]} rows")
        return df
    except (ValueError, KeyError, TypeError) as e:
        logging.error(f"Error fetching initial data for {symbol}: {e}", exc_info=True)
        return pd.DataFrame()


def check_and_fill_gaps(df):
    """Checks and fills missing timestamps."""
    try:
        expected_timestamps = pd.date_range(start=df['timestamp'].min(), end=df['timestamp'].max(), freq='15min')
        missing_timestamps = expected_timestamps.difference(df['timestamp'])
        if not missing_timestamps.empty:
            missing_df = pd.DataFrame(missing_timestamps, columns=['timestamp'])
            df = pd.concat([df, missing_df], ignore_index=True).sort_values(by='timestamp')
            df['open'] = df['open'].ffill().bfill()
            df['high'] = df['high'].ffill().bfill()
            df['low'] = df['low'].ffill().bfill()
            df['close'] = df['close'].ffill().bfill()
            df['volume'] = df['volume'].ffill().bfill()
            df = calculate_technical_indicators(df)
            df = generate_trade_signals(df, print_details=False)  # Do not print during gap filling
    except (ValueError, KeyError, TypeError) as e:
        logging.error(f"Error checking and filling gaps: {e}", exc_info=True)
    return df


def add_signal_labels(plot, source):
    """Adds buy and sell signals as labels to the chart."""
    try:
        buy_indices = [i for i in range(len(source.data['timestamp'])) if source.data['Buy'][i]]
        sell_indices = [i for i in range(len(source.data['timestamp'])) if source.data['Sell'][i]]

        buy_x = [source.data['timestamp'][i] for i in buy_indices]
        buy_y = [source.data['low'][i] * 0.99 + random.uniform(-0.01, 0.01) for i in buy_indices]

        sell_x = [source.data['timestamp'][i] for i in sell_indices]
        sell_y = [source.data['high'][i] * 1.01 + random.uniform(-0.01, 0.01) for i in sell_indices]

        plot.scatter(x=buy_x, y=buy_y, size=10, color="green", marker="triangle", legend_label="Buy", line_width=2)
        plot.scatter(x=sell_x, y=sell_y, size=10, color="red", marker="inverted_triangle", legend_label="Sell", line_width=2)
    except (ValueError, KeyError, TypeError) as e:
        logging.error(f"Error adding signal labels: {e}", exc_info=True)


class TradingBot:
    def __init__(
        self,
        balance=200,
        leverage=10,
        binance_client=None,
        symbol='',
        precision=2,
        sl_atr_mult=1.5,      
        tp_atr_mult=7.0,      
        trailing_stop_loss_pct=0.02,  # 2% trailing (secondary protection)
        min_time_between_trades=timedelta(minutes=150)
    ):
        self.balance = balance
        self.fixed_entry_amount = balance
        self.leverage = leverage
        self.holding = False
        self.entry_price = 0.0
        self.stop_loss = None
        self.take_profit = None
        self.binance_client = binance_client
        self.symbol = symbol
        self.precision = precision
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.trailing_stop_loss_pct = trailing_stop_loss_pct
        self.min_time_between_trades = min_time_between_trades
        self.last_trade_time = datetime.min.replace(tzinfo=timezone.utc)  # Add UTC timezone
        self.position_type = None

        # Dynamic levels
        self.sl_price = None
        self.tp_price = None
        self.best_price_since_entry = None  # Peak for long, bottom for short
        self.position_qty = 0.0  # Position quantity (set after opening)

    def find_atr_at_entry(self, df, entry_price):
        """Finds the candle with the close price closest to entry_price in the DataFrame and returns the ATR at that moment."""
        if df.empty or 'close' not in df.columns or 'ATR' not in df.columns:
            return None
        # Find the closest index based on close price
        closest_idx = (df['close'] - entry_price).abs().idxmin()
        atr_at_entry = df['ATR'].iloc[closest_idx]
        entry_time_approx = df['timestamp'].iloc[closest_idx]
        logging.info(f"Approximate entry time: {entry_time_approx}, ATR at entry: {atr_at_entry:.6f}")
        print(f"[DEBUG] Approximate entry time: {entry_time_approx}, Entry ATR: {atr_at_entry:.6f}", file=sys.stderr)
        return atr_at_entry

    async def initialize(self, df=None):
        positions = await self.binance_client.get_positions()
        open_positions = [p for p in positions if p['symbol'] == self.symbol and float(p['positionAmt']) != 0]
        if open_positions:
            position = open_positions[0]
            pos_amt = float(position['positionAmt'])
            self.position_type = 'long' if pos_amt > 0 else 'short'
            self.entry_price = float(position['entryPrice'])
            self.position_qty = abs(pos_amt)

            # First try ATR with existing df (current data)
            entry_atr = None
            if df is not None and not df.empty:
                entry_atr = self.find_atr_at_entry(df, self.entry_price)
                print(f"[DEBUG] ATR calculated with current data: {entry_atr:.6f}", file=sys.stderr)

            # If df is insufficient or ATR is None, try with a small historical fetch (limit=1000, ~10 days)
            if entry_atr is None:
                # Small fetch function (uses async client in code)
                hist_df = await self.fetch_small_historical_for_atr()
                if not hist_df.empty:
                    entry_atr = self.find_atr_at_entry(hist_df, self.entry_price)
                    print(f"[DEBUG] ATR calculated with small historical data: {entry_atr:.6f}", file=sys.stderr)

            # Set 1:8 TP/SL when ATR is found
            if entry_atr is not None:
                if self.position_type == 'long':
                    self.tp_price = self.entry_price + entry_atr * self.tp_atr_mult
                    self.sl_price = self.entry_price - entry_atr * self.sl_atr_mult
                    self.best_price_since_entry = self.entry_price
                else:  # short
                    self.tp_price = self.entry_price - entry_atr * self.tp_atr_mult
                    self.sl_price = self.entry_price + entry_atr * self.sl_atr_mult
                    self.best_price_since_entry = self.entry_price
                print(f"[DEBUG] ATR-based levels set - ATR: {entry_atr:.6f}, TP: {self.tp_price:.6f}, SL: {self.sl_price:.6f}", file=sys.stderr)
                logging.info(f"ATR-based levels set for existing {self.position_type}: ATR {entry_atr}, TP {self.tp_price}, SL {self.sl_price}")
            else:
                # Fallback: 2% temporary protection
                if self.position_type == 'long':
                    self.tp_price = self.entry_price * (1 + self.trailing_stop_loss_pct)
                    self.sl_price = self.entry_price * (1 - self.trailing_stop_loss_pct)
                    self.best_price_since_entry = self.entry_price
                else:
                    self.tp_price = self.entry_price * (1 - self.trailing_stop_loss_pct)
                    self.sl_price = self.entry_price * (1 + self.trailing_stop_loss_pct)
                    self.best_price_since_entry = self.entry_price
                print(f"[DEBUG] 2% temporary levels set - TP: {self.tp_price:.6f}, SL: {self.sl_price:.6f}", file=sys.stderr)
                logging.warning("Fallback to 2% temporary levels due to ATR fetch failure")

            logging.info(
                f"Existing {self.position_type} position found for {self.symbol}: "
                f"Entry Price: {self.entry_price}, TP: {self.tp_price}, SL: {self.sl_price}"
            )
            print(f"[DEBUG] Existing position: {self.position_type}, Entry: {self.entry_price:.6f}, Qty: {pos_amt}", file=sys.stderr)
        else:
            logging.info(f"No open position for {self.symbol}")
            print(f"[DEBUG] No open position: {self.position_type}", file=sys.stderr)

    async def fetch_small_historical_for_atr(self, limit=1000):
        """Fetches small historical data for the current position (fallback)."""
        try:
            klines = await self.binance_client.client.get_historical_klines(self.symbol, '15m', f"{limit * 15} minutes ago UTC")
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
            df = pd.DataFrame(klines, columns=columns)
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Europe/Dublin')
            df = fill_missing_klines_data(df, freq='15min')
            df = calculate_technical_indicators(df)
            logging.info(f"Fetched small historical for ATR: {df.shape[0]} rows")
            return df
        except Exception as e:
            logging.error(f"Error fetching small historical for ATR: {e}", exc_info=True)
            return pd.DataFrame()

    async def buy(self, price, latest_atr):
        now = datetime.now(timezone.utc)
        time_diff = now - self.last_trade_time
        time_diff_min = time_diff.total_seconds() / 60
        print(f"[DEBUG] BUY attempt: Price {price:.6f}, ATR {latest_atr:.6f}, Time diff {time_diff_min:.1f} min, Pos {self.position_type}", file=sys.stderr)
        logging.info(f"BUY check: Time diff {time_diff_min:.1f} min, Required: 120 min, Position: {self.position_type}")

        # 120 min cooldown for new entries
        if self.position_type is not None:
            print(f"[WARNING] BUY blocked: Existing position {self.position_type}", file=sys.stderr)
            logging.warning(f"BUY blocked: Existing position {self.position_type}")
            return
        if time_diff < self.min_time_between_trades:
            remaining_min = (self.min_time_between_trades - time_diff).total_seconds() / 60
            print(f"[WARNING] BUY blocked: Cooldown active ({remaining_min:.1f} min remaining)", file=sys.stderr)
            logging.warning(f"BUY blocked: Cooldown active, {remaining_min:.1f} min left")
            return

        fee = 0.00075
        self.position_type = 'long'
        # Effective entry including commission
        self.entry_price = price * (1 + fee)

        # ATR-based 1:8 SL/TP
        self.sl_price = self.entry_price - latest_atr * self.sl_atr_mult
        self.tp_price = self.entry_price + latest_atr * self.tp_atr_mult
        self.best_price_since_entry = self.entry_price

        # Quantity calculation (min notional ~100)
        quantity = round((self.fixed_entry_amount * self.leverage) / self.entry_price, self.precision)
        quantity = max(quantity, 0.001)
        if quantity * self.entry_price < 100:
            quantity = round(100 / self.entry_price, self.precision)
        self.position_qty = quantity  # Set quantity

        print(f"[ORDER ATTEMPT] BUY LONG | {self.symbol}, Qty: {quantity}, Notional: ~{quantity * price:.2f} USDT, SL: {self.sl_price:.6f}, TP: {self.tp_price:.6f}", file=sys.stderr)
        await self.binance_client.buy(self.symbol, quantity)
        self.last_trade_time = now
        logging.info(
            f"BUY LONG: Entry: {self.entry_price:.6f}, SL: {self.sl_price:.6f}, "
            f"TP: {self.tp_price:.6f}, ATR: {latest_atr:.6f}, Qty: {quantity}"
        )

    async def short(self, price, latest_atr):
        now = datetime.now(timezone.utc)
        time_diff = now - self.last_trade_time
        time_diff_min = time_diff.total_seconds() / 60
        print(f"[DEBUG] SHORT attempt: Price {price:.6f}, ATR {latest_atr:.6f}, Time diff {time_diff_min:.1f} min, Pos {self.position_type}", file=sys.stderr)
        logging.info(f"SHORT check: Time diff {time_diff_min:.1f} min, Required: 120 min, Position: {self.position_type}")

        # 120 min cooldown for new entries
        if self.position_type is not None:
            print(f"[WARNING] SHORT blocked: Existing position {self.position_type}", file=sys.stderr)
            logging.warning(f"SHORT blocked: Existing position {self.position_type}")
            return
        if time_diff < self.min_time_between_trades:
            remaining_min = (self.min_time_between_trades - time_diff).total_seconds() / 60
            print(f"[WARNING] SHORT blocked: Cooldown active ({remaining_min:.1f} min remaining)", file=sys.stderr)
            logging.warning(f"SHORT blocked: Cooldown active, {remaining_min:.1f} min left")
            return

        fee = 0.00075
        self.position_type = 'short'
        # Effective entry including commission
        self.entry_price = price * (1 - fee)

        # ATR-based 1:8 SL/TP (symmetric)
        self.sl_price = self.entry_price + latest_atr * self.sl_atr_mult
        self.tp_price = self.entry_price - latest_atr * self.tp_atr_mult
        self.best_price_since_entry = self.entry_price

        # Quantity calculation (min notional ~100)
        quantity = round((self.fixed_entry_amount * self.leverage) / self.entry_price, self.precision)
        quantity = max(quantity, 0.001)
        if quantity * self.entry_price < 100:
            quantity = round(100 / self.entry_price, self.precision)
        self.position_qty = quantity  # Set quantity

        print(f"[ORDER ATTEMPT] SHORT SELL | {self.symbol}, Qty: {quantity}, Notional: ~{quantity * price:.2f} USDT, SL: {self.sl_price:.6f}, TP: {self.tp_price:.6f}", file=sys.stderr)
        await self.binance_client.sell(self.symbol, quantity)
        self.last_trade_time = now
        logging.info(
            f"SHORT SELL: Entry: {self.entry_price:.6f}, SL: {self.sl_price:.6f}, "
            f"TP: {self.tp_price:.6f}, ATR: {latest_atr:.6f}, Qty: {quantity}"
        )

    async def update_trailing_stop(self, price):
        """Updates the trailing SL during each candle (while position is open)."""
        if self.trailing_stop_loss_pct is None:
            return  # Exit if trailing is disabled
        
        if self.position_type == 'long' and price > self.entry_price:  # Favor: price > entry
            trailed = price * (1 - self.trailing_stop_loss_pct)  # Move SL up (with max)
            self.sl_price = max(self.sl_price, trailed)
            self.best_price_since_entry = max(self.best_price_since_entry or price, price)
            print(f"[DEBUG] Long Trailing SL updated: {self.sl_price:.6f} (Price: {price:.6f})", file=sys.stderr)
            logging.info(f"Long trailing updated: SL {self.sl_price}, Best: {self.best_price_since_entry}")
        
        elif self.position_type == 'short' and price < self.entry_price:  # Favor: price < entry
            trailed = price * (1 + self.trailing_stop_loss_pct)  # Move SL down (with min)
            self.sl_price = min(self.sl_price, trailed)
            self.best_price_since_entry = min(self.best_price_since_entry or price, price)
            print(f"[DEBUG] Short Trailing SL updated: {self.sl_price:.6f} (Price: {price:.6f})", file=sys.stderr)
            logging.info(f"Short trailing updated: SL {self.sl_price}, Best: {self.best_price_since_entry}")
        
        # Check TP/SL immediately after trailing update
        await self.check_and_close_if_needed(price)
    
    async def check_and_close_if_needed(self, price):
        """TP/SL check and closure after trailing update."""
        close_reason = None
        if self.position_type == 'long':
            if price >= self.tp_price:
                close_reason = "TP"
            elif price <= self.sl_price:
                close_reason = "SL"
            if close_reason:
                await self.sell(price)  # Close
        elif self.position_type == 'short':
            if price <= self.tp_price:
                close_reason = "TP"
            elif price >= self.sl_price:
                close_reason = "SL"
            if close_reason:
                await self.cover(price)  # Close

    async def sell(self, price):
        """Closes a LONG position and sweeps up any remaining dust."""
        now = datetime.now(timezone.utc)
        time_diff = now - self.last_trade_time
        time_diff_min = time_diff.total_seconds() / 60
        
        print(f"[DEBUG] SELL attempt (long close): Price {price:.6f}, Time diff {time_diff_min:.1f} min", file=sys.stderr)
        logging.info(f"SELL check: Time diff {time_diff_min:.1f} min, Position: {self.position_type}")

        if self.position_type != 'long':
            print(f"[WARNING] SELL blocked: No long position active ({self.position_type})", file=sys.stderr)
            return

        # --- Position Closure Logic ---
        quantity = self.position_qty
        fee = 0.00075
        exit_price = price * (1 - fee)
        profit = (exit_price - self.entry_price) * self.leverage * (quantity * self.entry_price / self.balance)
        self.balance += profit

        print(f"[ORDER ATTEMPT] SELL LONG CLOSE | {self.symbol}, Qty: {quantity}, Exit: {exit_price:.6f}, Profit: {profit:.2f}", file=sys.stderr)
        
        # 1. Execute the main close order
        await self.binance_client.sell(self.symbol, quantity)
        
        # 2. TRIGGER AUTOMATIC DUST CLEANUP
        # We wait 2 seconds to ensure Binance has updated the position on their servers.
        print(f"[INFO] Main position closed. Starting dust cleanup in 2 seconds...", file=sys.stderr)
        await asyncio.sleep(2) 
        await self.clean_leftover_position()

        # 3. Reset bot state for the next signal
        logging.info(f"SELL LONG: Exit: {exit_price:.6f}, Profit: {profit:.2f}, Balance: {self.balance:.2f}")
        self.position_type = None
        self.position_qty = 0.0
        self.last_trade_time = now
        self.sl_price = None
        self.tp_price = None
        self.best_price_since_entry = None
        print(f"[SUCCESS] Position fully cleared. Ready for next signal.", file=sys.stderr)

    async def cover(self, price):
        """Closes a SHORT position and sweeps up any remaining dust."""
        now = datetime.now(timezone.utc)
        time_diff = now - self.last_trade_time
        time_diff_min = time_diff.total_seconds() / 60
        
        print(f"[DEBUG] COVER attempt (short close): Price {price:.6f}, Time diff {time_diff_min:.1f} min", file=sys.stderr)
        logging.info(f"COVER check: Time diff {time_diff_min:.1f} min, Position: {self.position_type}")

        if self.position_type != 'short':
            print(f"[WARNING] COVER blocked: No short position active ({self.position_type})", file=sys.stderr)
            return

        # --- Position Closure Logic ---
        quantity = self.position_qty
        fee = 0.00075
        exit_price = price * (1 + fee)
        profit = (self.entry_price - exit_price) * self.leverage * (quantity * self.entry_price / self.balance)
        self.balance += profit

        print(f"[ORDER ATTEMPT] COVER SHORT CLOSE | {self.symbol}, Qty: {quantity}, Exit: {exit_price:.6f}, Profit: {profit:.2f}", file=sys.stderr)
        
        # 1. Execute the main close order
        await self.binance_client.buy(self.symbol, quantity)
        
        # 2. TRIGGER AUTOMATIC DUST CLEANUP
        print(f"[INFO] Main position closed. Starting dust cleanup in 2 seconds...", file=sys.stderr)
        await asyncio.sleep(2) 
        await self.clean_leftover_position()

        # 3. Reset bot state for the next signal
        logging.info(f"COVER SHORT: Exit: {exit_price:.6f}, Profit: {profit:.2f}, Balance: {self.balance:.2f}")
        self.position_type = None
        self.position_qty = 0.0
        self.last_trade_time = now
        self.sl_price = None
        self.tp_price = None
        self.best_price_since_entry = None
        print(f"[SUCCESS] Position fully cleared. Ready for next signal.", file=sys.stderr)

    async def clean_leftover_position(self, min_amount=0.0001):
        """Automatically closes small remaining quantities after position closure."""
        try:
            positions = await self.binance_client.get_positions()
            for position in positions:
                if position['symbol'] == self.symbol:
                    amt = float(position['positionAmt'])
                    if abs(amt) > 0 and abs(amt) < min_amount:
                        qty = abs(amt)
                        side = 'BUY' if amt < 0 else 'SELL'
                        logging.info(f"Small leftover position detected: {amt}. Closing...")
                        print(f"[DEBUG] Cleaning leftover: {amt} -> {side} {qty}", file=sys.stderr)
                        
                        if side == 'BUY':
                            await self.binance_client.buy(self.symbol, qty)
                        else:
                            await self.binance_client.sell(self.symbol, qty)
                        
                        logging.info(f"Small position ({amt}) successfully closed.")
        except Exception as e:
            logging.error(f"Error during leftover cleanup: {e}")
        

async def kline_listener(client, symbol, source, df, doc, price_plot, bot):
    bm = BinanceSocketManager(client)
    reconnect_attempts = 0

    while reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            async with bm.kline_socket(symbol=symbol, interval='15m') as stream:
                while True:
                    res = await stream.recv()
                    if res and 'k' in res:
                        kline = res['k']
                        if kline['x']:  # If kline is closed (log and process only here)
                            print(f"[DEBUG] New candle closed: {pd.to_datetime(kline['t'], unit='ms', utc=True)}", file=sys.stderr)
                            new_data = {
                                'timestamp': datetime.fromtimestamp(kline['t'] / 1000, tz=timezone.utc).astimezone(df['timestamp'].dt.tz),
                                'open': float(kline['o']),
                                'high': float(kline['h']),
                                'low': float(kline['l']),
                                'close': float(kline['c']),
                                'volume': float(kline['v']),
                            }
                            new_df = pd.DataFrame([new_data])
                            df = pd.concat([df, new_df], ignore_index=True)
                            df = df.drop_duplicates(subset='timestamp')
                            df = df.sort_values(by='timestamp')

                            # Fill gaps and update indicators/signals
                            df = check_and_fill_gaps(df)
                            df = calculate_technical_indicators(df)  # Calculate updated indicators
                            df = generate_trade_signals(df, print_details=True)  # Real-time: show details every 15m

                            # Latest ATR (14) — Required for ATR-based 1:8 SL/TP
                            latest_atr = float(df['ATR'].iloc[-1])
                            current_price = df['close'].iloc[-1]

                            # Update trailing stop on every candle close (if position exists)
                            if bot.position_type is not None:
                                await bot.update_trailing_stop(current_price)

                            # Chart stream data
                            stream_data = {
                                'timestamp': [new_data['timestamp']],
                                'open': [new_data['open']],
                                'high': [new_data['high']],
                                'low': [new_data['low']],
                                'close': [new_data['close']],
                                'volume': [new_data['volume']],
                                'color': [determine_candle_color(new_data['open'], new_data['close'])],
                                'RSI': [df['RSI'].iloc[-1]],
                                'Buy': [df['Buy'].iloc[-1]],
                                'Sell': [df['Sell'].iloc[-1]],
                                'ATR': [df['ATR'].iloc[-1]],
                                'EMA_10': [df['EMA_10'].iloc[-1]],
                                'EMA_5': [df['EMA_5'].iloc[-1]],
                                'OBV': [df['OBV'].iloc[-1]],
                                'OBV_diff': [df['OBV_diff'].iloc[-1]],
                                'macdA_macd': [df['macdA_macd'].iloc[-1]],
                                'macdA_signal': [df['macdA_signal'].iloc[-1]],
                                'macdA_hist': [df['macdA_hist'].iloc[-1]],
                                'macdB_macd': [df['macdB_macd'].iloc[-1]],
                                'macdB_signal': [df['macdB_signal'].iloc[-1]],
                                'macdB_hist': [df['macdB_hist'].iloc[-1]],
                                'stochrsi_d': [df['stochrsi_d'].iloc[-1]],
                                'stochrsi_k': [df['stochrsi_k'].iloc[-1]],
                                'ADX': [df['ADX'].iloc[-1]],
                                'Bollinger_lower': [df['Bollinger_lower'].iloc[-1]],
                                'Bollinger_middle': [df['Bollinger_middle'].iloc[-1]],
                                'Bollinger_upper': [df['Bollinger_upper'].iloc[-1]],
                                'index': [df.index[-1]]
                            }

                            # Decision logic (TP/SL handled in trailing, close on reverse signals)
                            if bot.position_type is None:
                                if df['Buy'].iloc[-1]:
                                    print(f"[SIGNAL TRIGGERED] BUY! Close: {df['close'].iloc[-1]:.6f}, RSI: {df['RSI'].iloc[-1]:.2f}", file=sys.stderr)
                                    logging.info(f"Buy signal detected. Price: {df['close'].iloc[-1]}")
                                    await bot.buy(df['close'].iloc[-1], latest_atr=latest_atr)
                                elif df['Sell'].iloc[-1]:
                                    print(f"[SIGNAL TRIGGERED] SELL! Close: {df['close'].iloc[-1]:.6f}, RSI: {df['RSI'].iloc[-1]:.2f}", file=sys.stderr)
                                    logging.info(f"Sell signal detected. Price: {df['close'].iloc[-1]}")
                                    await bot.short(df['close'].iloc[-1], latest_atr=latest_atr)
                                else:
                                    print(f"[DEBUG] No signal: Buy={df['Buy'].iloc[-1]}, Sell={df['Sell'].iloc[-1]}", file=sys.stderr)

                            elif bot.position_type == 'long':
                                if df['Sell'].iloc[-1]:
                                    reason = "Sell Signal"
                                    print(f"[POSITION CLOSE TRIGGERED] Long SELL ({reason})! Close: {df['close'].iloc[-1]:.6f}", file=sys.stderr)
                                    logging.info(f"Long position close triggered. Price: {df['close'].iloc[-1]}, Reason: {reason}")
                                    await bot.sell(df['close'].iloc[-1])
                                else:
                                    print(f"[DEBUG] Long position continuing: Close {df['close'].iloc[-1]:.6f} (TP: {bot.tp_price:.6f}, SL: {bot.sl_price:.6f})", file=sys.stderr)

                            elif bot.position_type == 'short':
                                if df['Buy'].iloc[-1]:
                                    reason = "Buy Signal"
                                    print(f"[POSITION CLOSE TRIGGERED] Short COVER ({reason})! Close: {df['close'].iloc[-1]:.6f}", file=sys.stderr)
                                    logging.info(f"Short position close triggered. Price: {df['close'].iloc[-1]}, Reason: {reason}")
                                    await bot.cover(df['close'].iloc[-1])
                                else:
                                    print(f"[DEBUG] Short position continuing: Close {df['close'].iloc[-1]:.6f} (TP: {bot.tp_price:.6f}, SL: {bot.sl_price:.6f})", file=sys.stderr)

                            def update():
                                source.stream(stream_data, rollover=500)
                                add_signal_labels(price_plot, source)

                            doc.add_next_tick_callback(update)
                        else:
                            # Partial candle: NO LOG - stay silent (per-second spam completely removed)
                            pass
                    else:
                        logging.warning(f"Unexpected message format for {symbol}: {res}")
        except Exception as e:
            logging.error(f"Error in kline_listener for {symbol}: {e}", exc_info=True)
            print(f"[ERROR] Kline listener ({symbol}): {e}", file=sys.stderr)
            reconnect_attempts += 1
            logging.info(f"Reconnecting {symbol}... Attempt {reconnect_attempts}")
            await asyncio.sleep(RECONNECT_WAIT_TIME)

    logging.error(f"Max reconnect attempts reached for {symbol}. Exiting...")
    await client.close_connection()



async def setup_symbol(client, symbol, doc, binance_client):
    """Setup for a single symbol"""
    df = await fetch_initial_klines(client, symbol, interval='15m', limit=500)
    source = ColumnDataSource(df)

    price_plot = figure(x_axis_type="datetime", title=f"{symbol} Live Price Chart", sizing_mode="stretch_width", height=400)
    price_plot.vbar(x='timestamp', top='close', bottom='open', width=0.7*15*60*1000, source=source, color='color')  # 15m width in ms
    price_plot.xaxis.formatter = DatetimeTickFormatter(
        hours="%H:%M",
        days="%d %b",
        months="%d %b",
        years="%d %b %Y"
    )
    add_signal_labels(price_plot, source)

    symbol_info = await binance_client.get_symbol_info(symbol)
    precision = 3  # Default precision
    if symbol_info:
        for filt in symbol_info['filters']:
            if filt['filterType'] == 'LOT_SIZE':
                step_size = filt['stepSize']
                if '.' in step_size:
                    precision = len(step_size.rstrip('0').split('.')[1])
                else:
                    precision = 0  # For integers (like DOGEUSDT)
                break
    print(f"[DEBUG] {symbol} precision: {precision}", file=sys.stderr)

    bot = TradingBot(binance_client=binance_client, symbol=symbol, precision=precision)
    await bot.initialize(df)  # Pass df: Calculate ATR with current data

    asyncio.create_task(kline_listener(client, symbol, source, df, doc, price_plot, bot))

    return price_plot


async def main(doc):
    """Main function for the Bokeh server."""
    try:
        print("[DEBUG] Main start", file=sys.stderr)
        binance_client = BinanceClient(api_key, api_secret)
        await binance_client.create()

        client = await AsyncClient.create(api_key, api_secret)
        symbols = ['DOGEUSDT']  # Support for multiple symbols added

        plots = await asyncio.gather(*[setup_symbol(client, symbol, doc, binance_client) for symbol in symbols])

        def add_layout():
            for plot in plots:
                doc.add_root(plot)

        doc.add_next_tick_callback(add_layout)
        print("[DEBUG] Main done, waiting for candle close...", file=sys.stderr)
    except Exception as e:
        logging.error(f"Error in main: {e}", exc_info=True)
        print(f"[ERROR] Main: {e}", file=sys.stderr)


def modify_doc(doc):
    asyncio.create_task(main(doc))


if __name__ == '__main__':
    handler = FunctionHandler(modify_doc)
    app = Application(handler)
    server = Server({'/': app}, num_procs=1)  # Corrected: {'/': app}
    server.run_until_shutdown()
else:
    asyncio.create_task(main(curdoc()))