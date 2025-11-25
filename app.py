import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. KONFIGURASI SISTEM ---
st.set_page_config(
    page_title="Aurum Sentinel - Pro Dashboard",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card { background-color: #1E1E1E; border: 1px solid #333; padding: 20px; border-radius: 10px; color: white; }
    .bias-bullish { background-color: #0c4a28; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #28a745; }
    .bias-bearish { background-color: #5c1818; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #dc3545; }
    .bias-neutral { background-color: #3e3e3e; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #6c757d; }
</style>
""", unsafe_allow_html=True)

# --- 2. ENGINE PENGAMBIL DATA (BACKEND) ---
@st.cache_data(ttl=60)
def fetch_financial_data():
    tickers = ['GC=F', '^TNX', 'DX-Y.NYB', 'CL=F']
    
    # Ambil data
    data = yf.download(tickers, period='5d', interval='15m', progress=False)
    
    # Cleaning Data
    df = data['Close']
    
    # FIX PENTING (V1.1): Forward Fill
    # Jika data Yield kosong (NaN), pakai data jam sebelumnya.
    df = df.ffill()
    
    # Hapus baris yang masih kosong (jika ada)
    df = df.dropna()

    return df

# --- 3. ENGINE ANALISIS FUNDAMENTAL (LOGIC) ---
def analyze_market_regime(dxy_chg, yield_chg, oil_chg):
    score = 0
    reasons = []

    # A. Analisis Dolar (DXY)
    if dxy_chg > 0.05: 
        score -= 4
        reasons.append("USD Menguat (Bearish Gold)")
    elif dxy_chg < -0.05: 
        score += 4
        reasons.append("USD Melemah (Bullish Gold)")

    # B. Analisis Yield (US10Y)
    if yield_chg > 0.5: 
        score -= 5
        reasons.append("Yield Obligasi Melonjak (Bearish Gold)")
    elif yield_chg < -0.5: 
        score += 5
        reasons.append("Yield Obligasi Turun (Bullish Gold)")
        
    # C. Analisis Minyak
    if oil_chg > 1.0:
        score += 2
        reasons.append("Minyak Naik (Inflasi Hedge)")
    elif oil_chg < -1.0:
        score -= 1 
        
    if score >= 6: return "STRONG BUY 🚀", "bias-bullish", score, reasons
    elif score >= 2: return "BUY 🟢", "bias-bullish", score, reasons
    elif score <= -6: return "STRONG SELL 🩸", "bias-bearish", score, reasons
    elif score <= -2: return "SELL 🔴", "bias-bearish", score, reasons
    else: return "NEUTRAL ⚪", "bias-neutral", score, reasons

# --- 4. TAMPILAN ANTARMUKA (FRONTEND) ---
def main():
    st.title("👑 AURUM SENTINEL: XAUUSD Master Dashboard")
    st.caption(f"Last Updated: {datetime.now().strftime('%H:%M:%S UTC')} | Data Source: Yahoo Finance Live")
    
    with st.spinner('Menghubungkan ke Bursa Global...'):
        try:
            prices = fetch_financial_data()
            
            # Cek apakah data cukup
            if len(prices) < 2:
                st.warning("Data pasar belum tersedia (Market Closed). Coba lagi nanti.")
                return

            curr = prices.iloc[-1]
            prev = prices.iloc[-2]
            
            # Hitung % Change (Manual Calculation)
            # Menggunakan .get() untuk menghindari error jika ticker hilang
            try:
                dxy_val = curr.get('DX-Y.NYB')
                dxy_prev = prev.get('DX-Y.NYB')
                dxy_pct = ((dxy_val - dxy_prev) / dxy_prev) * 100 if pd.notna(dxy_val) else 0

                yield_val = curr.get('^TNX')
                yield_prev = prev.get('^TNX')
                yield_pct = ((yield_val - yield_prev) / yield_prev) * 100 if pd.notna(yield_val) else 0

                oil_val = curr.get('CL=F')
                oil_prev = prev.get('CL=F')
                oil_pct = ((oil_val - oil_prev) / oil_prev) * 100 if pd.notna(oil_val) else 0
                
                gold_val = curr.get('GC=F')
                gold_prev = prev.get('GC=F')
                gold_pct = ((gold_val - gold_prev) / gold_prev) * 100 if pd.notna(gold_val) else 0
            except:
                st.error("Data parsial tidak lengkap. Refresh browser.")
                return

            # Dapatkan Analisis
            bias_text, css_class, final_score, reason_list = analyze_market_regime(dxy_pct, yield_pct, oil_pct)

            # --- UI SECTIONS ---
            st.markdown("### 1. Market Bias Summary")
            col_bias, col_detail = st.columns([1, 2])
            
            with col_bias:
                st.markdown(f"""<div class="{css_class}"><h2 style="margin:0; color:white;">{bias_text}</h2><h4 style="margin:0; color:white;">Score: {final_score}/10</h4></div>""", unsafe_allow_html=True)
            
            with col_detail:
                st.info("📊 **Faktor Penggerak Saat Ini:**")
                if reason_list:
                    for r in reason_list: st.write(f"- {r}")
                else:
                    st.write("- Pasar tenang/konsolidasi (Volatilitas Rendah)")

            st.markdown("---")
            
            # Metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🥇 GOLD", f"${gold_val:,.2f}", f"{gold_pct:.2f}%")
            c2.metric("💵 DXY", f"{dxy_val:.2f}", f"{dxy_pct:.2f}%", delta_color="inverse")
            c3.metric("📈 US10Y Yield", f"{yield_val:.3f}%", f"{yield_pct:.2f}%", delta_color="inverse")
            c4.metric("🛢️ Oil", f"${oil_val:.2f}", f"{oil_pct:.2f}%")

            # Chart
            st.markdown("### 3. Visualisasi Korelasi")
            norm_data = prices.pct_change().cumsum()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['GC=F'], name='GOLD', fill='tozeroy', line=dict(color='#FFD700')))
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['^TNX'], name='US 10Y Yield', line=dict(color='#FF4B4B', dash='dot')))
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['DX-Y.NYB'], name='DXY', line=dict(color='#4B4BFF', dash='dot')))
            fig.update_layout(template="plotly_dark", height=450, title="Negative Correlation Check")
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button('🔄 Refresh Data'): st.cache_data.clear(); st.rerun()

        except Exception as e:
            st.error(f"Terjadi kesalahan data feed: {e}")

if __name__ == "__main__":
    main()
