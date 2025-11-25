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

# Custom CSS untuk tampilan profesional (Dark Mode Optimized)
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .bias-bullish {
        background-color: #0c4a28;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #28a745;
    }
    .bias-bearish {
        background-color: #5c1818;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #dc3545;
    }
    .bias-neutral {
        background-color: #3e3e3e;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #6c757d;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. ENGINE PENGAMBIL DATA (BACKEND) ---
@st.cache_data(ttl=60) # Auto-refresh data setiap 60 detik
def fetch_financial_data():
    # Tickers: Gold, US10Y Yield, DXY, Crude Oil (Inflation Proxy)
    tickers = ['GC=F', '^TNX', 'DX-Y.NYB', 'CL=F']
    
    # Ambil data intraday 5 hari terakhir interval 15 menit
    data = yf.download(tickers, period='5d', interval='15m', progress=False)
    
    # Cleaning Data Multi-index
    df = data['Close']
    
    # Hitung Perubahan Persentase (ROC) untuk Heatmap
    changes = df.pct_change()
    
    return df, changes

# --- 3. ENGINE ANALISIS FUNDAMENTAL (LOGIC) ---
def analyze_market_regime(dxy_chg, yield_chg, oil_chg):
    score = 0
    reasons = []

    # A. Analisis Dolar (DXY) - Bobot 4
    if dxy_chg > 0.05: 
        score -= 4
        reasons.append("USD Menguat Signifikan (Bearish Gold)")
    elif dxy_chg < -0.05: 
        score += 4
        reasons.append("USD Melemah (Bullish Gold)")

    # B. Analisis Yield (US10Y) - Bobot 5 (Musuh Utama)
    if yield_chg > 0.5: 
        score -= 5
        reasons.append("Yield Obligasi Melonjak (Bearish Gold)")
    elif yield_chg < -0.5: 
        score += 5
        reasons.append("Yield Obligasi Turun (Bullish Gold)")
        
    # C. Analisis Minyak (Inflasi) - Bobot 2
    if oil_chg > 1.0:
        score += 2
        reasons.append("Minyak Naik (Potensi Inflasi/Safe Haven)")
    elif oil_chg < -1.0:
        score -= 1 # Deflasi ringan
        
    # Penentuan Bias Akhir
    if score >= 6: return "STRONG BUY 🚀", "bias-bullish", score, reasons
    elif score >= 2: return "BUY 🟢", "bias-bullish", score, reasons
    elif score <= -6: return "STRONG SELL 🩸", "bias-bearish", score, reasons
    elif score <= -2: return "SELL 🔴", "bias-bearish", score, reasons
    else: return "NEUTRAL ⚪", "bias-neutral", score, reasons

# --- 4. TAMPILAN ANTARMUKA (FRONTEND) ---
def main():
    st.title("👑 AURUM SENTINEL: XAUUSD Master Dashboard")
    st.caption(f"Last Updated: {datetime.now().strftime('%H:%M:%S UTC')} | Data Source: Yahoo Finance Live")
    
    # Loading State
    with st.spinner('Menghubungkan ke Bursa Global...'):
        try:
            prices, changes = fetch_financial_data()
            
            # Ambil data baris terakhir (Realtime) dan baris sebelumnya
            curr = prices.iloc[-1]
            prev = prices.iloc[-2]
            
            # Hitung % Change manual untuk presisi
            dxy_pct = ((curr['DX-Y.NYB'] - prev['DX-Y.NYB']) / prev['DX-Y.NYB']) * 100
            yield_pct = ((curr['^TNX'] - prev['^TNX']) / prev['^TNX']) * 100
            oil_pct = ((curr['CL=F'] - prev['CL=F']) / prev['CL=F']) * 100
            gold_pct = ((curr['GC=F'] - prev['GC=F']) / prev['GC=F']) * 100
            
            # Dapatkan Analisis
            bias_text, css_class, final_score, reason_list = analyze_market_regime(dxy_pct, yield_pct, oil_pct)

            # --- SECTION A: KEPUTUSAN UTAMA ---
            st.markdown("### 1. Market Bias Summary")
            col_bias, col_detail = st.columns([1, 2])
            
            with col_bias:
                st.markdown(f"""
                <div class="{css_class}">
                    <h2 style="margin:0; color:white;">{bias_text}</h2>
                    <h4 style="margin:0; color:white;">Score: {final_score}/10</h4>
                </div>
                """, unsafe_allow_html=True)
            
            with col_detail:
                st.info("📊 **Faktor Penggerak Saat Ini:**")
                for r in reason_list:
                    st.write(f"- {r}")
                if not reason_list:
                    st.write("- Pasar sedang berkonsolidasi (Wait & See)")

            st.markdown("---")

            # --- SECTION B: DATA VITAL INTERMARKET ---
            st.markdown("### 2. Live Intermarket Data")
            c1, c2, c3, c4 = st.columns(4)
            
            c1.metric("🥇 GOLD (XAU)", f"${curr['GC=F']:,.2f}", f"{gold_pct:.2f}%")
            c2.metric("💵 USD Index (DXY)", f"{curr['DX-Y.NYB']:.2f}", f"{dxy_pct:.2f}%", delta_color="inverse")
            c3.metric("📈 US 10Y Yield", f"{curr['^TNX']:.3f}%", f"{yield_pct:.2f}%", delta_color="inverse")
            c4.metric("🛢️ Crude Oil", f"${curr['CL=F']:.2f}", f"{oil_pct:.2f}%")

            # --- SECTION C: CHART KORELASI ---
            st.markdown("### 3. Visualisasi Korelasi (Negative Correlation)")
            
            # Normalisasi data (Z-Score like normalization untuk visualisasi)
            # Kita gunakan Cumulative Return agar start dari titik 0 yang sama
            norm_data = prices.pct_change().cumsum()
            
            fig = go.Figure()
            # Gold sebagai Area utama
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['GC=F'], name='GOLD', 
                                     fill='tozeroy', line=dict(color='#FFD700', width=2)))
            # Musuh Gold (Yield & DXY) sebagai garis putus-putus
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['^TNX'], name='US 10Y Yield', 
                                     line=dict(color='#FF4B4B', width=2, dash='dot')))
            fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data['DX-Y.NYB'], name='DXY', 
                                     line=dict(color='#4B4BFF', width=2, dash='dot')))
            
            fig.update_layout(
                template="plotly_dark",
                height=500,
                title="Jika Garis Merah/Biru NAIK, Area Kuning (Emas) Harusnya TURUN",
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Tombol Refresh
            if st.button('🔄 Refresh Data Pasar'):
                st.cache_data.clear()
                st.rerun()

        except Exception as e:
            st.error(f"Gagal mengambil data pasar. Bursa mungkin tutup atau API limit. Error: {e}")

if __name__ == "__main__":
    main()
