import time
import requests
import pandas as pd
import numpy as np
import streamlit as st

# Streamlit Page Setup
st.set_page_config(
    page_title="Adaptive Kinetic Ribbon Web Screener",
    page_icon="⚡",
    layout="wide"
)

# Fetch Binance Futures OHLCV via direct public REST endpoints
def fetch_binance_klines(symbol, timeframe='1h', limit=100):
    symbol_formatted = symbol.replace('/', '').replace(':USDT', '')
    
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol_formatted}&interval={timeframe}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={symbol_formatted}&interval={timeframe}&limit={limit}",
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol_formatted}&interval={timeframe}&limit={limit}"
    ]

    for url in endpoints:
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                data = res.json()
                if len(data) < 30:  # Must have at least enough data to clear indicator lag
                    continue
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', '_1', '_2', '_3', '_4', '_5', '_6'])
                df['close'] = df['close'].astype(float)
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                return df
        except Exception:
            continue
    return None

@st.cache_data(ttl=3600)
def fetch_top_usdt_pairs(limit=100):
    endpoints = [
        "https://data-api.binance.vision/api/v3/ticker/24hr",
        "https://api.binance.com/api/v3/ticker/24hr",
        "https://fapi.binance.com/fapi/v1/ticker/24hr"
    ]
    
    for url in endpoints:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                sorted_data = sorted(data, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
                symbols = [
                    item['symbol'] for item in sorted_data 
                    if item['symbol'].endswith('USDT') 
                    and not item['symbol'].startswith('USDC')
                    and not item['symbol'].startswith('FDUSD')
                ]
                if len(symbols) >= limit:
                    return symbols[:limit]
        except Exception:
            continue

    fallback_100 = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'NEARUSDT', 'LINKUSDT',
        'SUIUSDT', 'PEPEUSDT', 'SHIBUSDT', 'APTUSDT', 'TAOUSDT', 'DOTUSDT', 'LTCUSDT', 'BCHUSDT', 'UNIUSDT',
        'ICPUSDT', 'FETUSDT', 'RENDERUSDT', 'BONKUSDT', 'FLOKIUSDT', 'WIFUSDT', 'INJUSDT', 'TIAUSDT', 'STXUSDT', 'SEIUSDT',
        'OPUSDT', 'ARBUSDT', 'FILUSDT', 'TRXUSDT', 'ETCUSDT', 'XLMUSDT', 'RUNEUSDT', 'GALAUSDT', 'AAVEUSDT', 'LDOUSDT',
        'ORDIUSDT', 'ARKMUSDT', 'ONDOUSDT', 'JUPUSDT', 'ENAUSDT', 'BEAMUSDT', 'NOTUSDT', 'TONUSDT', '1000SATSUSDT',
        'CRVUSDT', 'MKRUSDT', 'DYDXUSDT', 'COMPUSDT', 'SNXUSDT', 'EGLDUSDT', 'THETAUSDT', 'AXSUSDT', 'SANDUSDT', 'MANAUSDT',
        'EOSUSDT', 'FTMUSDT', 'FLOWUSDT', 'NEOUSDT', 'KAVAUSDT', 'ALGOUSDT', 'CHZUSDT', 'IOTAUSDT', 'ZECUSDT', 'DASHUSDT',
        'XTZUSDT', 'MINAUSDT', 'HOTUSDT', 'CAKEUSDT', 'WOOUSDT', 'JTOUSDT', 'PYTHUSDT', 'STRKUSDT', 'MANTAUSDT',
        'ALTUSDT', 'DYMUSDT', 'PIXELUSDT', 'PORTALUSDT', 'AEVOUSDT', 'ETHFIUSDT', 'BOMEUSDT', 'WUSDT', 'TNSRUSDT', 'SAFEUSDT',
        'BBUSDT', 'IOUSDT', 'ZKUSDT', 'LISTAUSDT', 'ZROUSDT', 'BLASTUSDT', 'LITUSDT', 'RVNUSDT', 'VENTUSDT'
    ]
    return fallback_100[:limit]

def calculate_ma(series, length, ma_type='EMA'):
    if ma_type == 'SMA':
        return series.rolling(window=length).mean()
    return series.ewm(span=length, adjust=False).mean()

# Pine Script Indicator Logic
def compute_kinetic_ribbon(df, length=20, mult=1.5, ma_type='EMA', fast_len=3, slow_len=8):
    source = df['close']
    velocity = source - source.shift(length)
    volatility = (source - source.shift(1)).rolling(window=length).std(ddof=0) * mult

    denom = velocity.abs() + volatility
    adaptive_alpha = np.where(denom == 0, 0, velocity.abs() / denom)

    kinetic_line = np.zeros(len(df))
    kinetic_line[0] = source.iloc[0]

    for i in range(1, len(df)):
        if np.isnan(kinetic_line[i-1]):
            kinetic_line[i] = source.iloc[i]
        else:
            kinetic_line[i] = kinetic_line[i-1] + adaptive_alpha[i] * (source.iloc[i] - kinetic_line[i-1])

    df['kinetic_line'] = kinetic_line
    df['ribbon_fast'] = calculate_ma(df['kinetic_line'], fast_len, ma_type)
    df['ribbon_slow'] = calculate_ma(df['kinetic_line'], slow_len, ma_type)

    df['ribbon_gap_pct'] = ((df['ribbon_fast'] - df['ribbon_slow']) / df['close']) * 100
    df['ribbon_gap_change'] = df['ribbon_gap_pct'] - df['ribbon_gap_pct'].shift(1)

    df['trend_up'] = df['ribbon_fast'] > df['ribbon_slow']
    df['acceleration'] = df['ribbon_fast'] > df['ribbon_fast'].shift(1)

    df['bull_cross'] = df['trend_up'] & (~df['trend_up'].shift(1))
    df['bear_cross'] = (~df['trend_up']) & df['trend_up'].shift(1)
    df['bull_accel_trigger'] = (df['trend_up'] & df['acceleration']) & (~(df['trend_up'].shift(1) & df['acceleration'].shift(1)))
    
    # CORRECTED BEAR ACCELERATION LOGIC
    df['bear_accel_trigger'] = ((~df['trend_up']) & (~df['acceleration'])) & (~((~df['trend_up'].shift(1)) & (~df['acceleration'].shift(1))))

    # Clean up NaN warm-up rows safely
    df = df.dropna().reset_index(drop=True)
    return df

# Scanner Engine
def scan_markets(max_coins=100, gap_threshold=2.5):
    timeframes = ['1h', '4h', '1d']
    results = {
        "approaching_bullish": [],
        "approaching_bearish": [],
        "active_triggers": []
    }

    symbols = fetch_top_usdt_pairs(limit=max_coins)
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, symbol in enumerate(symbols):
        pair_name = symbol.replace('USDT', '')
        status_text.text(f"Scanning Binance Pairs ({idx+1}/{len(symbols)}): #{pair_name}")
        progress_bar.progress((idx + 1) / len(symbols))

        for tf in timeframes:
            try:
                df = fetch_binance_klines(symbol, timeframe=tf, limit=100)
                if df is None or df.empty:
                    continue
                
                df = compute_kinetic_ribbon(df)
                if df.empty:
                    continue

                last_bar = df.iloc[-1]
                price = last_bar['close']
                gap = last_bar['ribbon_gap_pct']
                gap_change = last_bar['ribbon_gap_change']

                if np.isnan(gap) or np.isnan(gap_change):
                    continue

                # 1. Active Triggers
                if last_bar['bull_cross']:
                    results["active_triggers"].append({
                        "Coin": pair_name, "TF": tf, "Trigger": "🚀 Bullish Crossover",
                        "Price": f"${price:,.4f}", "Ribbon Gap": f"{gap:.2f}%"
                    })
                elif last_bar['bear_cross']:
                    results["active_triggers"].append({
                        "Coin": pair_name, "TF": tf, "Trigger": "🔻 Bearish Crossover",
                        "Price": f"${price:,.4f}", "Ribbon Gap": f"{gap:.2f}%"
                    })
                elif last_bar['bull_accel_trigger']:
                    results["active_triggers"].append({
                        "Coin": pair_name, "TF": tf, "Trigger": "⚡ Bullish Acceleration",
                        "Price": f"${price:,.4f}", "Ribbon Gap": f"{gap:.2f}%"
                    })
                elif last_bar['bear_accel_trigger']:
                    results["active_triggers"].append({
                        "Coin": pair_name, "TF": tf, "Trigger": "⚡ Bearish Acceleration",
                        "Price": f"${price:,.4f}", "Ribbon Gap": f"{gap:.2f}%"
                    })

                # 2. Approaching Bullish
                elif gap < 0 and abs(gap) <= gap_threshold and gap_change > 0:
                    results["approaching_bullish"].append({
                        "Coin": pair_name, "TF": tf, "Price": f"${price:,.4f}",
                        "Distance to Ribbon": f"{abs(gap):.2f}%", "Kinetic Status": "Closing In Upward ⬆️"
                    })

                # 3. Approaching Bearish
                elif gap > 0 and abs(gap) <= gap_threshold and gap_change < 0:
                    results["approaching_bearish"].append({
                        "Coin": pair_name, "TF": tf, "Price": f"${price:,.4f}",
                        "Distance to Ribbon": f"{gap:.2f}%", "Kinetic Status": "Closing In Downward ⬇️"
                    })

            except Exception:
                continue

    status_text.success("Scan completed successfully!")
    progress_bar.empty()
    return results

# Frontend UI
st.title("⚡ Adaptive Kinetic Ribbon Web Screener")
st.caption("Real-time multi-timeframe scanner powered by Pine Script dynamic velocity/volatility ribbon math.")

col1, col2 = st.columns([1, 3])
with col1:
    coin_limit = st.slider("Top Volume Pairs to Scan", 10, 100, 50, step=10)
    threshold = st.slider("Approaching Gap Threshold (%)", 0.5, 5.0, 2.5, step=0.1)
    start_button = st.button("🚀 Start Scanner", use_container_width=True)

if start_button:
    with st.spinner("Executing ribbon algorithms..."):
        scan_data = scan_markets(max_coins=coin_limit, gap_threshold=threshold)

    if scan_data:
        st.markdown("---")

        st.subheader("🟢 1. Approaching Bullish Crossover & Acceleration (1h, 4h, 1d)")
        if scan_data["approaching_bullish"]:
            st.dataframe(pd.DataFrame(scan_data["approaching_bullish"]), use_container_width=True)
        else:
            st.info(f"No coins currently approaching a bullish crossover within the {threshold}% threshold.")

        st.subheader("🔴 2. Approaching Bearish Crossover & Acceleration (1h, 4h, 1d)")
        if scan_data["approaching_bearish"]:
            st.dataframe(pd.DataFrame(scan_data["approaching_bearish"]), use_container_width=True)
        else:
            st.info(f"No coins currently approaching a bearish crossover within the {threshold}% threshold.")

        st.subheader("⚡ 3. Active Triggers (Fired on Current Candle)")
        if scan_data["active_triggers"]:
            st.dataframe(pd.DataFrame(scan_data["active_triggers"]), use_container_width=True)
        else:
            st.info("No active crossover or acceleration triggers on current candle bars.")
