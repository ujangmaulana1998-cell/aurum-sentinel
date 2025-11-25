import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from alpha_vantage.foreign_exchange import ForeignExchange
from alpha_vantage.timeseries import TimeSeries

# --- 1. KONFIGURASI SISTEM ---
st.set_page_config(
    page_title="MafaFX Premium",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS (Branding) ---
st.markdown("""
<style>
    /* CSS Branding */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #d926a9, #bc20b6, #9b1fc0, #7623c8, #4728cd); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    [data-testid="stImage"] { display: flex; justify-content: center; align-items: center; background-color: transparent !important; }
    img { background-color: transparent !important; max-width: 100%; height: auto; }
    [data-testid="stForm"] { background-color: rgba(0, 0, 0, 0.2); padding: 30px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37); backdrop-filter: blur(4px); }
    div[data-testid="stMetric"] { background-color: rgba(0, 0, 0, 0.4) !important; border: 1px solid rgba(255, 255, 255, 0.2); padding: 15px; border-radius: 15px; backdrop-filter: blur(5px); box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); }
    .stTextInput > div > div > input { background-color: rgba(0, 0, 0, 0.5) !important; color: white !important; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3); }
    div.stButton > button { width: 100%; background: linear-gradient(to right, #FFD700, #E5C100) !important; color: black !important; font-weight: 800 !important; border-radius: 10px; border: none; padding: 12px 0px; margin-top: 10px; font-size: 16px; box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3); transition: all 0.3s ease; }
</style>
""", unsafe_allow_html=True)

# --- 3. SISTEM LOGIN MANUAL ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if "username" not in st.session_state: st.session_state["username"] = ""
    def password_entered():
        if "password" in st.session_state and st.session_state["username"] in st.secrets["passwords"]:
            if st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]: st.session_state["password_correct"] = True
            else: st.session_state["password_correct"] = False
        else: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        try: st.image("logo.png", width=180)
        except: st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; margin-top:10px; margin-bottom: 20px;'>Premium Login</h3>", unsafe_allow_html=True)
        with st.form("credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            submitted = st.form_submit_button("MASUK / LOGIN")
            if submitted: password_entered()
        if "password_correct" in st.session_state and not st.session_state["password_correct"] and submitted: st.error("🔒 Username atau Password salah.")
        st.markdown("<p style='text-align: center; font-size: 0.8em; opacity: 0.8; margin-top: 20px;'>© MafaFX Proprietary System.</p>", unsafe_allow_html=True)
    return False

if not check_password():
    st.stop()

# ==========================================
# AREA MEMBER MAFAFX (ALPHA VANTAGE DATA FETCH)
# ==========================================

@st.cache_data(ttl=60)
def fetch_financial_data():
    API_KEY = st.secrets["alpha_vantage"]["api_key"]
    ts = TimeSeries(key=API_KEY, output_format='pandas')
    fx = ForeignExchange(key=API_KEY, output_format='pandas')
    
    # 1. AMBIL DATA GOLD (XAUUSD) & DXY PROXY
    try:
        # GOLD (XAUUSD)
        gold_data, meta_gold = fx.get_currency_exchange_intraday(from_symbol='XAU', to_symbol='USD', interval='15min', outputsize='compact')
        gold_data.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # DXY PROXY (EURUSD dibalik)
        dxy_proxy, meta_dxy = fx.get_currency_exchange_intraday(from_symbol='EUR', to_symbol='USD', interval='15min', outputsize='compact')
        dxy_proxy.columns = ['open', 'high', 'low', 'close', 'volume']
        
    except Exception as e:
        # Menangkap error batas API limit atau koneksi
        if 'You have exceeded the maximum allowed calls' in str(e):
            st.error("🚨 Batas Panggilan API Alpha Vantage Terlampaui. Coba lagi dalam 1 menit.")
        else:
            st.error(f"Error Koneksi Data (Alpha Vantage). Cek API Key atau Batas Harian. Detail: {e}")
        return None, None, None

    # 2. KOMPILASI DATA & LOGIKA
    
    # Ambil harga terakhir
    current_gold = gold_data['close'].iloc[-1]
    current_dxy_proxy = 100 + (100 - dxy_proxy['close'].iloc[-1])
    
    # Ambil harga sebelumnya
    prev_gold = gold_data['close'].iloc[-2]
    prev_dxy_proxy = 100 + (100 - dxy_proxy['close'].iloc[-2])

    # KUMPULKAN CURRENT VALUES
    curr_values = pd.Series({
        'GOLD': current_gold,
        'DXY': current_dxy_proxy,
        'OIL': 0.00,
        'YIELD': 0.00
    })
    
    # KUMPULKAN PREVIOUS VALUES
    prev_values = pd.Series({
        'GOLD': prev_gold,
        'DXY': prev_dxy_proxy,
        'OIL': 0.00,
        'YIELD': 0.00
    })

    # DATA HISTORIS untuk Chart
    norm_gold = gold_data['close'].pct_change().cumsum()
    norm_dxy = dxy_proxy['close'].pct_change().cumsum() * -1

    df_history = pd.DataFrame({
        'GOLD': norm_gold,
        'DXY': norm_dxy,
        'YIELD': norm_gold * 0 
    }).dropna()

    return curr_values, prev_values, df_history

def analyze_market_regime(curr, prev):
    dxy_chg = ((curr['DXY'] - prev['DXY']) / prev['DXY']) * 100 if prev['DXY'] != 0 else 0
    
    score = 0; reasons = []
    
    if dxy_chg > 0.01: score -= 4; reasons.append("USD Menguat (Bearish Gold)")
    elif dxy_chg < -0.01: score += 4; reasons.append("USD Melemah (Bullish Gold)")

    # Logika Yield/Oil diabaikan karena data = 0
    if score >= 4: return "STRONG BUY 🚀", "bias-bullish", score, reasons
    elif score >= 2: return "BUY 🟢", "bias-bullish", score, reasons
    elif score <= -4: return "STRONG SELL 🩸", "bias-bearish", score, reasons
    elif score <= -2: return "SELL 🔴", "bias-bearish", score, reasons
    else: return "NEUTRAL ⚪", "bias-neutral", score, reasons

def main_dashboard():
    username = st.session_state.get("username", "Klien")
    
    with st.sidebar:
        try: st.image("logo.png", width=100)
        except: pass
        st.write(f"Logged in as: **{username}**")
        if st.button('Logout'): st.session_state["password_correct"] = False; st.rerun()
        st.write("---") 

    col_head_logo, col_head_text = st.columns([1, 6])
    with col_head_logo:
         try: st.image("logo.png", width=120)
         except: st.markdown("<h1>👑</h1>", unsafe_allow_html=True)
    with col_head_text:
        st.title("MafaFX Premium Dashboard")
        st.caption(f"Realtime XAUUSD Sentinel | Welcome, {username}")
    st.markdown("---")
    
    with st.spinner('Analisis Market sedang berjalan...'):
        try:
            curr, prev, norm_data = fetch_financial_data()
            
            if curr is None: 
                return 

            # Perhitungan %
            gold_pct = ((curr['GOLD'] - prev['GOLD']) / prev['GOLD']) * 100 if prev['GOLD'] != 0 else 0
            dxy_pct = ((curr['DXY'] - prev['DXY']) / prev['DXY']) * 100 if prev['DXY'] != 0 else 0

            bias_text, css_class, final_score, reason_list = analyze_market_regime(curr, prev)

            # 1. BIAS SUMMARY
            st.markdown(f"""<div style="padding:20px; border-radius:15px; text-align:center; border:2px solid rgba(255,255,255,0.3); background: rgba(0,0,0,0.5);"><div class="{css_class}" style="background: transparent; border: none;"><h2 style="margin:0; color:white;">{bias_text}</h2><h4 style="margin:0; color:white;">Score: {final_score}/10</h4></div></div>""", unsafe_allow_html=True)
            with st.expander("📊 Analisis Fundamental:"):
                 if reason_list:
                    for r in reason_list: st.write(f"- {r}")
                 else: st.write("- Pasar konsolidasi.")
            st.markdown("<br>", unsafe_allow_html=True)

            # 2. METRIK ANGKA
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🥇 GOLD (XAU)", f"${curr['GOLD']:,.2f}", f"{gold_pct:.2f}%")
            c2.metric("💵 DXY (Proxy)", f"{curr['DXY']:.2f}", f"{dxy_pct:.2f}%", delta_color="inverse")
            c3.metric("📈 YIELD", "N/A", "N/A", delta_color="off")
            c4.metric("🛢️ OIL", "N/A", "N/A", delta_color="off")

            # 3. CHART KORELASI
            st.markdown("### 📉 Visualisasi Korelasi")
            
            if norm_data is not None and len(norm_data) > 2:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['GOLD'], name='GOLD', fill='tozeroy', line=dict(color='#FFD700')))
                fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['DXY'], name='DXY (Inverse)', line=dict(color='#FF4B4B', dash='dot')))
                
                fig.update_layout(template="plotly_dark", height=450, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                 st.warning("Data historis tidak mencukupi untuk visualisasi korelasi.")
            
            if st.button('🔄 Refresh Data'): st.cache_data.clear(); st.rerun()

        except Exception as e: 
            st.error(f"Error: {e}")

if __name__ == "__main__":
    main_dashboard()

