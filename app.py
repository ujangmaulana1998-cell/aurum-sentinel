import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import yfinance as yf
from datetime import datetime

# --- 1. KONFIGURASI SISTEM ---
st.set_page_config(
    page_title="MafaFX Institutional",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #0f0c29, #302b63, #24243e); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    div[data-testid="stMetric"] { background-color: rgba(255, 255, 255, 0.05) !important; border: 1px solid rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 10px; backdrop-filter: blur(5px); }
    div.stButton > button { width: 100%; background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%); border: none; font-weight: bold; color: white; padding: 10px; }
    
    /* Logo Center */
    [data-testid="stSidebar"] [data-testid="stImage"] {
        display: block; margin-left: auto; margin-right: auto;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SISTEM LOGIN ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        try: st.image("logo.png", width=180)
        except: st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; opacity: 0.8;'>Institutional Dashboard</h4>", unsafe_allow_html=True)
        with st.form("credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            if st.form_submit_button("ACCESS TERMINAL"):
                user = st.session_state.get("username")
                pwd = st.session_state.get("password")
                if user in st.secrets["passwords"] and st.secrets["passwords"][user] == pwd:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Access Denied.")
    return False

if not check_password(): st.stop()

# ==========================================
# 3. HYBRID DATA ENGINE (TWELVE DATA + YFINANCE)
# ==========================================

def get_twelvedata(symbol, interval, api_key):
    """Core Engine: Real-Time Price (Twelve Data)"""
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=35"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if "status" in data and data["status"] == "error": return None
        return data.get("values", [])
    except: return None

def get_yield_data():
    """Auxiliary Engine: US 10Y Yield (Yahoo Finance)"""
    try:
        # ^TNX adalah ticker untuk CBOE 10-Year Treasury Yield
        # Kita gunakan yf.Ticker yang lebih ringan daripada yf.download bulk
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="5d", interval="15m")
        
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2]
            change = ((current - prev) / prev) * 100
            
            # Normalisasi untuk chart
            return current, change, hist['Close']
        return None, None, None
    except:
        return None, None, None

def process_forex_data(values, inverse=False):
    if not values: return None, None, None, 0
    try:
        df = pd.DataFrame(values)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime').sort_index()
        df['close'] = df['close'].astype(float)
        
        current = df['close'].iloc[-1]
        prev = df['close'].iloc[-2]
        
        # Hitung Volatilitas (High - Low) candle terakhir
        high = float(values[0]['high'])
        low = float(values[0]['low'])
        volatility = high - low
        
        if inverse:
            # Proxy DXY (Inverted EURUSD)
            display_price = (1 / current) * 100
            change_pct = -1 * ((current - prev) / prev) * 100
            chart_data = (df['close'].pct_change().cumsum() * -1)
        else:
            display_price = current
            change_pct = ((current - prev) / prev) * 100
            chart_data = df['close'].pct_change().cumsum()
            
        return display_price, change_pct, chart_data, volatility
    except: return None, None, None, 0

@st.cache_data(ttl=60)
def fetch_market_data():
    try: api_key = st.secrets["twelvedata"]["api_key"]
    except: st.error("API Key Missing"); return None

    # 1. MAIN DATA (Twelve Data - Cepat)
    gold_raw = get_twelvedata("XAU/USD", "15min", api_key)
    dxy_raw = get_twelvedata("EUR/USD", "15min", api_key)
    
    # 2. AUX DATA (Yahoo Finance - Yields)
    y_price, y_chg, y_chart = get_yield_data()

    if not gold_raw or not dxy_raw: return None
    
    g_price, g_chg, g_chart, g_vol = process_forex_data(gold_raw)
    d_price, d_chg, d_chart, _ = process_forex_data(dxy_raw, inverse=True)
    
    return {
        'GOLD': {'price': g_price, 'chg': g_chg, 'chart': g_chart, 'vol': g_vol},
        'DXY': {'price': d_price, 'chg': d_chg, 'chart': d_chart},
        'YIELD': {'price': y_price, 'chg': y_chg, 'chart': y_chart}
    }

# ==========================================
# 4. DASHBOARD VISUALIZATION
# ==========================================

def main_dashboard():
    with st.sidebar:
        try: st.image("logo.png", width=140)
        except: st.header("MafaFX")
        st.markdown("---")
        st.success("● System Online")
        st.caption(f"Operator: {st.session_state.get('username')}")
        if st.button("Log Out"): st.session_state["password_correct"] = False; st.rerun()

    col_title, col_refresh = st.columns([4, 1])
    with col_title:
        st.title("MafaFX Institutional Dashboard")
        st.caption("Hybrid Engine | Twelve Data (XAU/DXY) + Yahoo (Yields)")
    with col_refresh:
        st.write("")
        if st.button("⚡ REFRESH"): st.cache_data.clear(); st.rerun()

    with st.spinner('Scanning Market Data...'):
        data = fetch_market_data()
        
        if data is None:
            st.warning("Menunggu data feed... Silakan refresh dalam 1 menit.")
            return

        gold = data['GOLD']
        dxy = data['DXY']
        yields = data['YIELD']
        
        # --- SCORING LOGIC ---
        score = 0
        reasons = []
        
        # 1. Dolar Impact (Bobot 3)
        if dxy['chg'] > 0.02: score -= 3; reasons.append("Dolar Menguat")
        elif dxy['chg'] < -0.02: score += 3; reasons.append("Dolar Melemah")
        
        # 2. Yield Impact (Bobot 4 - Jika Data Ada)
        if yields['price'] is not None:
            if yields['chg'] > 0.5: score -= 4; reasons.append("Yields Meroket")
            elif yields['chg'] < -0.5: score += 4; reasons.append("Yields Turun")
        else:
            reasons.append("Yield Data Offline (Ignored)")
        
        # 3. Volatility Check
        vol_state = "Normal"
        if gold['vol'] > 5.0: vol_state = "High Volatility ⚠️"
        elif gold['vol'] < 1.0: vol_state = "Consolidation 💤"

        # Signal Decision
        if score >= 4: signal = "STRONG BUY 🟢"
        elif score >= 2: signal = "BUY LEANING ↗️"
        elif score <= -4: signal = "STRONG SELL 🔴"
        elif score <= -2: signal = "SELL LEANING ↘️"
        else: signal = "NEUTRAL ⚪"

        # --- UI DISPLAY ---
        
        # Signal Banner
        st.markdown(f"""
        <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 15px; padding: 20px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin:0; font-size: 3em; text-shadow: 0px 0px 20px rgba(255,255,255,0.2);">{signal}</h1>
            <p style="color: #aaa; margin-top: 5px;">Score: {score}/10 | Volatility: {vol_state}</p>
        </div>
        """, unsafe_allow_html=True)

        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🥇 XAU/USD (Live)", f"${gold['price']:,.2f}", f"{gold['chg']:.2f}%")
        c2.metric("💵 DXY (Proxy)", f"{dxy['price']:.2f}", f"{dxy['chg']:.2f}%", delta_color="inverse")
        
        # Yield handling
        y_val = f"{yields['price']:.3f}%" if yields['price'] else "N/A"
        y_delta = f"{yields['chg']:.2f}%" if yields['chg'] else "0%"
        c3.metric("📈 US 10Y Yield", y_val, y_delta, delta_color="inverse")
        
        c4.metric("📊 Range (15m)", f"${gold['vol']:.2f}", vol_state, delta_color="off")

        # Chart Section
        st.markdown("### 🧬 Intermarket Correlation")
        
        fig = go.Figure()
        # Gold
        fig.add_trace(go.Scatter(y=gold['chart'], mode='lines', name='Gold Price', fill='tozeroy', line=dict(color='#FFD700', width=2)))
        # DXY
        fig.add_trace(go.Scatter(y=dxy['chart'], mode='lines', name='Dolar Strength', line=dict(color='#00d2ff', width=2)))
        # Yield (Jika Ada)
        if yields['chart'] is not None and len(yields['chart']) > 0:
            y_norm = yields['chart'].pct_change().cumsum()
            fig.add_trace(go.Scatter(y=y_norm, mode='lines', name='US10Y Yield', line=dict(color='#ff4b4b', dash='dot', width=2)))

        fig.update_layout(
            template="plotly_dark", 
            height=450, 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified",
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", y=1.02, x=0, xanchor="left")
        )
        st.plotly_chart(fig, use_container_width=True)

        if reasons:
            st.info(f"**Drivers:** {', '.join(reasons)}")

if __name__ == "__main__":
    main_dashboard()


