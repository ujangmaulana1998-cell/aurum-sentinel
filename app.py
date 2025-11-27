import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import hashlib
import numpy as np
from datetime import datetime, timedelta, timezone 

# ==========================================
# 1. KONFIGURASI SISTEM DAN CSS
# ==========================================

st.set_page_config(
    page_title="MafaFX Premium",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (UI MINIMALIS & ELEGAN) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #d926a9, #bc20b6, #9b1fc0, #7623c8, #4728cd); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    
    /* Styling Metric Cards */
    div[data-testid="stMetric"] { 
        background-color: rgba(0, 0, 0, 0.4) !important; 
        border: 1px solid rgba(255, 255, 255, 0.2); 
        padding: 15px; 
        border-radius: 15px; 
        backdrop-filter: blur(5px); 
        color: white !important;
    }
    
    /* Container Outlook Box */
    .outlook-box {
        background-color: rgba(0, 0, 0, 0.3);
        border-left: 5px solid #FFD700;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }

    /* GAYA TOMBOL HEADER (Refresh & Logout) - Jajar & Minimalis */
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) button {
        background-color: transparent !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        color: white !important;
        font-weight: normal !important;
        padding: 5px 15px !important;
        font-size: 14px !important;
        border-radius: 20px !important;
        transition: all 0.3s ease;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) button:hover {
        border-color: #FFD700 !important;
        color: #FFD700 !important;
        background-color: rgba(0,0,0,0.5) !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stImage"] { text-align: center; display: block; margin-left: auto; margin-right: auto; width: 100%; }
    div[data-testid="stForm"] { background-color: rgba(0, 0, 0, 0.5); padding: 30px; border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.3); }
    [data-testid="stDataFrame"] { background-color: rgba(0, 0, 0, 0.3) !important; border-radius: 10px; padding: 10px; }
    .stDataFrame .data-cell { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SISTEM LOGIN
# ==========================================

def get_session_token(username, password):
    raw_str = f"{username}::{password}::MafaFX_Secure_Salt"
    return hashlib.sha256(raw_str.encode()).hexdigest()

def check_password():
    try:
        VALID_USERS = st.secrets["passwords"]
    except:
        st.error("API Error: Secrets untuk Login tidak ditemukan.")
        st.stop()
        
    params = st.query_params
    if "auth_token" in params:
        token = params["auth_token"]
        for user, pwd in VALID_USERS.items():
            if get_session_token(user, pwd) == token:
                st.session_state["password_correct"] = True
                st.session_state["username"] = user
                break

    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    
    if st.session_state["password_correct"]: return True

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        try: st.image("logo.png", width=200)
        except: st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
            
        st.markdown("<h3 style='text-align: center;'>Real-Time Intelligence</h3>", unsafe_allow_html=True)
        
        with st.form("credentials"):
            st.text_input("Username", key="username_input")
            st.text_input("Password", type="password", key="password_input")
            
            if st.form_submit_button("LOGIN"):
                user = st.session_state.get("username_input")
                pwd = st.session_state.get("password_input")
                
                if user in VALID_USERS and VALID_USERS[user] == pwd:
                    st.session_state["password_correct"] = True
                    st.session_state["username"] = user
                    token = get_session_token(user, pwd)
                    st.query_params["auth_token"] = token
                    st.rerun()
                else:
                    st.error("Username/Password Salah.")
                    
    return False

if not check_password(): st.stop()


# 🟢 FUNGSI NOTIFIKASI TELEGRAM
def send_telegram_notification(message):
    try:
        bot_token = st.secrets["telegram"]["BOT_TOKEN"]
        chat_ids_str = st.secrets["telegram"]["CHAT_IDS"]
        chat_ids_list = [id.strip() for id in chat_ids_str.split(',')]
    except KeyError:
        return False

    success = True
    for chat_id in chat_ids_list:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        try:
            requests.post(url, data=payload, timeout=5)
        except:
            success = False
    return success


# ==========================================
# 3. ENGINE DATA & ANALISIS
# ==========================================

def get_twelvedata(symbol, interval, api_key):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=50" 
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if "status" in data and data["status"] == "error": return None
        return data.get("values", [])
    except: return None

def calculate_rsi(prices, period=14):
    try:
        prices = np.array(prices).astype(float)
        if len(prices) < period + 1: return 50.0
        
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum()/period
        down = -seed[seed < 0].sum()/period
        if down == 0: return 100.0
        rs = up/down
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100./(1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i-1] 
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up/down
            rsi[i] = 100. - 100./(1. + rs)
        return rsi[-1]
    except: return 50.0

def process_data(values, inverse=False):
    if not values: return None, None, None, None
    try:
        df = pd.DataFrame(values)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['datetime'] = df['datetime'] + pd.Timedelta(hours=7)
        df = df.set_index('datetime').sort_index()
        df['close'] = df['close'].astype(float)
        
        price_history = df['close'].values 
        current = df['close'].iloc[-1]
        prev = df['close'].iloc[-2]
        
        if inverse: 
            change_pct = -1 * ((current - prev) / prev) * 100
            chart_data = df['close'].pct_change() * -1 
            display_price = (1 / current) * 100 
        else:
            change_pct = ((current - prev) / prev) * 100
            chart_data = df['close'] 
            display_price = current
            
        return display_price, change_pct, chart_data, price_history
    except: return None, None, None, None

@st.cache_data(ttl=3600) 
def fetch_economic_calendar():
    """Mengambil Kalender Ekonomi dari Finnhub dengan Error Handling Kuat."""
    try:
        api_key = st.secrets["finnhub"]["api_key"]
        today = datetime.now().strftime('%Y-%m-%d')
        seven_days_later = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={seven_days_later}&token={api_key}"
        
        response = requests.get(url, timeout=10)
        data = response.json().get("economicCalendar", [])
        
        if not data: return pd.DataFrame() # Return empty DF if no data
        
        df = pd.DataFrame(data)
        # Filter High Impact US Only
        df = df[ (df['country'] == 'US') & (df['impact'] == 'high') ].copy()
        
        if df.empty: return pd.DataFrame()

        df['datetime_utc'] = pd.to_datetime(df['date'])
        df['WIB'] = df['datetime_utc'].apply(lambda x: x.tz_localize('UTC').tz_convert('Asia/Jakarta'))
        
        df_display = df[['WIB', 'event', 'actual', 'forecast', 'previous']].rename(columns={
            'WIB': 'Waktu (WIB)', 'event': 'Berita / Data', 'actual': 'Act',
            'forecast': 'Fcst', 'previous': 'Prev'
        })
        df_display['Waktu (WIB)'] = df_display['Waktu (WIB)'].dt.strftime('%a, %H:%M')
        return df_display
    except:
        return pd.DataFrame() # Fail safe

def calculate_technical_sentiment(prices):
    try:
        rsi = calculate_rsi(prices)
        net_score = (rsi - 50) / 50 
        return {'net_score': net_score, 'bullish': rsi, 'bearish': 100 - rsi, 'error': False}
    except:
        return {'net_score': 0, 'bullish': 50, 'bearish': 50, 'error': True}

# 🟢 FUNGSI BARU: GENERATE MARKET OUTLOOK (ANALISIS TEKS)
def generate_market_outlook(dxy_change, gold_rsi):
    """Menghasilkan teks analisis fundamental & teknikal sederhana."""
    outlook_dxy = ""
    outlook_gold = ""
    
    # Analisis Dolar
    if dxy_change > 0.05:
        outlook_dxy = "Dolar AS (DXY) sedang menguat signifikan. Ini memberikan tekanan bearish pada harga Emas."
    elif dxy_change < -0.05:
        outlook_dxy = "Dolar AS (DXY) terlihat melemah. Ini menjadi katalis positif bagi kenaikan Emas."
    else:
        outlook_dxy = "Dolar AS bergerak mendatar (sideways). Pasar menunggu pemicu berita selanjutnya."
        
    # Analisis Emas (RSI)
    if gold_rsi > 70:
        outlook_gold = "Secara teknikal, Emas sudah Overbought (Jenuh Beli). Hati-hati koreksi turun."
    elif gold_rsi < 30:
        outlook_gold = "Secara teknikal, Emas sudah Oversold (Jenuh Jual). Ada potensi pantulan naik."
    elif gold_rsi > 55:
        outlook_gold = "Momentum Emas cenderung Bullish, namun belum mencapai level ekstrem."
    elif gold_rsi < 45:
        outlook_gold = "Momentum Emas cenderung Bearish, waspada tekanan jual lanjutan."
    else:
        outlook_gold = "Emas berada di area Netral. Fokus pada Breakout level support/resistance terdekat."
        
    return f"{outlook_dxy} {outlook_gold}"

@st.cache_data(ttl=3600) 
def fetch_market_data():
    try: api_key = st.secrets["twelvedata"]["api_key"]
    except: st.error("Twelve Data API Key Missing"); return None

    gold_raw = get_twelvedata("XAU/USD", "1h", api_key) 
    dxy_raw = get_twelvedata("EUR/USD", "1h", api_key)
    
    if not gold_raw or not dxy_raw: st.warning("Twelve Data tidak ditemukan."); return None
    
    g_price, g_chg, g_chart, g_hist = process_data(gold_raw)
    d_price, d_chg, d_chart, d_hist = process_data(dxy_raw, inverse=True)
    
    calendar_data = fetch_economic_calendar()
    sentiment_data = calculate_technical_sentiment(g_hist)

    return {
        'GOLD': {'price': g_price, 'chg': g_chg, 'chart': g_chart, 'hist': g_hist},
        'DXY': {'price': d_price, 'chg': d_chg, 'chart': d_chart},
        'CALENDAR': calendar_data,
        'SENTIMENT': sentiment_data
    }

# ==========================================
# 4. DASHBOARD UTAMA
# ==========================================

def main_dashboard():
    if 'last_signal' not in st.session_state:
        st.session_state['last_signal'] = "NEUTRAL"

    with st.sidebar:
        try: st.image("logo.png", width=150)
        except: st.write("### 👑 MafaFX")
        st.markdown("---")
        st.write(f"User: **{st.session_state.get('username')}**")
        st.caption("Timeframe: H1 (1 Jam)") 
        st.caption("Status: Premium Active")

    # --- HEADER MINIMALIS ---
    col_head, col_act = st.columns([5, 2])
    with col_head:
        st.title("MafaFX Premium")
        st.caption("⚡ Data H1 Real-Time & RSI Sentiment - Waktu Indonesia Barat")
    with col_act:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Refresh"): 
                st.cache_data.clear()
                st.rerun()
        with c2:
            if st.button("🚪 Logout"): 
                st.session_state["password_correct"] = False
                st.query_params.clear() 
                st.rerun()

    # --- LOGIKA & TAMPILAN ---
    with st.spinner('Menganalisis Pasar Emas & Dolar...'):
        data = fetch_market_data()
        
        if data is None:
            st.warning("Menunggu data Real-Time... (Cek API Key di Secrets)")
            return

        gold = data['GOLD']
        dxy = data['DXY']
        sentiment = data['SENTIMENT']
        
        # Logika Sinyal Utama
        current_signal = "NEUTRAL"
        signal_color = "#FFFFFF"
        
        if dxy['chg'] > 0.05: 
            current_signal = "SELL"
            signal_color = "#FF4B4B"
        elif dxy['chg'] < -0.05: 
            current_signal = "BUY"
            signal_color = "#00CC96"

        if current_signal == "SELL":
            signal_text = "JUAL KUAT 🔴" if sentiment['net_score'] < -0.2 else "TEKANAN JUAL 🔴"
        elif current_signal == "BUY":
            signal_text = "BELI KUAT 🟢" if sentiment['net_score'] > 0.2 else "PELUANG BELI 🟢"
        else:
            signal_text = "NEUTRAL (WAIT & SEE) ⚪"

        # Kirim Notif
        if current_signal != st.session_state['last_signal'] and current_signal != "NEUTRAL":
            message = (
                f"🚨 *[MAFAFX ALERT]*\n"
                f"Sinyal: *{signal_text}*\n"
                f"Harga: ${gold['price']:,.2f}\n"
                f"RSI: {sentiment['bullish']:.1f}"
            )
            send_telegram_notification(message)
            st.session_state['last_signal'] = current_signal

        # 1. VISUALISASI UTAMA
        st.markdown(f"""
        <div style="background: rgba(0,0,0,0.3); padding:20px; border-radius:15px; text-align:center; border: 1px solid rgba(255,255,255,0.2); margin-bottom: 20px;">
            <h1 style="margin:0; text-shadow: 0 0 15px {signal_color}; color: {signal_color}; font-size: 2.5em;">{signal_text}</h1>
            <h3 style="margin:5px 0 0 0; color: white;">XAU/USD: ${gold['price']:,.2f}</h3>
            <p style="margin:0; opacity:0.7; font-size: 0.9em;">Perubahan 1 Jam: {gold['chg']:.2f}%</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 2. SEKSI OUTLOOK PASAR (BARU)
        st.markdown("### 📢 Proyeksi & Analisis Pasar (H1)")
        outlook_text = generate_market_outlook(dxy['chg'], sentiment['bullish'])
        st.markdown(f"""
        <div class="outlook-box">
            <p style="font-size: 16px; margin: 0;"><b>Outlook Gold & Dollar:</b><br>{outlook_text}</p>
        </div>
        """, unsafe_allow_html=True)

        col_sent1, col_sent2, col_sent3 = st.columns(3)
        col_sent1.metric("Skor Teknikal RSI", f"{sentiment['net_score']:.2f}")
        col_sent2.metric("Bullish Power", f"{sentiment['bullish']:.1f}")
        col_sent3.metric("Bearish Power", f"{sentiment['bearish']:.1f}")
            
        st.markdown("---")
        
        # 3. CHART HARGA VS TEKANAN
        st.markdown("### 🚦 Korelasi Arus Dolar vs Harga Emas")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.65, 0.35],
                            subplot_titles=("Harga Emas (XAU/USD)", "Tekanan Dolar AS (DXY)"))

        fig.add_trace(go.Scatter(y=gold['chart'], mode='lines', name='Gold', 
                                 line=dict(color='#FFD700', width=3), fill='tozeroy'), row=1, col=1)

        dxy_vals = dxy['chart'].dropna()
        bar_colors = ['#FF4B4B' if val > 0 else '#00CC96' for val in dxy_vals]
        
        fig.add_trace(go.Bar(x=dxy_vals.index, y=dxy_vals, name='DXY Pressure', 
                             marker_color=bar_colors), row=2, col=1)

        fig.update_layout(template="plotly_dark", height=500, 
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                          margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # 4. BERITA HIGH IMPACT
        st.markdown("---")
        c_news, c_tips = st.columns([2, 1])
        
        with c_news:
            st.markdown("### 📰 Kalender Ekonomi (High Impact)")
            calendar = data['CALENDAR']
            if not calendar.empty:
                st.dataframe(calendar, use_container_width=True, hide_index=True)
            else:
                st.info("Tidak ada berita High Impact USD dalam 7 hari ke depan, atau Pasar sedang Libur.")
        
        with c_tips:
            st.markdown("### 💡 Tips Trading")
            st.info("""
            * **DXY Naik** = Emas Turun (Sell)
            * **DXY Turun** = Emas Naik (Buy)
            * Hindari trading 15 menit sebelum berita High Impact rilis.
            """)

if __name__ == "__main__":
    main_dashboard()
