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
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #d926a9, #bc20b6, #9b1fc0, #7623c8, #4728cd); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    div[data-testid="stMetric"] { background-color: rgba(0, 0, 0, 0.4) !important; border: 1px solid rgba(255, 255, 255, 0.2); padding: 15px; border-radius: 15px; }
    div.stButton > button { width: 100%; background: linear-gradient(to right, #FFD700, #E5C100) !important; color: black !important; font-weight: 800 !important; border-radius: 10px; border: none; padding: 12px 0px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. SISTEM LOGIN ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Real-Time Intelligence</h3>", unsafe_allow_html=True)
        with st.form("credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            if st.form_submit_button("LOGIN"):
                user = st.session_state.get("username")
                pwd = st.session_state.get("password")
                if user in st.secrets["passwords"] and st.secrets["passwords"][user] == pwd:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Username/Password Salah.")
    return False

if not check_password(): st.stop()

# ==========================================
# 3. ENGINE TWELVE DATA (REAL-TIME)
# ==========================================

def get_twelvedata(symbol, interval, api_key):
    """Mengambil data dari Twelve Data API."""
    # Endpoint Time Series
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=50"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if "status" in data and data["status"] == "error":
            st.error(f"API Error ({symbol}): {data['message']}")
            return None
            
        return data["values"] # List of dictionaries

    except Exception as e:
        st.error(f"Koneksi Gagal: {e}")
        return None

def process_twelvedata(values, inverse=False):
    if not values: return None, None, None
    
    # Konversi ke DataFrame
    df = pd.DataFrame(values)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime').sort_index()
    df['close'] = df['close'].astype(float)
    
    current = df['close'].iloc[-1]
    prev = df['close'].iloc[-2]
    
    if inverse:
        # Untuk DXY Proxy (EUR/USD dibalik)
        # Rumus: 1/EURUSD * faktor (atau simplifikasi 100 + (100-harga) untuk visual)
        # Kita gunakan pendekatan invers persentase sederhana untuk visualisasi
        current_inv = 1 / current
        prev_inv = 1 / prev
        pct_change = ((current_inv - prev_inv) / prev_inv) * 100
        
        # Normalisasi chart (Inverted)
        chart_data = (df['close'].pct_change().cumsum() * -1)
        
        # Tampilkan harga sebagai "Proxy Index" (Bukan harga EURUSD asli)
        return round(current_inv * 100, 2), pct_change, chart_data
    
    else:
        pct_change = ((current - prev) / prev) * 100
        chart_data = df['close'].pct_change().cumsum()
        return current, pct_change, chart_data

@st.cache_data(ttl=60) # Cache 60 detik (Realtime tapi hemat kuota)
def fetch_market_data():
    api_key = st.secrets["twelvedata"]["api_key"]
    
    # 1. GOLD (XAU/USD) - Realtime Forex
    gold_raw = get_twelvedata("XAU/USD", "15min", api_key)
    
    # 2. DXY Proxy (EUR/USD) - Realtime Forex
    # Twelve Data DXY asli berbayar, kita pakai EUR/USD (komponen terbesar DXY) dan kita balik
    dxy_raw = get_twelvedata("EUR/USD", "15min", api_key)
    
    if not gold_raw or not dxy_raw: return None
    
    # Proses Data
    g_price, g_chg, g_chart = process_twelvedata(gold_raw)
    d_price, d_chg, d_chart = process_twelvedata(dxy_raw, inverse=True)
    
    return {
        'GOLD': {'price': g_price, 'chg': g_chg, 'chart': g_chart},
        'DXY': {'price': d_price, 'chg': d_chg, 'chart': d_chart}
    }

# ==========================================
# 4. DASHBOARD UTAMA
# ==========================================

def main_dashboard():
    # Header
    col_logo, col_title = st.columns([1, 5])
    with col_title:
        st.title("MafaFX Premium")
        st.caption("⚡ Powered by Twelve Data (Real-Time)")
    
    with st.spinner('Menghubungkan ke Server Real-Time...'):
        data = fetch_market_data()
        
        if data is None:
            st.warning("Gagal mengambil data. Cek API Key atau tunggu 1 menit.")
            if st.button("Coba Lagi"): st.cache_data.clear(); st.rerun()
            return

        # Ambil Data
        gold = data['GOLD']
        dxy = data['DXY'] # Ini adalah DXY Proxy (Inverted EURUSD)
        
        # LOGIKA SINYAL (Simple)
        # Jika DXY Turun -> Gold Bullish
        # Jika DXY Naik -> Gold Bearish
        
        score = 0
        signal = "NEUTRAL ⚪"
        
        if dxy['chg'] > 0.05: # USD Menguat
            score -= 5
            signal = "BEARISH BIAS 🔴"
        elif dxy['chg'] < -0.05: # USD Melemah
            score += 5
            signal = "BULLISH BIAS 🟢"
            
        # TAMPILAN UTAMA
        st.markdown("---")
        
        # Kotak Signal
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.1); padding:20px; border-radius:15px; text-align:center; border: 1px solid rgba(255,255,255,0.2);">
            <h1 style="margin:0;">{signal}</h1>
            <p style="margin:0; opacity:0.7;">Correlation Score: {score}/10</p>
        </div>
        <br>
        """, unsafe_allow_html=True)
        
        # Metrik
        c1, c2, c3 = st.columns(3)
        c1.metric("🥇 XAU/USD (Real-Time)", f"${gold['price']:,.2f}", f"{gold['chg']:.2f}%")
        c2.metric("💵 USD Strength (Proxy)", f"{dxy['price']:.2f}", f"{dxy['chg']:.2f}%", delta_color="inverse")
        c3.metric("📊 Market State", "Active", "Volatile")
        
        # Chart Korelasi
        st.markdown("### 📉 Live Correlation Chart")
        
        # Buat DataFrame gabungan untuk chart yang rapi
        # Kita perlu menyamakan index (datetime)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=gold['chart'], mode='lines', name='Gold', fill='tozeroy', line=dict(color='#FFD700')))
        fig.add_trace(go.Scatter(y=dxy['chart'], mode='lines', name='USD Inv.', line=dict(color='red', dash='dot')))
        
        fig.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)
        
        # Tombol Refresh
        if st.button("🔄 Refresh Real-Time Data"):
            st.cache_data.clear()
            st.rerun()

    # Sidebar Logout
    with st.sidebar:
        st.write(f"User: **{st.session_state.get('username')}**")
        if st.button("Logout"): 
            st.session_state["password_correct"] = False
            st.rerun()

if __name__ == "__main__":
    main_dashboard()
