import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime

# --- 1. KONFIGURASI SISTEM ---
st.set_page_config(
    page_title="MafaFX Premium",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (Branding MafaFX) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #d926a9, #bc20b6, #9b1fc0, #7623c8, #4728cd); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    div[data-testid="stMetric"] { background-color: rgba(0, 0, 0, 0.4) !important; border: 1px solid rgba(255, 255, 255, 0.2); padding: 15px; border-radius: 15px; }
    div.stButton > button { width: 100%; background: linear-gradient(to right, #FFD700, #E5C100) !important; color: black !important; font-weight: 800 !important; border-radius: 10px; border: none; padding: 12px 0px; margin-top: 10px; }
    
    /* Styling khusus Logo agar rata tengah */
    [data-testid="stSidebar"] [data-testid="stImage"] {
        text-align: center;
        display: block;
        margin-left: auto;
        margin-right: auto;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SISTEM LOGIN ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    
    if st.session_state["password_correct"]: return True

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        # --- LOGO DI HALAMAN LOGIN ---
        try:
            st.image("logo.png", width=200) # Pastikan file logo.png ada di GitHub
        except:
            st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
            
        st.markdown("<h3 style='text-align: center;'>Real-Time Intelligence</h3>", unsafe_allow_html=True)
        with st.form("credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            if st.form_submit_button("LOGIN"):
                user = st.session_state.get("username")
                pwd = st.session_state.get("password")
                # Cek credentials
                if user in st.secrets["passwords"] and st.secrets["passwords"][user] == pwd:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Username/Password Salah.")
    return False

if not check_password(): st.stop()

# ==========================================
# 3. ENGINE TWELVE DATA (REAL-TIME CORE)
# ==========================================

def get_twelvedata(symbol, interval, api_key):
    """Mengambil data Time Series dari Twelve Data."""
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=30"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Cek Error API
        if "status" in data and data["status"] == "error":
            return None
            
        return data.get("values", [])

    except Exception as e:
        return None

def process_data(values, inverse=False):
    """Memproses JSON menjadi DataFrame dan menghitung perubahan."""
    if not values: return None, None, None
    
    try:
        df = pd.DataFrame(values)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime').sort_index()
        df['close'] = df['close'].astype(float)
        
        current = df['close'].iloc[-1]
        prev = df['close'].iloc[-2]
        
        if inverse:
            # DXY Proxy (EUR/USD dibalik logikanya)
            change_pct = -1 * ((current - prev) / prev) * 100
            chart_data = (df['close'].pct_change().cumsum() * -1) # Chart dibalik
            display_price = (1 / current) * 100 
        else:
            change_pct = ((current - prev) / prev) * 100
            chart_data = df['close'].pct_change().cumsum()
            display_price = current
            
        return display_price, change_pct, chart_data
    except Exception as e:
        return None, None, None

@st.cache_data(ttl=60) # Cache 60 detik (Hemat Kuota API tapi Realtime)
def fetch_market_data():
    try:
        api_key = st.secrets["twelvedata"]["api_key"]
    except:
        st.error("API Key Twelve Data belum disetting di Secrets!")
        return None

    # 1. GOLD (Realtime)
    gold_raw = get_twelvedata("XAU/USD", "15min", api_key)
    
    # 2. DXY PROXY (EUR/USD Realtime)
    dxy_raw = get_twelvedata("EUR/USD", "15min", api_key)
    
    if not gold_raw or not dxy_raw: return None
    
    g_price, g_chg, g_chart = process_data(gold_raw)
    d_price, d_chg, d_chart = process_data(dxy_raw, inverse=True)
    
    return {
        'GOLD': {'price': g_price, 'chg': g_chg, 'chart': g_chart},
        'DXY': {'price': d_price, 'chg': d_chg, 'chart': d_chart} 
    }

# ==========================================
# 4. DASHBOARD TAMPILAN
# ==========================================

def main_dashboard():
    # --- SIDEBAR DENGAN LOGO ---
    with st.sidebar:
        try:
            st.image("logo.png", width=150) # LOGO DISINI
        except:
            st.write("### 👑 MafaFX")
        
        st.markdown("---")
        st.write(f"User: **{st.session_state.get('username')}**")
        st.caption("Status: Premium Active")
        
        if st.button("Logout"): 
            st.session_state["password_correct"] = False
            st.rerun()

    # Header Area
    col_head, col_status = st.columns([3, 1])
    with col_head:
        st.title("MafaFX Premium")
        st.caption("⚡ Powered by Twelve Data | Real-Time Execution")
    
    # Data Loading
    with st.spinner('Menghubungkan ke Exchange Real-Time...'):
        data = fetch_market_data()
        
        if data is None:
            st.warning("Menunggu data Real-Time... (Otomatis refresh dalam 1 menit)")
            if st.button("Paksa Refresh"):
                st.cache_data.clear()
                st.rerun()
            return

        gold = data['GOLD']
        dxy = data['DXY']
        
        # LOGIKA SINYAL FUNDAMENTAL
        score = 0
        signal_text = "NEUTRAL ⚪"
        
        if dxy['chg'] > 0.03: 
            score -= 5
            signal_text = "BEARISH PRESSURE 🔴"
        elif dxy['chg'] < -0.03: 
            score += 5
            signal_text = "BULLISH MOMENTUM 🟢"
            
        # Tampilan KOTAK SINYAL
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05)); 
                    padding:20px; border-radius:20px; text-align:center; border: 1px solid rgba(255,255,255,0.2); margin-bottom: 20px;">
            <h1 style="margin:0; text-shadow: 0 0 10px rgba(0,0,0,0.5);">{signal_text}</h1>
            <p style="margin:0; opacity:0.8; font-size: 1.2em;">Fundamental Score: {score}/10</p>
        </div>
        """, unsafe_allow_html=True)
        
        # METRIK HARGA
        c1, c2, c3 = st.columns(3)
        c1.metric("🥇 XAU/USD (Live)", f"${gold['price']:,.2f}", f"{gold['chg']:.2f}%")
        c2.metric("💵 USD Strength (Est)", f"{dxy['price']:.2f}", f"{dxy['chg']:.2f}%", delta_color="inverse")
        c3.metric("📊 Volatilitas", "Active", "Real-Time")
        
        # CHART KORELASI
        st.markdown("### 📉 Live Market Correlation")
        st.caption("Grafik ini membandingkan Emas vs Kekuatan Dolar. Jika garis Merah naik, garis Emas biasanya turun.")
        
        if gold['chart'] is not None and dxy['chart'] is not None:
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=gold['chart'], mode='lines', name='Gold', fill='tozeroy', line=dict(color='#FFD700', width=2)))
            fig.add_trace(go.Scatter(y=dxy['chart'], mode='lines', name='USD Strength', line=dict(color='#FF4B4B', dash='dot', width=2)))
            
            fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                              margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        
        # Footer Action
        if st.button("🔄 Refresh Data (Live)"):
            st.cache_data.clear()
            st.rerun()

if __name__ == "__main__":
    main_dashboard()


