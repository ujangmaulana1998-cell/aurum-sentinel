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

# --- 2. SISTEM LOGIN MANUAL ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if "username" not in st.session_state: st.session_state["username"] = ""

    def password_entered():
        if "password" in st.session_state and st.session_state["username"] in st.secrets["passwords"]:
            if st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]: 
                st.session_state["password_correct"] = True
            else: st.session_state["password_correct"] = False
        else: st.session_state["password_correct"] = False

    if st.session_state["password_correct"]: return True

    # Tampilan Login
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Premium Login</h3>", unsafe_allow_html=True)
        with st.form("credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            if st.form_submit_button("MASUK / LOGIN"): password_entered()
        if "password_correct" in st.session_state and not st.session_state["password_correct"]: 
            st.error("🔒 Username atau Password salah.")
    return False

if not check_password(): st.stop()

# ==========================================
# 3. ENGINE PENGAMBIL DATA (SMART FETCH)
# ==========================================

def get_data_from_api(symbol_from, symbol_to, api_key):
    """Mengambil data dengan penanganan error visual."""
    url = f'https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol={symbol_from}&to_symbol={symbol_to}&interval=15min&outputsize=compact&apikey={api_key}'
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # --- DIAGNOSA ERROR API ---
        if "Error Message" in data:
            st.error(f"❌ **API Key Salah/Tidak Valid:** Cek Secrets Anda. ({symbol_from}{symbol_to})")
            return None
        if "Note" in data:
            st.warning(f"⚠️ **Batas API Tercapai:** {data['Note']}")
            return None
        if "Time Series FX (15min)" not in data:
            st.error(f"❌ **Data Tidak Ditemukan:** Format JSON berubah atau simbol salah.")
            st.write(data) # Tampilkan mentahan untuk debug
            return None
            
        return data["Time Series FX (15min)"]

    except Exception as e:
        st.error(f"❌ **Koneksi Gagal:** {e}")
        return None

def process_data(json_data, inverse=False):
    if not json_data: return None, None
    
    df = pd.DataFrame.from_dict(json_data, orient='index')
    df = df.rename(columns={'1. open': 'open', '2. high': 'high', '3. low': 'low', '4. close': 'close'})
    df['close'] = df['close'].astype(float)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    current = df['close'].iloc[-1]
    prev = df['close'].iloc[-2]
    
    if inverse: # Untuk DXY Proxy (EURUSD dibalik)
        current = 100 + (100 - current)
        prev = 100 + (100 - prev)
        norm_data = (df['close'].pct_change().cumsum() * -1)
    else:
        norm_data = df['close'].pct_change().cumsum()
        
    return current, prev, norm_data

# Cache diperpanjang ke 5 menit (300s) agar tidak kena limit
@st.cache_data(ttl=300)
def fetch_all_data():
    api_key = st.secrets["alpha_vantage"]["api_key"]
    
    # 1. Ambil XAUUSD
    gold_json = get_data_from_api("XAU", "USD", api_key)
    
    # 2. Ambil EURUSD (Proxy DXY)
    dxy_json = get_data_from_api("EUR", "USD", api_key)
    
    if not gold_json or not dxy_json:
        return None # Berhenti jika salah satu gagal

    # Proses Data
    g_curr, g_prev, g_chart = process_data(gold_json)
    d_curr, d_prev, d_chart = process_data(dxy_json, inverse=True)
    
    return {
        'GOLD': {'curr': g_curr, 'prev': g_prev, 'chart': g_chart},
        'DXY': {'curr': d_curr, 'prev': d_prev, 'chart': d_chart}
    }

# ==========================================
# 4. DASHBOARD UTAMA
# ==========================================

def main_dashboard():
    # Sidebar Info
    with st.sidebar:
        st.image("logo.png", width=100) if st.sidebar.button("Show Logo") else None
        st.write(f"User: **{st.session_state['username']}**")
        if st.button("Logout"): st.session_state["password_correct"] = False; st.rerun()

    # Header
    st.title("MafaFX Premium Dashboard")
    st.caption("Realtime Sentinel | Alpha Vantage Engine")
    st.markdown("---")

    # Fetch Data dengan Spinner
    with st.spinner('Menghubungkan ke Server Alpha Vantage...'):
        data = fetch_all_data()

        # JIKA DATA KOSONG (Ini yang mencegah layar blank)
        if data is None:
            st.warning("⚠️ Data belum tersedia. Silakan tunggu 1-2 menit lalu tekan tombol Refresh di bawah.")
            if st.button("Coba Lagi (Refresh)"):
                st.cache_data.clear()
                st.rerun()
            return # Stop eksekusi agar tidak error di bawah

        # Logika Bisnis
        curr = data
        gold_chg = ((curr['GOLD']['curr'] - curr['GOLD']['prev']) / curr['GOLD']['prev']) * 100
        dxy_chg = ((curr['DXY']['curr'] - curr['DXY']['prev']) / curr['DXY']['prev']) * 100
        
        # Scoring Sederhana
        score = 0
        status = "NEUTRAL ⚪"
        if dxy_chg > 0.01: score -= 5; status = "SELL BIAS 🔴"
        elif dxy_chg < -0.01: score += 5; status = "BUY BIAS 🟢"

        # Tampilan Utama
        col_score, col_info = st.columns([1, 2])
        with col_score:
            st.markdown(f"""<div style="background:rgba(0,0,0,0.5); padding:20px; border-radius:10px; text-align:center; border:1px solid white;">
            <h2>{status}</h2>
            <h4>Score: {score}/10</h4></div>""", unsafe_allow_html=True)
        
        with col_info:
            st.info(f"**Analisis:** DXY bergerak {dxy_chg:.3f}%. Korelasi invers dengan Gold aktif.")

        st.markdown("<br>", unsafe_allow_html=True)

        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🥇 GOLD", f"${curr['GOLD']['curr']:,.2f}", f"{gold_chg:.2f}%")
        c2.metric("💵 DXY (Proxy)", f"{curr['DXY']['curr']:.2f}", f"{dxy_chg:.2f}%", delta_color="inverse")
        c3.metric("Yield", "N/A", "Premium Only")
        c4.metric("Oil", "N/A", "Premium Only")

        # Chart
        st.markdown("### 📉 Live Correlation")
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=curr['GOLD']['chart'], mode='lines', name='Gold', fill='tozeroy', line=dict(color='#FFD700')))
        fig.add_trace(go.Scatter(y=curr['DXY']['chart'], mode='lines', name='DXY (Inv)', line=dict(color='red', dash='dot')))
        fig.update_layout(height=400, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
        
        # Tombol Refresh
        if st.button("🔄 Refresh Data (Tunggu 2 Menit per Klik)"):
            st.cache_data.clear()
            st.rerun()

if __name__ == "__main__":
    main_dashboard()
