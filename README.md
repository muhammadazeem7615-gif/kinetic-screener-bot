# 🚀 Crypto Futures Screener - Adaptive Kinetic Ribbon

Real-time signal detector for crypto futures trading using the Adaptive Kinetic Ribbon indicator from TradingView.

## Overview

This Streamlit app scans **all** Binance crypto futures pairs for entry signals based on your custom Adaptive Kinetic Ribbon indicator. Detects:

- **Bullish/Bearish Crossovers** — Ribbon fast crosses slow ribbon
- **Bullish/Bearish Acceleration** — Momentum building in trend direction
- **Bullish/Bearish Deceleration** — Momentum weakening (potential reversals)

## Features

✅ Scans 10-200+ crypto futures pairs in real-time  
✅ Monitors 4 timeframes: 15m, 2h, 4h, 1d  
✅ Indicator parameters matched to your TradingView settings (length=20, mult=1.5, fast/slow=3/8)  
✅ Filter signals by type and timeframe  
✅ Export signals to CSV  
✅ Clean, responsive Streamlit UI  
✅ Uses **free Binance API** — no subscription needed  

## Installation

### Local Setup

```bash
# Clone repo
git clone https://github.com/yourusername/kinetic-screener-bot.git
cd kinetic-screener-bot

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Opens at: `http://localhost:8501`

### Deploy to Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app"
4. Select your repo, branch, and `app.py`
5. Deploy!

### Deploy to Other Platforms

Works on any platform that supports Python + Streamlit:
- Railway
- Heroku
- AWS
- Digital Ocean
- Self-hosted VPS

## Usage

### Step 1: Configure
- Set number of coins to scan (10-200)
- Select timeframes (15m/2h/4h/1d)
- Choose signal filters

### Step 2: Scan
- Click **"Scan Now"** button
- Progress bar shows scan status
- Results appear in table

### Step 3: Monitor & Trade
- View signals sorted by most recent first
- Filter by signal type (Crossovers, Acceleration, etc.)
- Export to CSV for further analysis
- Follow signals in your trading platform

## Indicator Logic

The indicator recreates your Pine Script logic:

```
1. Calculate velocity: change over lookback period
2. Calculate volatility: stdev of price changes
3. Adaptive alpha: velocity / (velocity + volatility)
4. Kinetic line: exponential smoothing with adaptive alpha
5. Ribbon fast/slow: moving averages of kinetic line
6. Detect: crossovers, acceleration/deceleration states
```

**Parameters (matching your defaults):**
- Lookback period: 20
- Volatility multiplier: 1.5
- Fast ribbon: 3
- Slow ribbon: 8

## Data Source

Uses **Binance Futures API**:
- Free, no API key needed
- Covers 500+ trading pairs
- Real-time OHLCV data
- Rate limited to ~1200 req/min

## Troubleshooting

### No signals found
- Try more coins (increase slider)
- Try different timeframes
- Wait for market volatility

### Slow performance
- Reduce number of coins scanned
- Reduce number of timeframes
- Run during off-peak hours

### API errors
- Check internet connection
- Binance API may be temporarily down
- Try again in a few minutes

## Configuration

Edit `app.py` to customize:

```python
# Change default coins to scan
num_coins = st.slider("Number of coins to scan", 10, 200, 100, step=10)

# Change default timeframes
selected_timeframes = st.multiselect(
    "Timeframes to scan",
    options=[t[1] for t in timeframes],
    default=['2h', '4h', '1d']  # Edit this
)

# Change indicator parameters
indicator = AdaptiveKineticRibbon(
    length=20,      # Lookback period
    mult=1.5,       # Volatility sensitivity
    fast_period=3,  # Fast ribbon
    slow_period=8   # Slow ribbon
)
```

## Disclaimer

This tool is for **educational purposes only**. Not financial advice. Always verify signals against your own analysis before trading. Past performance ≠ future results. Trade at your own risk.

## License

MIT

## Support

Questions or issues? Open a GitHub issue or contact the maintainer.

---

**Made with ❤️ for crypto traders**
