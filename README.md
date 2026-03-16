# 📈 Professional Crypto Trading Bot & Analytics Suite (Golden Standard)

This repository contains a high-performance, modular, and symmetrical trading infrastructure specifically designed for **Binance Futures**. It integrates automated data collection, professional indicator processing, a robust backtesting engine, and a live trading bot with real-time visualization.

---

## 🏗️ Project Architecture

The project is structured with high symmetry to ensure scalability and ease of maintenance. Every file is organized to work in harmony with the shared `data/` folder.

```
C:...
│   config.py               # API Configuration (keep it secret!)
│   requirements.txt        # Python dependencies (categorized)
│   README.md               # You are here!
│
├── data                    # Raw and processed (indicator) CSV files
├── src
│   │   backtest.py         # Strategy testing engine (dynamic paths)
│   │   finally.py          # Live trading bot & Bokeh dashboard
│   │
│   ├── data_fetchers       # Binance historical data collection
│   └── indicators          # "Golden Standard" indicator calculators
└── notebooks               # Research, development, and analysis lab
```
---

## 🚀 Getting Started

### 1. Prerequisites

Python: 3.9+ (Tested and verified on 3.9)

TA-Lib: This project uses the TA-Lib C++ library for all technical indicator calculations.

Recommended Setup (Conda): To avoid installation issues on Windows and match the developer's environment:

```conda create -n trading_bot python=3.9```
```conda activate trading_bot```
```conda install conda-forge::ta-lib==0.4.32```

### 2. Installation
Install all dependencies with a single command: ``` pip install -r requirements.txt ```

### 3. API Configuration
Open ``` config.py ``` and input your credentials: api_key = "YOUR_BINANCE_API_KEY"  api_secret = "YOUR_BINANCE_API_SECRET"
⚠️ Security Notice: Never share these keys or commit this file to public repositories!

## 🛠️ Operational Workflow

### Phase 1: Data Preparation
First, fetch historical data and then process indicators to populate the data/ folder.

-- Fetch Data: python ``` src/data_fetchers/dogedata15m.py ```
-- Calculate Indicators: ``` python src/indicators/dogecalculate15m.py ```

### Phase 2: Backtesting
Verify your strategy logic against historical data before risking capital: ``` python src/backtest.py ```

⚠️ IMPORTANT NOTE: The provided backtest script is pre-configured specifically for the DOGE/USDT 15m timeframe with specific indicator optimizations.
If you plan to trade other coins (BTC, ETH, etc.) or use different timeframes (15m, 1h, 4h, 1d etc.), you must perform your own optimization.
The ``` finally.py ``` script has been fine-tuned based on these 15-minute DOGE results. Trading other assets without re-optimizing parameters is highly risky. 
Please take this into account for your own safety.

### Phase 3: Live Trading
Start the live bot and visual dashboard: ``` python src/finally.py ```

## 📊 Technical Highlights
Code Symmetry: All indicator scripts across timeframes (15m, 1h, 4h, 1d) share identical logic and output formats.

ATR-Based Risk Management: Dynamic SL/TP calculation (1.5x ATR for SL, 7.0x ATR for TP) adapted to current market volatility.

Automatic Dust Cleanup: Built-in logic to clear small leftover "dust" positions on Binance after closing trades.

Advanced Cooldown: Enforces a 150-minute minimum interval between trades to prevent overtrading.

Real-time Monitoring: Live dashboard tracking RSI, MACD A/B, Bollinger Bands, and real-time execution signals.

## ⚠️ Important Considerations
Timezone Synchronization: The core logic operates on UTC. While the dashboard can display local time (e.g., Europe/Dublin), ensure your system clock is accurate for precise cooldown and signal management.

Memory Optimization: The live bot is designed to handle streaming data efficiently without memory leaks during long-running sessions.

**Disclaimer:** This software is for educational and research purposes only. Trading involves significant risk of loss. The author is not responsible for any financial losses. 

**NOT FINANCIAL ADVICE (NFA):** Everything provided in this repository is for informational purposes. This is not investment advice. Please do your own research (DYOR) before trading.
   
