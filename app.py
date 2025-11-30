import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import hashlib
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURASI SISTEM DAN CSS
# ==========================================

st.set_page_config(
    page_title="MafaFX Pro Hybrid",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (GABUNGAN STYLE LAMA & BARU) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #0f0c29, #302b63, #24243e); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label, li { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    
    /* MATRIX CARD (FITUR BARU) */
    .matrix-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        margin-bottom: 15px;
    }
    .matrix-title { font-size: 0.8em; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
    .matrix-val { font-size: 1.2em; font-weight: bold; margin-top: 5px; }

    /* SIGNAL BOX (FITUR LAMA YANG DIPERTAHANKAN) */
    .signal-box {
        background: rgba(0,0,0,0.3); 
        padding: 20px; 
        border-radius: 15px; 
        text-align: center; 
        border: 1px solid rgba(255,255,255,0.2); 
        margin-bottom: 20px;
    }

    /* Metric Cards */
    div[data-testid="stMetric"] { 
        background-color: rgba(0, 0, 0, 0.4) !important; 
        border: 1px solid rgba(255, 255, 255, 0.2); 
        padding: 15px; 
        border-radius: 15px; 
        backdrop-filter: blur(5px); 
    }
    
    /* Outlook Box */
    .outlook-box {
        background-color: rgba(0, 0, 0, 0.3);
        border-left: 5px solid #FFD700;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
    }

    /* Key Levels Box */
    .sr-box {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        border: 1px dashed rgba(255,255,255,0.3);
    }

    /* Buttons */
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
    
    [data-testid="stSidebar"] [data-testid="stImage"] { margin-left: auto; margin-right: auto; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SISTEM LOGIN
# ==========================================

def get_session_token(username, password):
    raw_str = f"{username}::{password}::MafaFX_Secure_Salt"
    return hashlib.sha256(raw_str.encode()).hexdigest()

def check_password():
    try: VALID_USERS = st.secrets["passwords"]
    except: st.error("Setup Secrets dulu!"); st.stop()
    params = st.query_params
    if "auth_token" in params:
        token = params["auth_token"]
        for user, pwd in VALID_USERS.items():
            if get_session_token(user, pwd) == token:
                st.session_state["password_correct"] = True; st.session_state["username"] = user; break
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        try: st.image("logo.png", width=200)
        except: st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
        with st.form("credentials"):
            st.text_input("Username", key="username_input")
            st.text_input("Password", type="password", key="password_input")
            if st.form_submit_button("LOGIN"):
                user = st.session_state.get("username_input")
                pwd = st.session_state.get("password_input")
                if user in VALID_USERS and VALID_USERS[user] == pwd:
                    st.session_state["password_correct"] = True; st.session_state["username"] = user
                    st.query_params["auth_token"] = get_session_token(user, pwd); st.rerun()
                else: st.error("Salah password.")
    return False

if not check_password(): st.stop()

# ==========================================
# 3. ENGINE DATA (GABUNGAN LAMA & BARU)
# ==========================================

def send_telegram_notification(message):
    try:
        bot_token = st.secrets["telegram"]["BOT_TOKEN"]
        chat_ids_str = st.secrets["telegram"]["CHAT_IDS"]
        chat_ids_list = [id.strip() for id in chat_ids_str.split(',')]
        for chat_id in chat_ids_list:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
            requests.post(url, data=payload, timeout=5)
        return True
    except: return False

def get_twelvedata(symbol, interval, api_key):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=50"
    try:
        r = requests.get(url, timeout=10).json()
        if "status" in r and r["status"] == "error": return None
        return r.get("values", [])
    except: return None

# 🟢 BARU: YIELD US10Y
def get_us10y_data():
    try:
        ticker = yf.Ticker("^TNX")
        df = ticker.history(period="5d", interval="1h")
        if df.empty: return {'price': 0, 'chg': 0}
        curr = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        chg = ((curr - prev) / prev) * 100
        return {'price': curr, 'chg': chg}
    except: return {'price': 0, 'chg': 0}

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
            if delta > 0: upval = delta; downval = 0.
            else: upval = 0.; downval = -delta
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
        df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=7)
        df = df.set_index('datetime').sort_index()
        df['close'] = df['close'].astype(float)
        hist = df['close'].values
        curr = df['close'].iloc[-1]
        prev = df['close'].iloc[-2]
        if inverse: 
            chg = -1 * ((curr - prev) / prev) * 100
            chart = df['close'].pct_change() * -1
        else: 
            chg = ((curr - prev) / prev) * 100
            chart = df['close']
        return curr, chg, chart, hist
    except: return None, None, None, None

def calculate_sr_levels(raw_vals):
    try:
        if not raw_vals: return None
        df = pd.DataFrame(raw_vals); df['high']=df['high'].astype(float); df['low']=df['low'].astype(float); df['close']=df['close'].astype(float)
        w = df.head(24)
        return {'R1': w['high'].max(), 'S1': w['low'].min(), 'P': w['close'].mean()}
    except: return {'R1':0,'S1':0,'P':0}

@st.cache_data(ttl=3600)
def fetch_news():
    try:
        df = pd.read_csv("https://nfs.faireconomy.media/ff_calendar_thisweek.csv")
        df = df[df['Country'] == 'USD'].copy()
        df = df[df['Impact'].isin(['High', 'Medium'])].copy()
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%m-%d-%Y %I:%M%p', errors='coerce')
        df['WIB'] = df['DateTime'] + pd.Timedelta(hours=11)
        today = datetime.now().date()
        df_today = df[df['WIB'].dt.date == today].sort_values('WIB') # Filter Hari Ini Saja untuk Matrix
        
        return df_today, df # Return (Hari Ini, Semua Minggu Ini)
    except: return pd.DataFrame(), pd.DataFrame()

# 🟢 BARU: LOGIKA BIAS (SCORING)
def determine_bias(dxy_chg, us10y_chg, rsi):
    score = 0
    if dxy_chg > 0.05: score -= 2
    elif dxy_chg < -0.05: score += 2
    
    if us10y_chg > 0.5: score -= 2
    elif us10y_chg < -0.5: score += 2
    
    if rsi > 60: score += 1
    elif rsi < 40: score -= 1
    
    if score >= 3: return "STRONG BUY", "#00CC96"
    elif score <= -3: return "STRONG SELL", "#FF4B4B"
    elif score > 0: return "WEAK BUY", "#b2d8d8"
    elif score < 0: return "WEAK SELL", "#ffcccc"
    else: return "NEUTRAL", "#FFFFFF"

@st.cache_data(ttl=300)
def fetch_market_data():
    try: api = st.secrets["twelvedata"]["api_key"]
    except: return None
    
    g_raw = get_twelvedata("XAU/USD", "1h", api)
    d_raw = get_twelvedata("EUR/USD", "1h", api)
    if not g_raw or not d_raw: return None
    
    gp, gc, gchart, ghist = process_data(g_raw)
    dp, dc, dchart, dhist = process_data(d_raw, inverse=True)
    sr = calculate_sr_levels(g_raw)
    rsi = calculate_rsi(ghist)
    sentiment = {'net_score': (rsi-50)/50, 'bullish': rsi, 'bearish': 100-rsi}
    
    # NEW DATA
    us10y = get_us10y_data()
    news_today, news_week = fetch_news()
    bias_text, bias_col = determine_bias(dc, us10y['chg'], rsi)
    
    return {
        'GOLD': {'p': gp, 'c': gc, 'chart': gchart, 'sr': sr},
        'DXY': {'p': dp, 'c': dc, 'chart': dchart},
        'US10Y': us10y,
        'SENTIMENT': sentiment,
        'NEWS': {'today': news_today, 'week': news_week},
        'BIAS': {'text': bias_text, 'color': bias_col}
    }

# ==========================================
# 4. DASHBOARD UTAMA
# ==========================================

def main():
    if 'last_signal' not in st.session_state: st.session_state['last_signal'] = "NEUTRAL"

    with st.sidebar:
        try: st.image("logo.png", width=120)
        except: st.write("## 👑 MafaFX")
        st.write(f"User: **{st.session_state.get('username')}**")
        st.markdown("---")
        if st.button("🚪 Logout"):
            st.session_state["password_correct"] = False
            st.query_params.clear(); st.rerun()

    col_head, col_act = st.columns([5, 2])
    with col_head:
        st.title("MafaFX Premium")
        st.caption("⚡ Hybrid System: Fundamental Matrix + H1 Execution")
    with col_act:
        c1, c2 = st.columns(2)
        with c1: 
            if st.button("🔄 Refresh"): st.cache_data.clear(); st.rerun()

    with st.spinner("Menggabungkan Data Fundamental & Teknikal..."):
        data = fetch_market_data()
        if not data: st.warning("Menunggu data API..."); return

        gold = data['GOLD']; dxy = data['DXY']; us10y = data['US10Y']
        sentiment = data['SENTIMENT']; bias = data['BIAS']
        sr = gold['sr']
        
        # === [BAGIAN 1: FUNDAMENTAL MATRIX BARU] ===
        st.markdown("### 🛡️ Fundamental Matrix (5-Point Check)")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        # DXY
        d_col = "#FF4B4B" if dxy['c'] > 0 else "#00CC96"
        with m1: st.markdown(f"""<div class="matrix-card"><div class="matrix-title">1. USD (DXY)</div><div class="matrix-val" style="color:{d_col}">{dxy['c']:+.2f}%</div></div>""", unsafe_allow_html=True)
        
        # US10Y
        u_col = "#FF4B4B" if us10y['chg'] > 0 else "#00CC96"
        with m2: st.markdown(f"""<div class="matrix-card"><div class="matrix-title">2. US10Y YIELD</div><div class="matrix-val" style="color:{u_col}">{us10y['chg']:+.2f}%</div></div>""", unsafe_allow_html=True)
        
        # RSI
        r_val = sentiment['bullish']
        r_col = "#00CC96" if r_val > 50 else "#FF4B4B"
        with m3: st.markdown(f"""<div class="matrix-card"><div class="matrix-title">3. SENTIMENT</div><div class="matrix-val" style="color:{r_col}">{r_val:.0f}/100</div></div>""", unsafe_allow_html=True)
        
        # NEWS TODAY
        n_count = len(data['NEWS']['today'])
        n_col = "#FF4B4B" if n_count > 0 else "#FFFFFF"
        with m4: st.markdown(f"""<div class="matrix-card"><div class="matrix-title">4. NEWS TODAY</div><div class="matrix-val" style="color:{n_col}">{n_count}</div></div>""", unsafe_allow_html=True)
        
        # BIAS
        with m5: st.markdown(f"""<div class="matrix-card" style="border-color:{bias['color']};"><div class="matrix-title">5. BIAS ARAH</div><div class="matrix-val" style="color:{bias['color']}; font-size:1em;">{bias['text']}</div></div>""", unsafe_allow_html=True)
        
        st.markdown("---")

        # === [BAGIAN 2: DASHBOARD EKSEKUSI (FITUR LAMA DIPERTAHANKAN)] ===
        
        # Logic Sinyal Utama (H1)
        current_signal = "NEUTRAL"; signal_color = "#FFFFFF"
        if dxy['c'] > 0.05: current_signal = "SELL"; signal_color = "#FF4B4B"
        elif dxy['c'] < -0.05: current_signal = "BUY"; signal_color = "#00CC96"

        if current_signal == "SELL": signal_text = "JUAL KUAT 🔴" if sentiment['net_score'] < -0.2 else "TEKANAN JUAL 🔴"
        elif current_signal == "BUY": signal_text = "BELI KUAT 🟢" if sentiment['net_score'] > 0.2 else "PELUANG BELI 🟢"
        else: signal_text = "NEUTRAL (WAIT & SEE) ⚪"

        # Notifikasi (Tetap pakai Sinyal Eksekusi, bukan Bias)
        if current_signal != st.session_state['last_signal'] and current_signal != "NEUTRAL":
            message = (f"🚨 *[MAFAFX ALERT]*\nSinyal: *{signal_text}*\nHarga: ${gold['p']:,.2f}\nBias: {bias['text']}")
            send_telegram_notification(message)
            st.session_state['last_signal'] = current_signal

        # VISUALISASI KOTAK BESAR (LAMA)
        st.markdown(f"""
        <div class="signal-box">
            <h1 style="margin:0; text-shadow: 0 0 15px {signal_color}; color: {signal_color}; font-size: 2.5em;">{signal_text}</h1>
            <h3 style="margin:5px 0 0 0; color: white;">XAU/USD: ${gold['p']:,.2f}</h3>
            <p style="margin:0; opacity:0.7; font-size: 0.9em;">Perubahan 1 Jam: {gold['c']:.2f}%</p>
        </div>
        """, unsafe_allow_html=True)
        
        c_sr, c_outlook = st.columns([1, 2])
        
        # KOLOM SUPPORT RESISTANCE (LAMA)
        with c_sr:
            st.markdown("### 🎯 Key Levels (24H)")
            st.markdown(f"""
            <div class="sr-box" style="border-color: #FF4B4B;"><small style="color: #FF4B4B;">RESISTANCE</small><br><b style="font-size: 1.2em;">${sr['R1']:,.2f}</b></div>
            <div style="margin: 5px 0;"></div>
            <div class="sr-box" style="border-color: #FFD700;"><small style="color: #FFD700;">PIVOT</small><br><b style="font-size: 1.2em;">${sr['P']:,.2f}</b></div>
            <div style="margin: 5px 0;"></div>
            <div class="sr-box" style="border-color: #00CC96;"><small style="color: #00CC96;">SUPPORT</small><br><b style="font-size: 1.2em;">${sr['S1']:,.2f}</b></div>
            """, unsafe_allow_html=True)
            
        # KOLOM OUTLOOK (LAMA + UPDATE BIAS)
        with c_outlook:
            st.markdown("### 📢 Market Outlook")
            # Generate outlook text
            outlook_text = f"Fundamental Bias: **{bias['text']}**. "
            if dxy['c'] > 0.05: outlook_text += "Dolar menguat menekan Emas. "
            elif dxy['c'] < -0.05: outlook_text += "Dolar melemah mendukung Emas. "
            
            if sentiment['bullish'] > 70: outlook_text += "Hati-hati Overbought."
            elif sentiment['bullish'] < 30: outlook_text += "Hati-hati Oversold."
            
            st.markdown(f"""
            <div class="outlook-box">
                <p style="margin: 0; font-size: 1.1em; line-height: 1.6;">{outlook_text}</p>
                <br>
                <small>Teknikal RSI: <b>{sentiment['bullish']:.1f}/100</b> | Yield US10Y: <b>{us10y['chg']:+.2f}%</b></small>
            </div>
            """, unsafe_allow_html=True)
            
        col_sent1, col_sent2, col_sent3 = st.columns(3)
        col_sent1.metric("Skor Teknikal RSI", f"{sentiment['net_score']:.2f}")
        col_sent2.metric("Bullish Power", f"{sentiment['bullish']:.1f}")
        col_sent3.metric("Bearish Power", f"{sentiment['bearish']:.1f}")
        
        st.markdown("---")

        # CHART & CALENDAR (LAMA)
        st.markdown("### 🚦 Korelasi Arus Dolar vs Harga Emas")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.65, 0.35], subplot_titles=("Harga Emas", "Tekanan DXY"))
        fig.add_trace(go.Scatter(y=gold['chart'], mode='lines', name='Gold', line=dict(color='#FFD700', width=3), fill='tozeroy'), row=1, col=1)
        dxy_vals = dxy['chart'].dropna()
        bar_colors = ['#FF4B4B' if val > 0 else '#00CC96' for val in dxy_vals]
        fig.add_trace(go.Bar(x=dxy_vals.index, y=dxy_vals, name='DXY Pressure', marker_color=bar_colors), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        c_news, c_tips = st.columns([2, 1])
        with c_news:
            st.markdown("### 📰 Kalender USD (High Impact)")
            # Tampilkan News Minggu Ini (seperti sebelumnya)
            calendar = data['NEWS']['week']
            if not calendar.empty: st.dataframe(calendar, use_container_width=True, hide_index=True)
            else: st.info("Tidak ada berita High Impact USD minggu ini.")
        
        with c_tips:
            st.markdown("### 💡 Tips Trading")
            st.info("""
            * **Cek Matrix (Atas):** Jika DXY & US10Y Merah semua, JANGAN BUY.
            * **Cek Sinyal (Tengah):** Eksekusi hanya jika sinyal sesuai Matrix.
            * **S1/R1:** Target Profit realistis harian.
            """)

if __name__ == "__main__":
    main()
