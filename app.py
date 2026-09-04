import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import numpy as np
from typing import List, Optional, Tuple

# Page config
st.set_page_config(
    page_title="Crypto Futures Screener",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1f3a 0%, #0f1329 100%);
        padding: 20px;
        border-radius: 8px;
        border-left: 3px solid #00ffaa;
        color: white;
    }
    .bull-signal {
        color: #00ffaa;
        font-weight: bold;
    }
    .bear-signal {
        color: #ff4444;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ============ INDICATOR CALCULATIONS ============
class AdaptiveKineticRibbon:
    def __init__(self, length=20, mult=1.5, fast_period=3, slow_period=8):
        self.length = length
        self.mult = mult
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def calculate(self, closes: np.ndarray) -> Optional[dict]:
        """Calculate indicator values from close prices"""
        if len(closes) < self.length + 2:
            return None
        
        closes = np.array(closes, dtype=float)
        n = len(closes)
        
        # Velocity: change over lookback period
        velocity = closes[-1] - closes[-self.length]
        
        # Volatility: standard deviation of price changes * multiplier
        price_changes = np.diff(closes[-self.length:])
        volatility = np.std(price_changes) * self.mult
        
        # Adaptive alpha
        denominator = abs(velocity) + volatility + 1e-10
        adaptive_alpha = abs(velocity) / denominator
        
        # Kinetic line: exponential smoothing with adaptive alpha
        kinetic_line = closes[-self.length]
        for i in range(-self.length + 1, 0):
            kinetic_line = kinetic_line + adaptive_alpha * (closes[i] - kinetic_line)
        
        # Ribbon bands using SMA of recent closes as proxy
        recent = closes[-(self.slow_period + 5):]
        ribbon_fast = np.mean(recent[-self.fast_period:])
        ribbon_slow = np.mean(recent[-self.slow_period:])
        
        return {
            'kinetic_line': float(kinetic_line),
            'ribbon_fast': float(ribbon_fast),
            'ribbon_slow': float(ribbon_slow),
            'velocity': float(velocity),
            'volatility': float(volatility),
            'adaptive_alpha': float(adaptive_alpha)
        }


def detect_signals(closes_history: List[float], indicator: AdaptiveKineticRibbon) -> List[str]:
    """Detect signals from closes history"""
    if len(closes_history) < indicator.length + 2:
        return []
    
    current = indicator.calculate(closes_history)
    if not current:
        return []
    
    previous = indicator.calculate(closes_history[:-1])
    if not previous:
        return []
    
    signals = []
    
    # Trend states
    trend_up = current['ribbon_fast'] > current['ribbon_slow']
    trend_up_prev = previous['ribbon_fast'] > previous['ribbon_slow']
    
    # Acceleration states
    accelerating = current['ribbon_fast'] > previous['ribbon_fast']
    accelerating_prev = previous['ribbon_fast'] > (closes_history[-3] if len(closes_history) > 3 else closes_history[-2])
    
    # Crossovers
    if not trend_up_prev and trend_up:
        signals.append('Bullish Crossover')
    if trend_up_prev and not trend_up:
        signals.append('Bearish Crossover')
    
    # Acceleration/Deceleration entries
    if trend_up and accelerating and not (trend_up_prev and accelerating_prev):
        signals.append('Bullish Acceleration')
    if trend_up and not accelerating and not (trend_up_prev and not accelerating_prev):
        signals.append('Bullish Deceleration')
    if not trend_up and not accelerating and not (trend_up_prev and not accelerating_prev):
        signals.append('Bearish Acceleration')
    if not trend_up and accelerating and not (trend_up_prev and accelerating_prev):
        signals.append('Bearish Deceleration')
    
    return signals


def get_futures_symbols(limit=100) -> List[str]:
    """Fetch tradeable futures symbols from Binance"""
    try:
        response = requests.get('https://fapi.binance.com/fapi/v1/exchangeInfo', timeout=5)
        if response.status_code == 200:
            data = response.json()
            symbols = [
                s['symbol'] for s in data['symbols']
                if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT'
            ]
            return symbols[:limit]
    except Exception as e:
        st.warning(f"Error fetching symbols: {e}")
    return []


def fetch_klines(symbol: str, interval: str, limit: int = 30) -> Optional[List]:
    """Fetch klines from Binance"""
    try:
        url = f'https://fapi.binance.com/fapi/v1/klines'
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None


def scan_signals(symbols: List[str], timeframes: List[Tuple[str, str]]) -> List[dict]:
    """Scan all symbols for signals"""
    indicator = AdaptiveKineticRibbon(length=20, mult=1.5, fast_period=3, slow_period=8)
    all_signals = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(symbols) * len(timeframes)
    current = 0
    
    for symbol in symbols:
        for tf_name, tf_display in timeframes:
            current += 1
            progress_bar.progress(current / total)
            status_text.text(f"Scanning {symbol} {tf_display}... ({current}/{total})")
            
            klines = fetch_klines(symbol, tf_name)
            if not klines or len(klines) < 2:
                continue
            
            closes = [float(k[4]) for k in klines]
            signals = detect_signals(closes, indicator)
            
            if signals:
                for signal in signals:
                    all_signals.append({
                        'Coin': symbol.replace('USDT', ''),
                        'Signal': signal,
                        'Timeframe': tf_display,
                        'Price': f"${closes[-1]:.2f}",
                        'Time': datetime.now().strftime('%H:%M:%S')
                    })
            
            time.sleep(0.1)  # Rate limit
    
    progress_bar.empty()
    status_text.empty()
    
    return all_signals


# ============ STREAMLIT UI ============

# Initialize session state
if 'signals' not in st.session_state:
    st.session_state.signals = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'scanning' not in st.session_state:
    st.session_state.scanning = False

# Header
st.title("🚀 Crypto Futures Screener")
st.markdown("Adaptive Kinetic Ribbon Signal Detector | Real-time Entry Signals")

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Settings")
    
    num_coins = st.slider("Number of coins to scan", 10, 200, 100, step=10)
    
    timeframes = [
        ('15m', '15m'),
        ('2h', '2h'),
        ('4h', '4h'),
        ('1d', '1d')
    ]
    
    selected_timeframes = st.multiselect(
        "Timeframes to scan",
        options=[t[1] for t in timeframes],
        default=['2h', '4h', '1d']
    )
    
    selected_timeframes = [(t[0], t[1]) for t in timeframes if t[1] in selected_timeframes]
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 Scan Now", use_container_width=True, key="scan_button"):
            st.session_state.scanning = True
    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=False)
    
    if st.session_state.last_update:
        st.caption(f"Last update: {st.session_state.last_update.strftime('%H:%M:%S')}")

# Main content
if st.session_state.scanning:
    st.info("Fetching futures symbols...")
    symbols = get_futures_symbols(num_coins)
    
    if symbols:
        st.session_state.signals = scan_signals(symbols, selected_timeframes)
        st.session_state.last_update = datetime.now()
        st.session_state.scanning = False
        st.rerun()

# Display metrics
if st.session_state.signals:
    df_signals = pd.DataFrame(st.session_state.signals)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Signals", len(df_signals))
    with col2:
        bull_count = len(df_signals[df_signals['Signal'].str.contains('Bullish')])
        st.metric("Bullish", bull_count, delta="signals")
    with col3:
        bear_count = len(df_signals[df_signals['Signal'].str.contains('Bearish')])
        st.metric("Bearish", bear_count, delta="signals")
    with col4:
        if st.session_state.last_update:
            st.metric("Last Scan", st.session_state.last_update.strftime('%H:%M:%S'))
    
    st.divider()
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        filter_signal = st.multiselect(
            "Filter by Signal Type",
            options=df_signals['Signal'].unique(),
            default=df_signals['Signal'].unique(),
            key="signal_filter"
        )
    with col2:
        filter_timeframe = st.multiselect(
            "Filter by Timeframe",
            options=df_signals['Timeframe'].unique(),
            default=df_signals['Timeframe'].unique(),
            key="timeframe_filter"
        )
    
    # Apply filters
    df_filtered = df_signals[
        (df_signals['Signal'].isin(filter_signal)) &
        (df_signals['Timeframe'].isin(filter_timeframe))
    ]
    
    # Display table with color coding
    if len(df_filtered) > 0:
        st.subheader(f"Signals ({len(df_filtered)})")
        
        # Display as interactive table
        st.dataframe(
            df_filtered,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Coin': st.column_config.TextColumn("Coin", width="small"),
                'Signal': st.column_config.TextColumn("Signal", width="medium"),
                'Timeframe': st.column_config.TextColumn("Timeframe", width="small"),
                'Price': st.column_config.TextColumn("Price", width="small"),
                'Time': st.column_config.TextColumn("Time", width="small"),
            }
        )
        
        # Export option
        csv = df_filtered.to_csv(index=False)
        st.download_button(
            label="📥 Download Signals (CSV)",
            data=csv,
            file_name=f"signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No signals match the current filters.")

else:
    st.info("👈 Click **Scan Now** to start scanning for signals")

# Auto-refresh logic
if auto_refresh and st.session_state.signals:
    st.info("Auto-refresh enabled. Rescanning every 5 minutes...")
