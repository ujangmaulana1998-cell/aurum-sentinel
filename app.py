import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import requests # <-- Library yang Paling Stabil

# --- 1. KONFIGURASI SISTEM & CSS (Sama) ---
st.set_page_config(
    page_title="MafaFX Premium",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* CSS Branding */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #d926a9, #bc20b6, #9b1fc0, #7623c8, #4728cd); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    [data-testid="stImage"] { display: flex; justify-content: center; align-items: center; background-color: transparent !important; }
    img { background-color: transparent !important; max-width: 100%; height: auto; }
    div[data-testid="stMetric"] { background-color: rgba(0, 0, 0, 0.4) !important; border: 1px solid rgba(255, 255, 255, 0.2); padding: 15px; border-radius: 15px; backdrop-filter: blur(5px); box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); }
    .stTextInput > div > div > input { background-color: rgba(0, 0, 0, 0.5) !important; color: white !important; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3); }
    div.stButton > button { width: 100%; background: linear-gradient(to right, #FFD700, #E5C100) !important; color: black !important; font-weight: 800 !important; border-radius: 10px; border: none; padding: 12px 0px; margin-top: 10px; font-size: 16px; box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3); transition: all 0.3s ease; }
</style>
""", unsafe_allow_html=True)

# --- 3. SISTEM LOGIN MANUAL (Sama) ---
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
# AREA MEMBER MAFAFX (FINAL REQUESTS DATA FETCH)
# ==========================================

def get_alpha_vantage_data(symbol, function_name, api_key):
    """Fungsi pembantu untuk mengambil data dari Alpha Vantage menggunakan Requests."""
    if function_name == "FX_INTRADAY":
        # Untuk XAUUSD (Forex/Physical) dan DXY Proxy (EURUSD)
        url = f'https://www.alphavantage.co/query?function={function_name}&from_symbol={symbol[0]}&to_symbol={symbol[1]}&interval=15min&outputsize=compact&apikey={api_key}'
        key_data = 'Time Series FX (15min)'
    else: # Timeseries/Stock
        url = f'https://www.alphavantage.co/query?function={function_name}&symbol={symbol}&interval=15min&outputsize=compact&apikey={api_key}'
        key_data = 'Time Series (15min)'

    try:
        r = requests.get(url)
        r.raise_for_status() # Cek error HTTP
        data = r.json()
        
        if key_data in data:
            return data[key_data]
        elif 'Note' in data or 'Error Message' in data:
             # Menangkap error limit atau API key salah
            st.warning(f"Error API: {data.get('Note', data.get('Error Message', 'Batas API terlampaui atau simbol salah.'))}")
            return None
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error Koneksi HTTP: {e}")
        return None

def process_intraday_data(json_data, is_inverse=False):
    """Mengubah JSON data 15m menjadi DataFrame yang sudah di-clean."""
    if not json_data:
        return None, None

    df = pd.DataFrame.from_dict(json_data, orient='index')
    df = df.rename(columns={
        '1. open': 'open', '2. high': 'high', '3. low': 'low', '4. close': 'close', '5. volume': 'volume'
    }).astype(float)
    
    # Memastikan index adalah datetime dan diurutkan
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    if is_inverse:
        # Untuk DXY Proxy (EURUSD), kita balikkan logikanya
        df['close'] = 100 + (100 - df['close'])

    # Menghitung data normalisasi untuk chart korelasi
    norm_data = df['close'].pct_change().cumsum()
    
    return df, norm_data

@st.cache_data(ttl=60)
def fetch_financial_data():
    API_KEY = st.secrets["alpha_vantage"]["api_key"]
    
    # 1. AMBIL DATA DENGAN REQUESTS
    # Gold (XAUUSD)
    gold_json = get_alpha_vantage_data(['XAU', 'USD'], 'FX_INTRADAY', API_KEY)
    
    # DXY Proxy (EURUSD) - Kita pakai EURUSD dan balikkan logikanya
    dxy_json = get_alpha_vantage_data(['EUR', 'USD'], 'FX_INTRADAY', API_KEY)
    
    # US10Y Yield dan Crude Oil tetap N/A karena tidak tersedia gratis
    
    # 2. PROSES DATA
    df_gold, norm_gold = process_intraday_data(gold_json)
    df_dxy, norm_dxy = process_intraday_data(dxy_json, is_inverse=True)

    if df_gold is None or df_dxy is None:
        return None, None, None # Gagal mengambil data

    # Ambil nilai terakhir (Current) dan sebelumnya (Prev)
    curr_values = pd.Series({
        'GOLD': df_gold['close'].iloc[-1],
        'DXY': df_dxy['close'].iloc[-1],
        'OIL': 0.00, 
        'YIELD': 0.00
    })
    
    prev_values = pd.Series({
        'GOLD': df_gold['close'].iloc[-2],
        'DXY': df_dxy['close'].iloc[-2],
        'OIL': 0.00,
        'YIELD': 0.00
    })

    # DATA HISTORIS untuk Chart
    df_history = pd.DataFrame({
        'GOLD': norm_gold,
        'DXY': norm_dxy,
        'YIELD': norm_gold * 0 # Placeholder untuk grafik
    }).dropna()

    # Pastikan data korelasi memiliki indeks yang sama
    df_history = df_history.loc[df_history.index.intersection(df_history.index)]

    return curr_values, prev_values, df_history

def analyze_market_regime(curr, prev):
    # Logika analisis dipertahankan, Yield/Oil diabaikan
    dxy_chg = ((curr['DXY'] - prev['DXY']) / prev['DXY']) * 100 if prev['DXY'] != 0 else 0
    
    score = 0; reasons = []
    
    if dxy_chg > 0.01: score -= 4; reasons.append("USD Menguat (Bearish Gold)")
    elif dxy_chg < -0.01: score += 4; reasons.append("USD Melemah (Bullish Gold)")

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
            
            if curr is None: return 

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
