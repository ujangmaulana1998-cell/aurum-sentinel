import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. KONFIGURASI SISTEM ---
st.set_page_config(
    page_title="Aurum Sentinel - Member Area",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS untuk Tampilan Login & Dashboard
st.markdown("""
<style>
    .metric-card { background-color: #1E1E1E; border: 1px solid #333; padding: 20px; border-radius: 10px; color: white; }
    .bias-bullish { background-color: #0c4a28; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #28a745; }
    .bias-bearish { background-color: #5c1818; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #dc3545; }
    .bias-neutral { background-color: #3e3e3e; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #6c757d; }
    /* Style untuk kotak login */
    .stTextInput > div > div > input { color: #fff; }
</style>
""", unsafe_allow_html=True)

# --- 2. SISTEM KEAMANAN (LOGIN SYSTEM) ---
def check_password():
    """Returns `True` if the user had a correct password."""

    # Jika user belum login
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Fungsi validasi input
    def password_entered():
        # Cek apakah username ada di database rahasia
        if st.session_state["username"] in st.secrets["passwords"]:
            # Cek apakah password cocok
            if st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
                st.session_state["password_correct"] = True
                # Hapus password dari memori sesi demi keamanan
                del st.session_state["password"]  
            else:
                st.session_state["password_correct"] = False
        else:
            st.session_state["password_correct"] = False

    # Jika sudah login, return True
    if st.session_state["password_correct"]:
        return True

    # TAMPILAN HALAMAN LOGIN
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<br><br><h1 style='text-align: center;'>🔒 XAUUSD Sentinel</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Akses Premium Only. Silakan Login.</p>", unsafe_allow_html=True)
        
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        
        if "password_correct" in st.session_state and not st.session_state["password_correct"] and "username" in st.session_state:
            st.error("😕 Username atau Password salah.")
            
        st.markdown("<p style='text-align: center; font-size: 0.8em; color: grey;'>Hubungi Admin untuk berlangganan.</p>", unsafe_allow_html=True)

    return False

# Jika password salah/belum login, berhenti di sini.
if not check_password():
    st.stop()

# ==========================================
# AREA DI BAWAH INI HANYA BISA DIBACA MEMBER
# ==========================================

# --- 3. ENGINE PENGAMBIL DATA (BACKEND) ---
@st.cache_data(ttl=60)
def fetch_financial_data():
    tickers = ['GC=F', '^TNX', 'DX-Y.NYB', 'CL=F']
    data = yf.download(tickers, period='5d', interval='15m', progress=False)
    df = data['Close']
    df = df.ffill() # Fix NaN
    df = df.dropna()
    return df

# --- 4. ENGINE ANALISIS ---
def analyze_market_regime(dxy_chg, yield_chg, oil_chg):
    score = 0
    reasons = []

    if dxy_chg > 0.05: score -= 4; reasons.append("USD Menguat (Bearish Gold)")
    elif dxy_chg < -0.05: score += 4; reasons.append("USD Melemah (Bullish Gold)")

    if yield_chg > 0.5: score -= 5; reasons.append("Yield Obligasi Melonjak (Bearish Gold)")
    elif yield_chg < -0.5: score += 5; reasons.append("Yield Obligasi Turun (Bullish Gold)")
        
    if oil_chg > 1.0: score += 2; reasons.append("Minyak Naik (Inflasi Hedge)")
    elif oil_chg < -1.0: score -= 1 
        
    if score >= 6: return "STRONG BUY 🚀", "bias-bullish", score, reasons
    elif score >= 2: return "BUY 🟢", "bias-bullish", score, reasons
    elif score <= -6: return "STRONG SELL 🩸", "bias-bearish", score, reasons
    elif score <= -2: return "SELL 🔴", "bias-bearish", score, reasons
    else: return "NEUTRAL ⚪", "bias-neutral", score, reasons

# --- 5. TAMPILAN DASHBOARD UTAMA ---
def main():
    # Tombol Logout di Sidebar
    with st.sidebar:
        st.write(f"Logged in as: **{st.session_state['username']}**")
        if st.button("Logout"):
            st.session_state["password_correct"] = False
            st.rerun()

    st.title("👑 AURUM SENTINEL: Premium Dashboard")
    st.caption(f"Live Market Data | Welcome, {st.session_state['username']}")
    
    with st.spinner('Mengambil data market premium...'):
        try:
            prices = fetch_financial_data()
            if len(prices) < 2: st.warning("Market Closed."); return

            curr = prices.iloc[-1]
            prev = prices.iloc[-2]
            
            dxy_val = curr.get('DX-Y.NYB'); dxy_prev = prev.get('DX-Y.NYB')
            dxy_pct = ((dxy_val - dxy_prev) / dxy_prev) * 100 if pd.notna(dxy_val) else 0

            yield_val = curr.get('^TNX'); yield_prev = prev.get('^TNX')
            yield_pct = ((yield_val - yield_prev) / yield_prev) * 100 if pd.notna(yield_val) else 0

            oil_val = curr.get('CL=F'); oil_prev = prev.get('CL=F')
            oil_pct = ((oil_val - oil_prev) / oil_prev) * 100 if pd.notna(oil_val) else 0
            
            gold_val = curr.get('GC=F'); gold_prev = prev.get('GC=F')
            gold_pct = ((gold_val - gold_prev) / gold_prev) * 100 if pd.notna(gold_val) else 0

            bias_text, css_class, final_score, reason_list = analyze_market_regime(dxy_pct, yield_pct, oil_pct)

            st.markdown("### 1. Market Bias Summary")
            col_bias, col_detail = st.columns([1, 2])
            with col_bias:
                st.markdown(f"""<div class="{css_class}"><h2 style="margin:0; color:white;">{bias_text}</h2><h4 style="margin:0; color:white;">Score: {final_score}/10</h4></div>""", unsafe_allow_html=True)
            with col_detail:
                st.info("📊 **Analisis Premium:**")
                if reason_list:
                    for r in reason_list: st.write(f"- {r}")
                else: st.write("- Pasar konsolidasi.")
            
            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🥇 GOLD", f"${gold_val:,.2f}", f"{gold_pct:.2f}%")
            c2.metric("💵 DXY", f"{dxy_val:.2f}", f"{dxy_pct:.2f}%", delta_color="inverse")
            c3.metric("📈 Yield", f"{yield_val:.3f}%", f"{yield_pct:.2f}%", delta_color="inverse")
            c4.metric("🛢️ Oil", f"${oil_val:.2f}", f"{oil_pct:.2f}%")

            st.markdown("### 3. Visualisasi Korelasi")
            norm_data = prices.pct_change().cumsum()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['GC=F'], name='GOLD', fill='tozeroy', line=dict(color='#FFD700')))
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['^TNX'], name='Yield', line=dict(color='#FF4B4B', dash='dot')))
            fig.update_layout(template="plotly_dark", height=450)
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button('🔄 Refresh'): st.cache_data.clear(); st.rerun()

        except Exception as e: st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
