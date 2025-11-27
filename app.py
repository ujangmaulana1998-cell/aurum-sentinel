import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import hashlib
import numpy as np
from datetime import datetime, timedelta, timezone 

# ==========================================
# 1. KONFIGURASI SISTEM DAN CSS
# ==========================================

st.set_page_config(
    page_title="MafaFX Premium",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-image: linear-gradient(to right bottom, #d926a9, #bc20b6, #9b1fc0, #7623c8, #4728cd); background-attachment: fixed; }
    h1, h2, h3, h4, h5, h6, p, span, div, label { color: #ffffff !important; font-family: 'Helvetica Neue', sans-serif; }
    div[data-testid="stMetric"] { 
        background-color: rgba(0, 0, 0, 0.4) !important; 
        border: 1px solid rgba(255, 255, 255, 0.2); 
        padding: 15px; 
        border-radius: 15px; 
        backdrop-filter: blur(5px); 
        color: white !important;
    }
    div.stButton > button { 
        width: 100%; 
        background: linear-gradient(to right, #FFD700, #E5C100) !important; 
        color: black !important; 
        font-weight: 800 !important; 
        border-radius: 10px; 
        border: none; 
        padding: 12px 0px; 
        margin-top: 5px; 
    }
    div.stButton > button:last-child {
        width: 50%;
        margin-left: 25%;
        margin-right: 25%;
        margin-top: 15px;
    }
    [data-testid="stSidebar"] [data-testid="stImage"] { text-align: center; display: block; margin-left: auto; margin-right: auto; width: 100%; }
    div[data-testid="stForm"] { background-color: rgba(0, 0, 0, 0.5); padding: 30px; border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.3); }
    [data-testid="stDataFrame"] { background-color: rgba(0, 0, 0, 0.3) !important; border-radius: 10px; padding: 10px; }
    .stDataFrame .data-cell { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SISTEM LOGIN
# ==========================================

def get_session_token(username, password):
    raw_str = f"{username}::{password}::MafaFX_Secure_Salt"
    return hashlib.sha256(raw_str.encode()).hexdigest()

def check_password():
    try:
        VALID_USERS = st.secrets["passwords"]
    except:
        st.error("API Error: Secrets untuk Login tidak ditemukan.")
        st.stop()
        
    params = st.query_params
    if "auth_token" in params:
        token = params["auth_token"]
        for user, pwd in VALID_USERS.items():
            if get_session_token(user, pwd) == token:
                st.session_state["password_correct"] = True
                st.session_state["username"] = user
                break

    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    
    if st.session_state["password_correct"]: return True

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        try: st.image("logo.png", width=200)
        except: st.markdown("<h1 style='text-align: center;'>👑 MafaFX</h1>", unsafe_allow_html=True)
            
        st.markdown("<h3 style='text-align: center;'>Real-Time Intelligence</h3>", unsafe_allow_html=True)
        
        with st.form("credentials"):
            st.text_input("Username", key="username_input")
            st.text_input("Password", type="password", key="password_input")
            
            if st.form_submit_button("LOGIN"):
                user = st.session_state.get("username_input")
                pwd = st.session_state.get("password_input")
                
                if user in VALID_USERS and VALID_USERS[user] == pwd:
                    st.session_state["password_correct"] = True
                    st.session_state["username"] = user
                    token = get_session_token(user, pwd)
                    st.query_params["auth_token"] = token
                    st.rerun()
                else:
                    st.error("Username/Password Salah.")
                    
    return False

if not check_password(): st.stop()


# 🟢 FUNGSI NOTIFIKASI TELEGRAM
def send_telegram_notification(message):
    try:
        bot_token = st.secrets["telegram"]["BOT_TOKEN"]
        chat_ids_str = st.secrets["telegram"]["CHAT_IDS"]
        chat_ids_list = [id.strip() for id in chat_ids_str.split(',')]
    except KeyError:
        return False

    success = True
    for chat_id in chat_ids_list:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, data=payload, timeout=5)
            if response.status_code != 200:
                success = False
        except requests.exceptions.RequestException:
            success = False
            
    return success


# ==========================================
# 3. ENGINE DATA (RSI SENTIMENT FIX)
# ==========================================

def get_twelvedata(symbol, interval, api_key):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={api_key}&outputsize=50" # Need 50 for good RSI
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if "status" in data and data["status"] == "error": return None
        return data.get("values", [])
    except: return None

def calculate_rsi(prices, period=14):
    """Menghitung RSI secara manual."""
    try:
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum()/period
        down = -seed[seed < 0].sum()/period
        rs = up/down
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100./(1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i-1] 
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up/down
            rsi[i] = 100. - 100./(1. + rs)
        return rsi[-1] # Return latest RSI
    except:
        return 50.0

def process_data(values, inverse=False):
    if not values: return None, None, None, None
    try:
        df = pd.DataFrame(values)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['datetime'] = df['datetime'] + pd.Timedelta(hours=7)
        df = df.set_index('datetime').sort_index()
        df['close'] = df['close'].astype(float)
        
        # Simpan harga close untuk perhitungan RSI nanti
        prices_series = df['close'].values 
        
        current = df['close'].iloc[-1]
        prev = df['close'].iloc[-2]
        
        if inverse: 
            change_pct = -1 * ((current - prev) / prev) * 100
            chart_data = df['close'].pct_change() * -1 
            display_price = (1 / current) * 100 
        else:
            change_pct = ((current - prev) / prev) * 100
            chart_data = df['close'] 
            display_price = current
            
        return display_price, change_pct, chart_data, prices_series
    except: return None, None, None, None

@st.cache_data(ttl=3600) 
def fetch_economic_calendar():
    try:
        api_key = st.secrets["finnhub"]["api_key"]
    except KeyError:
        return pd.DataFrame() 

    today = datetime.now().strftime('%Y-%m-%d')
    seven_days_later = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={seven_days_later}&token={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json().get("economicCalendar", [])
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df = df[ (df['country'] == 'US') & (df['impact'] == 'high') ].copy() 
        if df.empty: return pd.DataFrame()
        df['datetime_utc'] = pd.to_datetime(df['date'])
        df['WIB'] = df['datetime_utc'].apply(lambda x: x.tz_localize('UTC').tz_convert('Asia/Jakarta'))
        df_display = df[['WIB', 'event', 'actual', 'forecast', 'previous']].rename(columns={
            'WIB': 'Waktu (WIB)', 'event': 'Acara Berita', 'actual': 'Aktual',
            'forecast': 'Konsensus', 'previous': 'Sebelum'
        })
        df_display['Waktu (WIB)'] = df_display['Waktu (WIB)'].dt.strftime('%a, %d %b %H:%M')
        return df_display
    except Exception as e:
        return pd.DataFrame()

# 🟢 BARU: FUNGSI SENTIMEN TEKNIKAL (PENGGANTI FINNHUB YANG ERROR)
def calculate_technical_sentiment(gold_prices):
    """Menghitung Sentimen Pasar berdasarkan RSI dan Tren Harga."""
    try:
        if gold_prices is None or len(gold_prices) < 20:
             return {'net_score': 0, 'bullish': 50, 'bearish': 50, 'status': 'Neutral'}

        # Hitung RSI (Relative Strength Index)
        rsi_val = calculate_rsi(gold_prices)
        
        # Logika Sentimen berdasarkan RSI
        # RSI 0-100. RSI 50 = Netral. 
        # Kita mapping RSI ke "Bullish %"
        
        bullish_pct = rsi_val
        bearish_pct = 100 - rsi_val
        
        # Net Score scale: -1 (Total Bear) to +1 (Total Bull)
        net_score = (bullish_pct - bearish_pct) / 100
        
        return {
            'net_score': net_score,
            'bullish': bullish_pct,
            'bearish': bearish_pct,
            'error': False
        }
    except Exception as e:
        return {'net_score': 0, 'bullish': 50, 'bearish': 50, 'error': True}


@st.cache_data(ttl=3600) 
def fetch_market_data():
    """Mengambil semua data pasar."""
    try: api_key = st.secrets["twelvedata"]["api_key"]
    except: st.error("Twelve Data API Key Missing"); return None

    gold_raw = get_twelvedata("XAU/USD", "1h", api_key) 
    dxy_raw = get_twelvedata("EUR/USD", "1h", api_key)
    
    if not gold_raw or not dxy_raw: st.warning("Twelve Data tidak ditemukan."); return None
    
    g_price, g_chg, g_chart, g_history = process_data(gold_raw)
    d_price, d_chg, d_chart, d_history = process_data(dxy_raw, inverse=True)
    
    calendar_data = fetch_economic_calendar()
    
    # MENGGUNAKAN SENTIMEN TEKNIKAL SEKARANG
    sentiment_data = calculate_technical_sentiment(g_history)

    return {
        'GOLD': {'price': g_price, 'chg': g_chg, 'chart': g_chart},
        'DXY': {'price': d_price, 'chg': d_chg, 'chart': d_chart},
        'CALENDAR': calendar_data,
        'SENTIMENT': sentiment_data
    }

# ==========================================
# 4. DASHBOARD UTAMA
# ==========================================

def main_dashboard():
    if 'last_signal' not in st.session_state:
        st.session_state['last_signal'] = "NEUTRAL"

    # --- SIDEBAR ---
    with st.sidebar:
        try: st.image("logo.png", width=150)
        except: st.write("### 👑 MafaFX")
        st.markdown("---")
        st.write(f"User: **{st.session_state.get('username')}**")
        st.caption("Timeframe: H1 (1 Jam)") 
        st.caption("Status: Premium Active")

    # --- HEADER ---
    col_head, col_refresh = st.columns([4, 1])
    with col_head:
        st.title("MafaFX Premium (Fundamental Trading)")
        st.caption("⚡ Data H1 Real-Time - Waktu Indonesia Barat")
    with col_refresh:
        if st.button("🔄 Refresh Data"): 
            st.cache_data.clear()
            st.rerun()
        
        if st.button("🚪 Logout"): 
            st.session_state["password_correct"] = False
            st.query_params.clear() 
            st.rerun()

    # --- DATA & LOGIC ---
    with st.spinner('Menghitung Tekanan Harian & Sinkronisasi Data...'):
        data = fetch_market_data()
        
        if data is None:
            st.warning("Menunggu data Real-Time... (Cek API Key di Secrets)")
            return

        gold = data['GOLD']
        dxy = data['DXY']
        sentiment = data['SENTIMENT']
        
        current_signal = "NEUTRAL"
        signal_color = "#FFFFFF"
        signal_text = "NEUTRAL ⚪"
        
        if dxy['chg'] > 0.05: 
            current_signal = "SELL"
            signal_color = "#FF4B4B"
        elif dxy['chg'] < -0.05: 
            current_signal = "BUY"
            signal_color = "#00CC96"
        else:
            current_signal = "NEUTRAL"

        if current_signal == "SELL":
            if sentiment['net_score'] < -0.1:
                signal_text = "JUAL KUAT 🔴 (Teknikal Bearish)"
            elif sentiment['net_score'] > 0.1:
                 signal_text = "JUAL WASPADA 🔴 (Teknikal Bullish)"
            else:
                signal_text = "TEKANAN JUAL (SELL) 🔴"
            
        elif current_signal == "BUY":
            if sentiment['net_score'] > 0.1:
                signal_text = "BELI KUAT 🟢 (Teknikal Bullish)"
            elif sentiment['net_score'] < -0.1:
                signal_text = "BELI WASPADA 🟢 (Teknikal Bearish)"
            else:
                signal_text = "PELUANG BELI (BUY) 🟢"
        
        # NOTIFIKASI
        if current_signal != st.session_state['last_signal'] and current_signal != "NEUTRAL":
            message = (
                f"🚨 *[MAFAFX ALERT]* 🚨\n"
                f"Sinyal Baru Terdeteksi: *{signal_text}*\n"
                f"--------------------------------------\n"
                f"Harga XAU/USD: ${gold['price']:,.2f}\n"
                f"Perubahan H1: {gold['chg']:.2f}%\n"
                f"Sentimen RSI: {sentiment['bullish']:.1f}/100\n"
                f"Timeframe: H1 (1 Jam)\n"
                f"--------------------------------------\n"
                f"⏳ Sinyal sebelumnya: {st.session_state['last_signal']}"
            )
            send_telegram_notification(message)
            st.session_state['last_signal'] = current_signal

        # UI DASHBOARD
        st.markdown(f"""
        <div style="background: rgba(0,0,0,0.3); padding:20px; border-radius:15px; text-align:center; border: 1px solid rgba(255,255,255,0.2); margin-bottom: 20px;">
            <h1 style="margin:0; text-shadow: 0 0 15px {signal_color}; color: {signal_color}; font-size: 2.5em;">{signal_text}</h1>
            <h3 style="margin:5px 0 0 0; color: white;">XAU/USD: ${gold['price']:,.2f}</h3>
            <p style="margin:0; opacity:0.7; font-size: 0.9em;">Perubahan 1 Jam: {gold['chg']:.2f}%</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_sent1, col_sent2, col_sent3 = st.columns(3)
        calendar = data['CALENDAR']

        # MENAMPILKAN SENTIMEN TEKNIKAL
        col_sent1.metric("Skor Sentimen Teknikal (Net)", f"{sentiment['net_score']:.2f}", help="Berdasarkan RSI. Positif = Bullish, Negatif = Bearish.")
        col_sent2.metric("Bullish Power (RSI)", f"{sentiment['bullish']:.1f}%")
        col_sent3.metric("Bearish Power", f"{sentiment['bearish']:.1f}%")
            
        st.markdown("---")
        
        # GRAFIK
        st.markdown("### 🚦 Analisis Arus & Tekanan H1 (WIB)")
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.65, 0.35],
                            subplot_titles=("1. Harga Emas (H1 Akibat)", "2. Tekanan Dolar (H1 Sebab)"))

        fig.add_trace(go.Scatter(y=gold['chart'], mode='lines', name='Harga Emas', 
                                 line=dict(color='#FFD700', width=3), fill='tozeroy'), row=1, col=1)

        dxy_vals = dxy['chart'].dropna()
        bar_colors = ['#FF4B4B' if val > 0 else '#00CC96' for val in dxy_vals]
        
        fig.add_trace(go.Bar(x=dxy_vals.index, y=dxy_vals, name='Tekanan Dolar', 
                             marker_color=bar_colors), row=2, col=1)

        fig.update_layout(template="plotly_dark", height=550, 
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                          margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
        fig.update_yaxes(showgrid=False, zeroline=False)
        fig.update_xaxes(showgrid=False)
        fig.add_hline(y=0, line_dash="dot", row=2, col=1, line_color="white", opacity=0.5)

        st.plotly_chart(fig, use_container_width=True)
        
        # LEGEND
        c1, c2 = st.columns(2)
        c1.error("**🟥 MERAH:** Dolar Kuat (Menekan Emas). Fokus pada posisi JUAL (SELL).")
        c2.success("**🟩 HIJAU:** Dolar Lemah (Melegakan Emas). Fokus pada posisi BELI (BUY).")

        # KALENDER
        st.markdown("---")
        st.markdown("### 🚨 Filter Fundamental: High Impact USD News (WIB)")
        
        if not calendar.empty:
            st.caption("Gunakan ini sebagai **PERINGATAN DINI** untuk menghindari atau memanfaatkan Volatilitas.")
            st.dataframe(
                calendar, 
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Acara Berita": st.column_config.Column(width="medium"),
                }
            )
        else:
            st.info("Tidak ada berita High Impact USD yang terdeteksi untuk 7 hari ke depan.")

        # TOMBOL TES NOTIFIKASI
        st.markdown("---")
        st.markdown("<h3 style='text-align: center;'>Uji Koneksi Telegram</h3>", unsafe_allow_html=True)
        
        if st.button("🧪 Tes Kirim Notifikasi Telegram Sekarang"):
             if send_telegram_notification("✅ *[MAFAFX TEST]* Notifikasi Telegram berhasil terkirim!"):
                st.success("Notifikasi tes terkirim! Pesan dikirim ke SEMUA CHAT_IDS.")
             else:
                st.error("Gagal mengirim notifikasi. Cek BOT_TOKEN dan CHAT_IDS di Secrets, dan pastikan Bot adalah Admin di semua Channel/Group.")

if __name__ == "__main__":
    main_dashboard()
