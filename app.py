import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. KONFIGURASI SISTEM ---
st.set_page_config(
    page_title="MafaFX Premium",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS (STYLE & GRADASI FINAL) ---
st.markdown("""
<style>
    /* HILANGKAN ELEMENT BAWAAN */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* BACKGROUND GRADASI PINK-BIRU MAFAFX */
    .stApp {
        background-image: linear-gradient(to right bottom, #d926a9, #bc20b6, #9b1fc0, #7623c8, #4728cd);
        background-attachment: fixed;
    }

    /* TEKS PUTIH */
    h1, h2, h3, h4, h5, h6, p, span, div, label {
        color: #ffffff !important;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* --- PERBAIKAN TAMPILAN LOGO --- */
    /* Memastikan container gambar di tengah dan transparan */
    [data-testid="stImage"] {
        display: flex;
        justify-content: center;
        align-items: center;
        background-color: transparent !important;
    }
    /* Memastikan gambar itu sendiri tidak punya background */
    img {
        background-color: transparent !important;
        max-width: 100%; /* Agar responsif */
        height: auto;
    }
    
    /* STYLE FORM LOGIN (Dibuat transparan & rapi) */
    [data-testid="stForm"] {
        background-color: rgba(0, 0, 0, 0.2);
        padding: 30px;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        backdrop-filter: blur(4px);
    }
    
    /* STYLE INPUT FIELD */
    .stTextInput > div > div > input {
        background-color: rgba(0, 0, 0, 0.5) !important;
        color: white !important;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    /* STYLE TOMBOL LOGIN */
    div.stButton > button {
        width: 100%;
        background: linear-gradient(to right, #FFD700, #E5C100);
        color: black !important;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        padding: 12px 0px;
        margin-top: 10px;
        font-size: 16px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    div.stButton > button:hover {
         background: linear-gradient(to right, #fff, #ddd);
         box-shadow: 0 6px 10px rgba(0,0,0,0.5);
    }

    /* STYLE KARTU METRIK DASHBOARD */
    div[data-testid="stMetric"] {
        background-color: rgba(0, 0, 0, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 15px;
        border-radius: 15px;
        backdrop-filter: blur(5px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SISTEM LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    def password_entered():
        if st.session_state["username"] in st.secrets["passwords"]:
            if st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
                st.session_state["password_correct"] = True
            else:
                st.session_state["password_correct"] = False
        else:
            st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # --- TAMPILAN HALAMAN LOGIN ---
    # Menggunakan 3 kolom agar form berada di tengah
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        # Menampilkan Logo
        try:
            # Lebar disesuaikan agar proporsional
            st.image("logo.png", width=180) 
        except:
             st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; margin-top:10px; margin-bottom: 20px;'>Premium Login</h3>", unsafe_allow_html=True)

        # FORM LOGIN DALAM KOTAK TRANSPARAN
        with st.form("credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            submitted = st.form_submit_button("MASUK / LOGIN")
            if submitted: password_entered()
        
        if "password_correct" in st.session_state and not st.session_state["password_correct"] and "username" in st.session_state and submitted:
            st.error("🔒 Username atau Password salah.")
            
        st.markdown("<p style='text-align: center; font-size: 0.8em; opacity: 0.8; margin-top: 20px;'>© MafaFX Proprietary System.</p>", unsafe_allow_html=True)
    return False

if not check_password():
    st.stop()

# ==========================================
# AREA MEMBER MAFAFX (DASHBOARD)
# ==========================================

@st.cache_data(ttl=60)
def fetch_financial_data():
    tickers = ['GC=F', '^TNX', 'DX-Y.NYB', 'CL=F']
    data = yf.download(tickers, period='5d', interval='15m', progress=False)
    df = data['Close']
    df = df.ffill(); df = df.dropna()
    return df

def analyze_market_regime(dxy_chg, yield_chg, oil_chg):
    score = 0; reasons = []
    if dxy_chg > 0.05: score -= 4; reasons.append("USD Menguat (Bearish Gold)")
    elif dxy_chg < -0.05: score += 4; reasons.append("USD Melemah (Bullish Gold)")
    if yield_chg > 0.5: score -= 5; reasons.append("Yield Melonjak (Bearish Gold)")
    elif yield_chg < -0.5: score += 5; reasons.append("Yield Turun (Bullish Gold)")
    if oil_chg > 1.0: score += 2; reasons.append("Minyak Naik (Inflasi Hedge)")
    elif oil_chg < -1.0: score -= 1 
        
    if score >= 6: return "STRONG BUY 🚀", "bias-bullish", score, reasons
    elif score >= 2: return "BUY 🟢", "bias-bullish", score, reasons
    elif score <= -6: return "STRONG SELL 🩸", "bias-bearish", score, reasons
    elif score <= -2: return "SELL 🔴", "bias-bearish", score, reasons
    else: return "NEUTRAL ⚪", "bias-neutral", score, reasons

def main():
    with st.sidebar:
        try: st.image("logo.png", width=100)
        except: pass
        st.write(f"User: **{st.session_state['username']}**")
        if st.button("Logout"): st.session_state["password_correct"] = False; st.rerun()

    # HEADER DASHBOARD
    col_head_logo, col_head_text = st.columns([1, 6])
    with col_head_logo:
         try: st.image("logo.png", width=120)
         except: st.markdown("<h1>👑</h1>", unsafe_allow_html=True)
    with col_head_text:
        st.title("MafaFX Premium Dashboard")
        st.caption(f"Realtime XAUUSD Sentinel | Welcome, {st.session_state['username']}")
    st.markdown("---")
    
    with st.spinner('Analisis Market sedang berjalan...'):
        try:
            prices = fetch_financial_data()
            if len(prices) < 2: st.warning("Market Closed."); return
            curr = prices.iloc[-1]; prev = prices.iloc[-2]
            dxy_val = curr.get('DX-Y.NYB'); dxy_prev = prev.get('DX-Y.NYB')
            dxy_pct = ((dxy_val - dxy_prev) / dxy_prev) * 100 if pd.notna(dxy_val) and dxy_prev != 0 else 0
            yield_val = curr.get('^TNX'); yield_prev = prev.get('^TNX')
            yield_pct = ((yield_val - yield_prev) / yield_prev) * 100 if pd.notna(yield_val) and yield_prev != 0 else 0
            oil_val = curr.get('CL=F'); oil_prev = prev.get('CL=F')
            oil_pct = ((oil_val - oil_prev) / oil_prev) * 100 if pd.notna(oil_val) and oil_prev != 0 else 0
            gold_val = curr.get('GC=F'); gold_prev = prev.get('GC=F')
            gold_pct = ((gold_val - gold_prev) / gold_prev) * 100 if pd.notna(gold_val) and gold_prev != 0 else 0
            bias_text, css_class, final_score, reason_list = analyze_market_regime(dxy_pct, yield_pct, oil_pct)

            col_bias, col_detail = st.columns([1, 2])
            st.markdown(f"""<div style="padding:20px; border-radius:15px; text-align:center; border:2px solid rgba(255,255,255,0.3); background: rgba(0,0,0,0.5);"><div class="{css_class}" style="background: transparent; border: none;"><h2 style="margin:0; color:white;">{bias_text}</h2><h4 style="margin:0; color:white;">Score: {final_score}/10</h4></div></div>""", unsafe_allow_html=True)
            with col_detail:
                st.info("📊 **Analisis Fundamental:**")
                if reason_list:
                    for r in reason_list: st.write(f"- {r}")
                else: st.write("- Pasar konsolidasi (Wait & See).")
            st.markdown("<br>", unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🥇 GOLD (XAU)", f"${gold_val:,.2f}", f"{gold_pct:.2f}%")
            c2.metric("💵 USD Index", f"{dxy_val:.2f}", f"{dxy_pct:.2f}%", delta_color="inverse")
            c3.metric("📈 US10Y Yield", f"{yield_val:.3f}%", f"{yield_pct:.2f}%", delta_color="inverse")
            c4.metric("🛢️ Crude Oil", f"${oil_val:.2f}", f"{oil_pct:.2f}%")

            st.markdown("### 📉 Visualisasi Korelasi")
            norm_data = prices.pct_change().cumsum()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['GC=F'], name='GOLD', fill='tozeroy', line=dict(color='#FFD700')))
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['^TNX'], name='Yield', line=dict(color='#FF4B4B', dash='dot')))
            fig.update_layout(template="plotly_dark", height=450, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
            if st.button('🔄 Refresh Data'): st.cache_data.clear(); st.rerun()

        except Exception as e: st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
