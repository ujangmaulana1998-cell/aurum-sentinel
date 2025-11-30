import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import hashlib
import numpy as np
import yfinance as yf  # 🟢 LIBRARY BARU UNTUK US10Y
from datetime import datetime, time, timedelta
import pytz

# ==========================================
# 1. KONFIGURASI SISTEM & CSS
# ==========================================

st.set_page_config(
    page_title="MafaFX Pro Fundamental",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (PREMIUM LOOK) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #0f0c29, #302b63, #24243e); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label, li { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    
    /* MATRIX BOX STYLING */
    .matrix-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        margin-bottom: 10px;
    }
    .matrix-title { font-size: 0.9em; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
    .matrix-val { font-size: 1.4em; font-weight: bold; margin-top: 5px; }
    
    /* BIAS CARD */
    .bias-card {
        background: linear-gradient(45deg, #1e3c72, #2a5298);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.2);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }

    /* Metric Cards */
    div[data-testid="stMetric"] { background-color: rgba(0, 0, 0, 0.4) !important; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); }
    
    /* Buttons */
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) button {
        background: transparent; border: 1px solid rgba(255,255,255,0.3); color: white; border-radius: 20px;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) button:hover {
        border-color: #FFD700; color: #FFD700;
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
    
    # Login Form
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
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
# 3. ENGINE DATA (5-POINT CHECK)
# ==========================================

# 1 & 2. DXY & XAU (Twelve Data)
def get_twelvedata(symbol, interval, api_key):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=50"
    try:
        r = requests.get(url, timeout=10).json()
        if "status" in r and r["status"] == "error": return None
        return r.get("values", [])
    except: return None

# 3. US10Y (Yahoo Finance)
def get_us10y_data():
    """Mengambil Data Yield US 10 Year via YFinance"""
    try:
        # ^TNX adalah ticker untuk CBOE Interest Rate 10 Year T Note
        ticker = yf.Ticker("^TNX")
        # Ambil data 5 hari terakhir interval 1 jam (atau 1 hari)
        df = ticker.history(period="5d", interval="1h")
        if df.empty: return None
        
        current = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        change_pct = ((current - prev) / prev) * 100
        return {'price': current, 'chg': change_pct}
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
            if delta > 0: upval = delta; downval = 0.
            else: upval = 0.; downval = -delta
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up/down
            rsi[i] = 100. - 100./(1. + rs)
        return rsi[-1]
    except: return 50.0

def process_twelve_data(values, inverse=False):
    if not values: return None, None, None, None
    try:
        df = pd.DataFrame(values)
        df['datetime'] = pd.to_datetime(df['datetime']) + pd.Timedelta(hours=7) # WIB
        df = df.set_index('datetime').sort_index()
        df['close'] = df['close'].astype(float)
        hist = df['close'].values
        curr = df['close'].iloc[-1]
        prev = df['close'].iloc[-2]
        
        if inverse: chg = -1 * ((curr - prev) / prev) * 100
        else: chg = ((curr - prev) / prev) * 100
        
        return curr, chg, df['close'], hist
    except: return None, None, None, None

def calculate_sr(raw_vals):
    try:
        if not raw_vals: return None
        df = pd.DataFrame(raw_vals); df['high']=df['high'].astype(float); df['low']=df['low'].astype(float); df['close']=df['close'].astype(float)
        w = df.head(24)
        return {'R1': w['high'].max(), 'S1': w['low'].min(), 'P': w['close'].mean()}
    except: return {'R1':0,'S1':0,'P':0}

# 4. News Check (Forex Factory)
@st.cache_data(ttl=3600)
def fetch_news_today():
    try:
        df = pd.read_csv("https://nfs.faireconomy.media/ff_calendar_thisweek.csv")
        df = df[df['Country'] == 'USD'].copy()
        df = df[df['Impact'].isin(['High', 'Medium'])].copy()
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%m-%d-%Y %I:%M%p', errors='coerce')
        df['WIB'] = df['DateTime'] + pd.Timedelta(hours=11)
        
        # Filter HANYA HARI INI
        today = datetime.now().date()
        df_today = df[df['WIB'].dt.date == today].sort_values('WIB')
        
        # Format
        df_display = df_today[['WIB', 'Title', 'Impact']].rename(columns={'WIB':'Jam (WIB)', 'Title':'Event'})
        df_display['Jam (WIB)'] = df_display['Jam (WIB)'].dt.strftime('%H:%M')
        return df_display
    except: return pd.DataFrame()

# 5. BIAS DETERMINATION (LOGIC INTI)
def determine_bias(dxy_chg, us10y_chg, rsi):
    score = 0
    reasons = []
    
    # Faktor DXY
    if dxy_chg > 0.05: score -= 2; reasons.append("DXY Bullish")
    elif dxy_chg < -0.05: score += 2; reasons.append("DXY Bearish")
    
    # Faktor US10Y (Yields Naik = Gold Turun)
    if us10y_chg > 0.5: score -= 2; reasons.append("Yields Meroket")
    elif us10y_chg < -0.5: score += 2; reasons.append("Yields Anjlok")
    
    # Faktor RSI
    if rsi > 60: score += 1; reasons.append("Teknikal Bullish")
    elif rsi < 40: score -= 1; reasons.append("Teknikal Bearish")
    
    # Keputusan
    if score >= 3: return "STRONG BUY", "#00CC96", reasons
    elif score <= -3: return "STRONG SELL", "#FF4B4B", reasons
    elif score > 0: return "WEAK BUY", "#b2d8d8", reasons
    elif score < 0: return "WEAK SELL", "#ffcccc", reasons
    else: return "NEUTRAL", "#FFFFFF", ["Market Sideways"]

def get_market_session():
    now_hour = (datetime.now() + timedelta(hours=7)).hour # WIB
    # Estimasi Kasar
    if 5 <= now_hour < 14: return "🌏 SESI ASIA (Sideways/Range)"
    elif 14 <= now_hour < 19: return "🇪🇺 SESI LONDON (Volatile)"
    elif 19 <= now_hour < 24: return "🇺🇸 SESI NEW YORK (Trend/Reversal)"
    else: return "😴 MARKET TUTUP/SEPI"

@st.cache_data(ttl=300)
def fetch_full_data():
    try: api = st.secrets["twelvedata"]["api_key"]
    except: return None
    
    g_raw = get_twelvedata("XAU/USD", "1h", api)
    d_raw = get_twelvedata("EUR/USD", "1h", api) # Inverse DXY proxy
    
    g_price, g_chg, g_chart, g_hist = process_twelve_data(g_raw)
    d_price, d_chg, d_chart, d_hist = process_twelve_data(d_raw, inverse=True)
    us10y = get_us10y_data()
    sr = calculate_sr(g_raw)
    rsi = calculate_rsi(g_hist)
    news = fetch_news_today()
    
    # Fallback jika US10Y error (kadang yfinance limit)
    if us10y is None: us10y = {'price': 4.0, 'chg': 0.0}
    
    bias, color, reasons = determine_bias(d_chg, us10y['chg'], rsi)
    
    return {
        'gold': {'p': g_price, 'c': g_chg, 'chart': g_chart, 'rsi': rsi, 'sr': sr},
        'dxy': {'p': d_price, 'c': d_chg, 'chart': d_chart},
        'us10y': us10y,
        'news': news,
        'bias': {'text': bias, 'color': color, 'reasons': reasons}
    }

# ==========================================
# 4. DASHBOARD UI
# ==========================================

def main():
    with st.sidebar:
        try: st.image("logo.png", width=120)
        except: st.write("## 👑 MafaFX")
        st.write(f"👤 **{st.session_state.get('username')}**")
        st.markdown("---")
        st.info(get_market_session())
        if st.button("🚪 Logout"):
            st.session_state["password_correct"] = False
            st.query_params.clear(); st.rerun()

    st.title("🛡️ MafaFX Fundamental Matrix")
    st.caption("5-Point Check System: DXY • US10Y • Sentiment • News • Bias")
    
    if st.button("🔄 SCAN MARKET SEKARANG"): st.cache_data.clear(); st.rerun()
    
    with st.spinner("Menghubungkan ke Exchange & Obligasi US..."):
        data = fetch_full_data()
        if not data: st.error("Data Feed Error. Cek API Key."); return
        
        gold = data['gold']; dxy = data['dxy']; us10y = data['us10y']; bias = data['bias']
        
        # === BAGIAN 1: MATRIX 5 POIN ===
        st.markdown("### 🔍 Pra-Sesi Checklist (5 Poin)")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        
        # 1. DXY
        dxy_color = "#FF4B4B" if dxy['c'] > 0 else "#00CC96" # Merah jika naik (bad for gold)
        with c1:
            st.markdown(f"""
            <div class="matrix-card">
                <div class="matrix-title">1. ARAH USD (DXY)</div>
                <div class="matrix-val" style="color:{dxy_color}">{dxy['c']:+.2f}%</div>
                <small>{'Menguat' if dxy['c']>0 else 'Melemah'}</small>
            </div>""", unsafe_allow_html=True)
            
        # 2. US10Y
        us_color = "#FF4B4B" if us10y['chg'] > 0 else "#00CC96" # Merah jika naik
        with c2:
            st.markdown(f"""
            <div class="matrix-card">
                <div class="matrix-title">2. US10Y YIELD</div>
                <div class="matrix-val" style="color:{us_color}">{us10y['chg']:+.2f}%</div>
                <small>{us10y['price']:.3f}% Rate</small>
            </div>""", unsafe_allow_html=True)

        # 3. SENTIMEN RSI
        rsi_val = gold['rsi']
        rsi_col = "#00CC96" if rsi > 50 else "#FF4B4B"
        with c3:
            st.markdown(f"""
            <div class="matrix-card">
                <div class="matrix-title">3. TEKNIKAL (RSI)</div>
                <div class="matrix-val" style="color:{rsi_col}">{rsi_val:.1f}</div>
                <small>{'Bullish' if rsi>50 else 'Bearish'}</small>
            </div>""", unsafe_allow_html=True)
            
        # 4. NEWS HARI INI
        news_count = len(data['news'])
        news_col = "#FF4B4B" if news_count > 0 else "#FFFFFF"
        with c4:
            st.markdown(f"""
            <div class="matrix-card">
                <div class="matrix-title">4. JADWAL NEWS</div>
                <div class="matrix-val" style="color:{news_col}">{news_count}</div>
                <small>High Impact Today</small>
            </div>""", unsafe_allow_html=True)

        # 5. FINAL BIAS
        with c5:
            st.markdown(f"""
            <div class="matrix-card" style="border-color:{bias['color']}; background:rgba(255,255,255,0.08);">
                <div class="matrix-title">5. BIAS XAUUSD</div>
                <div class="matrix-val" style="color:{bias['color']}; font-size:1.1em;">{bias['text']}</div>
                <small>{', '.join(bias['reasons'][:1])}</small>
            </div>""", unsafe_allow_html=True)

        # === BAGIAN 2: DATA VISUALIZATION ===
        
        # TAMPILAN JADWAL NEWS (Jika Ada)
        if news_count > 0:
            with st.expander("📅 Rincian Jadwal News Hari Ini (WIB)", expanded=True):
                st.dataframe(data['news'], use_container_width=True, hide_index=True)
        else:
            st.caption("✅ Tidak ada News High Impact USD terjadwal hari ini. Market Technical.")
            
        st.markdown("---")
        
        # KEY LEVELS & CHART
        col_main, col_side = st.columns([3, 1])
        
        with col_main:
            st.subheader(f"Grafik Korelasi (Gold vs DXY)")
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(y=gold['chart'], name="Gold Price", line=dict(color='#FFD700', width=3)), secondary_y=False)
            fig.add_trace(go.Bar(x=dxy['chart'].index, y=dxy['chart'], name="DXY Pressure", marker_color='rgba(255,255,255,0.2)'), secondary_y=True)
            fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
        with col_side:
            st.subheader("🎯 Key Levels")
            sr = gold['sr']
            st.markdown(f"""
            <div style="background:rgba(255,0,0,0.2); padding:10px; border-radius:5px; margin-bottom:5px; text-align:center;">
                <small>RESISTANCE</small><br><b>${sr['R1']:,.2f}</b>
            </div>
            <div style="background:rgba(255,215,0,0.2); padding:10px; border-radius:5px; margin-bottom:5px; text-align:center;">
                <small>PIVOT</small><br><b>${sr['P']:,.2f}</b>
            </div>
            <div style="background:rgba(0,255,0,0.2); padding:10px; border-radius:5px; margin-bottom:5px; text-align:center;">
                <small>SUPPORT</small><br><b>${sr['S1']:,.2f}</b>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.metric("Harga Emas Live", f"${gold['p']:,.2f}", f"{gold['c']:.2f}%")

if __name__ == "__main__":
    main()
