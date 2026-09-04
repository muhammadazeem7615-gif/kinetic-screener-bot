import os
import time
import requests
import ccxt
import pandas as pd
import numpy as np

# Configuration from Environment Variables (for secure cloud hosting)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'YOUR_TELEGRAM_CHAT_ID')

exchange = ccxt.binance({
    'options': {'defaultType': 'future'},
    'enableRateLimit': True,
    'urls': {
        'api': {
            'public': 'https://data-api.binance.vision/api/v3',
            'fapi': 'https://fapi.binance.com/fapi/v1',
        }
    }
})

def send_telegram_alert(message):
    """Sends immediate push notification to your phone via Telegram."""
    if TELEGRAM_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN':
        print(message)
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

def calculate_ma(series, length, ma_type='EMA'):
    if ma_type == 'SMA':
        return series.rolling(window=length).mean()
    return series.ewm(span=length, adjust=False).mean()

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

    df['trend_up'] = df['ribbon_fast'] > df['ribbon_slow']
    df['acceleration'] = df['ribbon_fast'] > df['ribbon_fast'].shift(1)

    # State triggers on current candle
    df['bull_cross'] = df['trend_up'] & (~df['trend_up'].shift(1))
    df['bear_cross'] = (~df['trend_up']) & df['trend_up'].shift(1)
    df['bull_accel_trigger'] = (df['trend_up'] & df['acceleration']) & (~(df['trend_up'].shift(1) & df['acceleration'].shift(1)))
    df['bear_accel_trigger'] = ((~df['trend_up']) & (~df['acceleration'])) & (~((~df['trend_up'].shift(1)) & (~df['acceleration'].shift(1))))

    return df

def run_scan():
    markets = exchange.load_markets()
    symbols = [m for m in markets if markets[m]['linear'] and markets[m]['quote'] == 'USDT' and markets[m]['active']]
    
    tickers = exchange.fetch_tickers()
    sorted_symbols = sorted(
        symbols, 
        key=lambda x: tickers[x]['quoteVolume'] if x in tickers and tickers[x]['quoteVolume'] is not None else 0, 
        reverse=True
    )[:40]

    for symbol in sorted_symbols:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = compute_kinetic_ribbon(df)

            last_bar = df.iloc[-1]
            pair_name = symbol.replace('/USDT:USDT', '')
            price = last_bar['close']

            # Send push alert if a fresh trigger occurred
            if last_bar['bull_cross']:
                msg = f"🚀 *BULLISH CROSSOVER DETECTED*\n\n*Coin:* #{pair_name}\n*Price:* ${price}\n*Timeframe:* 15m\n*Action:* Look for LONG entry setup."
                send_telegram_alert(msg)
            elif last_bar['bear_cross']:
                msg = f"🔻 *BEARISH CROSSOVER DETECTED*\n\n*Coin:* #{pair_name}\n*Price:* ${price}\n*Timeframe:* 15m\n*Action:* Look for SHORT entry setup."
                send_telegram_alert(msg)
            elif last_bar['bull_accel_trigger']:
                msg = f"⚡ *BULLISH ACCELERATION*\n\n*Coin:* #{pair_name}\n*Price:* ${price}\n*Timeframe:* 15m"
                send_telegram_alert(msg)
            elif last_bar['bear_accel_trigger']:
                msg = f"⚡ *BEARISH ACCELERATION*\n\n*Coin:* #{pair_name}\n*Price:* ${price}\n*Timeframe:* 15m"
                send_telegram_alert(msg)

        except Exception:
            continue

if __name__ == '__main__':
    print("Scanner active. Monitoring Binance Futures...")
    while True:
        run_scan()
        time.sleep(30)  # Scan every 30 seconds
