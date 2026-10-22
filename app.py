import os
import json
import time
import re
import datetime
import requests
import ccxt
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from dotenv import load_dotenv
from google import genai

# 1. 페이지 기본 설정 및 환경 변수 로드
load_dotenv()

st.set_page_config(
    page_title="OKX AI Pro Trading",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 🔒 세션 상태 초기화
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Dark (다크 모드)"

if "active_tf" not in st.session_state:
    st.session_state.active_tf = "1h"

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

if "limit_price_val" not in st.session_state:
    st.session_state.limit_price_val = 0.0

# 동적 CSS 테마 색상 설정
is_dark = "Dark" in st.session_state.theme_mode

bg_color = "#000000" if is_dark else "#f4f5f8"
card_bg = "#0e1217" if is_dark else "#ffffff"
input_bg = "#1a1f26" if is_dark else "#ffffff"
text_color = "#eaeaea" if is_dark else "#111827"
border_color = "#282e38" if is_dark else "#e5e7eb"

st.markdown(f"""
<style>
    /* 1. 사이드바 완전히 숨기기 */
    [data-testid="stSidebar"] {{
        display: none !important;
    }}
    
    /* 2. 전체 메인 앱 딥 블랙 배경 */
    .stApp, div[data-testid="stHeader"], div[data-testid="stToolbar"] {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}

    /* 3. 컬럼 레이아웃 간격 최적화 */
    div[data-testid="stHorizontalBlock"] {{
        gap: 8px !important;
    }}

    /* 4. ⭐ 각 영역(차트, 호가창, 주문패널)을 오른쪽 OKX 스타일로 카드 분리 ⭐ */
    div[data-testid="column"] > div {{
        background-color: {card_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
        padding: 10px 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4) !important;
    }}

    /* 5. 타이틀, 라벨, 텍스트 글자색 다크 적용 */
    label, p, span, h1, h2, h3, h4, h5, h6, div[data-testid="stWidgetLabel"] {{
        color: {text_color} !important;
    }}

    /* 6. ⭐ 입력창, 넘버입력기, 선택박스 등 컨테이너 선명한 테두리 카드화 ⭐ */
    div[data-baseweb="input"], 
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"],
    input, textarea, select {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 6px !important;
    }}

    input[type="number"] {{
        color: {text_color} !important;
        background-color: {input_bg} !important;
    }}
    
    button[aria-label="Decrease value"], button[aria-label="Increase value"] {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border-color: {border_color} !important;
    }}

    /* 7. 일반 슬림 버튼 다크 모드 */
    div.stButton > button {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
        padding: 2px 6px !important;
        min-height: 24px !important;
        height: 24px !important;
        font-size: 11px !important;
        line-height: 20px !important;
    }}
    div.stButton > button:hover {{
        border-color: #00c076 !important;
        color: #00c076 !important;
    }}

    /* 8. '더보기' 및 팝오버(Popover) 다크 오버라이드 */
    button[data-testid="stBaseButton-popover"],
    div[data-testid="stPopover"] > button {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        min-height: 24px !important;
        height: 24px !important;
        font-size: 11px !important;
        padding: 0px 8px !important;
        border-radius: 4px !important;
    }}
    button[data-testid="stBaseButton-popover"]:hover,
    div[data-testid="stPopover"] > button:hover {{
        border-color: #f0b90b !important;
        color: #f0b90b !important;
    }}
    div[data-testid="stPopoverBody"], div[data-baseweb="popover"] {{
        background-color: {card_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 6px !important;
    }}

    /* 9. 💡 호가창(Order Book) 초밀착 3열 디자인 및 0px Gap */
    div[data-testid="stVerticalBlock"] > div {{
        gap: 0px !important;
    }}

    div[class*="ob-ask-"] > button, div[class*="ob-bid-"] > button {{
        border: none !important;
        border-radius: 0px !important;
        padding: 0px 6px !important;
        margin: 0px !important;
        min-height: 20px !important;
        height: 20px !important;
        line-height: 20px !important;
        font-size: 11px !important;
        font-family: "Roboto Mono", "Courier New", monospace !important;
        width: 100% !important;
        white-space: pre !important;
        text-align: left !important;
        box-shadow: none !important;
    }}

    div[class*="ob-ask-"] > button {{
        color: #ff4d4f !important;
    }}
    div[class*="ob-ask-"] > button:hover {{
        outline: 1px solid #ff4d4f !important;
        background-color: rgba(255, 77, 79, 0.35) !important;
    }}

    div[class*="ob-bid-"] > button {{
        color: #00c076 !important;
    }}
    div[class*="ob-bid-"] > button:hover {{
        outline: 1px solid #00c076 !important;
        background-color: rgba(0, 192, 118, 0.35) !important;
    }}

    /* 10. 탭 헤더 다크 스타일 */
    button[data-baseweb="tab"] {{
        color: #848e9c !important;
        background-color: transparent !important;
    }}
    button[aria-selected="true"] {{
        color: #00c076 !important;
        border-bottom-color: #00c076 !important;
    }}

    /* OKX Header Bar 카드 */
    .okx-header {{
        background-color: {card_bg};
        padding: 8px 16px;
        border-radius: 8px;
        border: 1px solid {border_color};
        margin-bottom: 8px;
    }}
    .okx-price-up {{ color: #00c076; font-weight: bold; }}
    .okx-price-down {{ color: #ff4d4f; font-weight: bold; }}
</style>
""", unsafe_allow_html=True)

# 🔒 비밀번호 잠금 기능
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.title("🔒 OKX Pro Trading 로그인")
        pwd = st.text_input("대시보드 비밀번호를 입력하세요:", type="password")
        if st.button("로그인"):
            correct_pwd = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", "1234"))
            if pwd == correct_pwd:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 올바르지 않습니다.")
        return False
    return True

if not check_password():
    st.stop()

# 거래소 및 AI 클라이언트 초기화
@st.cache_resource
def get_clients():
    api_key = os.getenv("OKX_API_KEY") or st.secrets.get("OKX_API_KEY")
    secret_key = os.getenv("OKX_SECRET_KEY") or st.secrets.get("OKX_SECRET_KEY")
    passphrase = os.getenv("OKX_PASSPHRASE") or st.secrets.get("OKX_PASSPHRASE")
    gemini_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True)

    ai_client = genai.Client(api_key=gemini_key) if gemini_key else None
    return exchange, ai_client

try:
    exchange, ai_client = get_clients()
except Exception as e:
    st.error(f"거래소 설정 오류: {e}")
    st.stop()

openrouter_key = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY", "")

display_symbol = 'BTCUSDT'
ccxt_symbol = 'BTC/USDT'

# 실시간 시세 및 계좌 데이터 로드
try:
    ticker = exchange.fetch_ticker(ccxt_symbol)
    balance = exchange.fetch_balance()
    
    current_price = ticker['last']
    high_24h = ticker.get('high', current_price)
    low_24h = ticker.get('low', current_price)
    volume_24h = ticker.get('baseVolume', 0)
    change_24h = ticker.get('percentage', 0)
    
    usdt_balance = balance['total'].get('USDT', 0)
    btc_balance = balance['total'].get('BTC', 0)
    total_asset_usdt = usdt_balance + (btc_balance * current_price)

    if st.session_state.limit_price_val == 0.0:
        st.session_state.limit_price_val = current_price

except Exception as e:
    st.error(f"거래소 데이터 로드 실패: {e}")
    st.stop()

# --- 1. Top Header Bar & 내장 설정 창 ---
change_class = "okx-price-up" if change_24h >= 0 else "okx-price-down"
change_sign = "+" if change_24h >= 0 else ""

header_col, settings_col = st.columns([9.2, 0.8])

with header_col:
    st.markdown(f"""
    <div class="okx-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 15px; font-weight: bold;">⬛ {display_symbol}</span>
                <span style="background-color: #2b313a; color: #f0b90b; font-size: 10px; padding: 1px 4px; border-radius: 3px;">Demo Trading</span>
                <span style="background-color: #1e232a; color: #848e9c; font-size: 10px; padding: 1px 4px; border-radius: 3px;">Perp</span>
            </div>
            <div style="display: flex; gap: 14px; font-size: 11px;">
                <div><span style="color: #848e9c;">최근가</span><br><span class="{change_class}" style="font-size: 13px;">${current_price:,.2f}</span></div>
                <div><span style="color: #848e9c;">24h 변동률</span><br><span class="{change_class}">{change_sign}{change_24h:.2f}%</span></div>
                <div><span style="color: #848e9c;">24h 고가</span><br><span>${high_24h:,.2f}</span></div>
                <div><span style="color: #848e9c;">24h 저가</span><br><span>${low_24h:,.2f}</span></div>
                <div><span style="color: #848e9c;">24h 거래량</span><br><span>{volume_24h:,.2f} BTC</span></div>
                <div><span style="color: #848e9c;">총 평가 자산</span><br><span style="color: #f0b90b; font-weight: bold;">${total_asset_usdt:,.2f} USDT</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with settings_col:
    with st.popover("⚙️ 설정", use_container_width=True):
        st.markdown("<div style='font-size: 12px; font-weight: bold; margin-bottom: 6px;'>🎨 화면 테마 선택</div>", unsafe_allow_html=True)
        new_theme = st.radio(
            "테마 선택",
            ["Dark (다크 모드)", "Light (밝은 모드)"],
            index=0 if "Dark" in st.session_state.theme_mode else 1,
            label_visibility="collapsed"
        )
        if new_theme != st.session_state.theme_mode:
            st.session_state.theme_mode = new_theme
            st.rerun()

# --- 2. 상단 슬림 타임프레임 컨트롤 바 ---
tf_cols = st.columns([0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 1.2, 5])

def set_timeframe(tf_code):
    st.session_state.active_tf = tf_code

primary_tfs = [("1s", "1s"), ("1m", "1m"), ("5m", "5m"), ("15m", "15m"), ("1h", "1h"), ("4h", "4h"), ("1D", "1d")]

for idx, (label, code) in enumerate(primary_tfs):
    with tf_cols[idx]:
        is_active = (st.session_state.active_tf == code)
        btn_type = "primary" if is_active else "secondary"
        if st.button(label, key=f"btn_tf_{code}", type=btn_type, use_container_width=True):
            set_timeframe(code)
            st.rerun()

with tf_cols[7]:
    with st.popover("⌵ 더보기", use_container_width=True):
        st.markdown("<div style='font-size:11px; margin-bottom:6px;'><b>⏱️ Intervals 선택</b></div>", unsafe_allow_html=True)
        
        grid_r1 = st.columns(5)
        with grid_r1[0]:
            if st.button("Line", key="pop_line"): set_timeframe("1m"); st.rerun()
        with grid_r1[1]:
            if st.button("1s", key="pop_1s"): set_timeframe("1s"); st.rerun()
        with grid_r1[2]:
            if st.button("1m", key="pop_1m"): set_timeframe("1m"); st.rerun()
        with grid_r1[3]:
            if st.button("3m", key="pop_3m"): set_timeframe("3m"); st.rerun()
        with grid_r1[4]:
            if st.button("5m", key="pop_5m"): set_timeframe("5m"); st.rerun()

        grid_r2 = st.columns(5)
        with grid_r2[0]:
            if st.button("15m", key="pop_15m"): set_timeframe("15m"); st.rerun()
        with grid_r2[1]:
            if st.button("30m", key="pop_30m"): set_timeframe("30m"); st.rerun()
        with grid_r2[2]:
            if st.button("1h", key="pop_1h"): set_timeframe("1h"); st.rerun()
        with grid_r2[3]:
            if st.button("2h", key="pop_2h"): set_timeframe("2h"); st.rerun()
        with grid_r2[4]:
            if st.button("4h", key="pop_4h"): set_timeframe("4h"); st.rerun()

        grid_r3 = st.columns(5)
        with grid_r3[0]:
            if st.button("6h", key="pop_6h"): set_timeframe("6h"); st.rerun()
        with grid_r3[1]:
            if st.button("12h", key="pop_12h"): set_timeframe("12h"); st.rerun()
        with grid_r3[2]:
            if st.button("1D", key="pop_1d"): set_timeframe("1d"); st.rerun()
        with grid_r3[3]:
            if st.button("2D", key="pop_2d"): set_timeframe("2d"); st.rerun()
        with grid_r3[4]:
            if st.button("3D", key="pop_3d"): set_timeframe("3d"); st.rerun()

        grid_r4 = st.columns(5)
        with grid_r4[0]:
            if st.button("5D", key="pop_5d"): set_timeframe("5d"); st.rerun()
        with grid_r4[1]:
            if st.button("1W", key="pop_1w"): set_timeframe("1w"); st.rerun()
        with grid_r4[2]:
            if st.button("1M", key="pop_1M"): set_timeframe("1M"); st.rerun()
        with grid_r4[3]:
            if st.button("3M", key="pop_3M"): set_timeframe("3M"); st.rerun()

# --- 3. 메인 3컬럼 레이아웃 (차트 카드 | 호가창 카드 | 주문 패널 카드) ---
chart_col, orderbook_col, trade_col = st.columns([5.5, 2.2, 2.3])

# --- [LEFT: OKX 차트 패널 카드] ---
with chart_col:
    timeframe = st.session_state.active_tf

    try:
        limit_cnt = 50 if timeframe in ['1s', '1m', '3m'] else 70
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit_cnt)
    except Exception:
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe='1m', limit=50)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()

    min_idx = df['low'].idxmin()
    min_row = df.loc[min_idx]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02,
        row_heights=[0.8, 0.2]
    )

    fig.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name=display_symbol,
        increasing_line_color='#00c076', increasing_fillcolor='#00c076',
        decreasing_line_color='#ff4d4f', decreasing_fillcolor='#ff4d4f'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA5'], line=dict(color='#ff9900', width=1.2), name='MA(5)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA10'], line=dict(color='#ff2a6d', width=1.2), name='MA(10)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA20'], line=dict(color='#00e5ff', width=1.2), name='MA(20)'), row=1, col=1)

    fig.add_hline(
        y=current_price, row=1, col=1,
        line_dash="dot", line_color="#00c076", line_width=1.2
    )

    fig.add_annotation(
        x=min_row['datetime'], y=min_row['low'],
        text=f"← {min_row['low']:,.2f}",
        showarrow=False,
        font=dict(size=11, color="#eaeaea"),
        yshift=-12, xanchor="left",
        row=1, col=1
    )

    colors = ['#00c076' if row['close'] >= row['open'] else '#ff4d4f' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=colors, name='Volume'), row=2, col=1)

    fig.update_layout(
        paper_bgcolor=card_bg,
        plot_bgcolor=card_bg,
        font=dict(color="#848e9c", size=10),
        height=470,
        margin=dict(l=10, r=55, t=10, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=False,
        hovermode="x unified"
    )

    fig.update_yaxes(side="right", gridcolor="#1a1e24", zerolinecolor="#1a1e24", showgrid=True, row=1, col=1)
    fig.update_yaxes(side="right", gridcolor="#1a1e24", zerolinecolor="#1a1e24", showgrid=True, row=2, col=1)
    fig.update_xaxes(gridcolor="#1a1e24", zerolinecolor="#1a1e24", showgrid=True)

    st.plotly_chart(fig, use_container_width=True)

# --- [MIDDLE: 실시간 호가창 패널 카드] ---
with orderbook_col:
    st.markdown("<div style='font-weight: bold; font-size: 13px; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #282e38;'>📖 Order Book</div>", unsafe_allow_html=True)

    asks = []
    bids = []

    try:
        ob = exchange.fetch_order_book(ccxt_symbol, limit=8)
        if ob and 'asks' in ob and 'bids' in ob and len(ob['asks']) > 0 and len(ob['bids']) > 0:
            asks = [[float(x[0]), float(x[1])] for x in ob['asks'][:8] if len(x) >= 2]
            bids = [[float(x[0]), float(x[1])] for x in ob['bids'][:8] if len(x) >= 2]
    except Exception:
        pass

    if not asks or not bids:
        step = 0.50
        asks = [[current_price + (i * step), 0.0005 + (i * 0.002)] for i in range(8, 0, -1)]
        bids = [[current_price - (i * step), 0.0005 + (i * 0.002)] for i in range(1, 9)]

    st.markdown("""
    <div style='font-size: 10px; color: #848e9c; font-family: monospace; display:flex; justify-content: space-between; padding: 2px 4px; border-bottom: 1px solid #1a1e24; margin-bottom: 1px;'>
        <span>Price(USDT)</span>
        <span>Amount(BTC)</span>
        <span>Total(BTC)</span>
    </div>
    """, unsafe_allow_html=True)

    cum_ask = 0
    ask_rows = []
    for p, a in reversed(asks):
        cum_ask += a
        ask_rows.append((p, a, cum_ask))

    max_ask_cum = ask_rows[-1][2] if ask_rows else 1.0

    for idx, (p, a, c) in enumerate(ask_rows):
        pct = min(100.0, (c / max_ask_cum) * 100) if max_ask_cum > 0 else 0
        st.markdown(f"""
        <style>
            div.ob-ask-{idx} > button {{
                background: linear-gradient(90deg, rgba(255, 77, 79, 0.28) {pct:.1f}%, rgba(20, 12, 15, 0.8) {pct:.1f}%) !important;
            }}
        </style>
        """, unsafe_allow_html=True)
        
        row_str = f"{p:,.2f}".ljust(11) + f"{a:.4f}".rjust(9) + f"{c:.4f}".rjust(10)
        
        st.markdown(f'<div class="ob-ask-{idx}">', unsafe_allow_html=True)
        if st.button(row_str, key=f"ask_row_{idx}_{p:.2f}", use_container_width=True):
            st.session_state.limit_price_val = float(p)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div style='padding: 4px 6px; background-color: #1a1f26; border-radius: 4px; border: 1px solid #282e38; margin: 3px 0; display:flex; align-items:center; justify-content:space-between;'>
        <span class='{change_class}' style='font-size: 15px; font-weight: bold;'>${current_price:,.2f} {change_sign}</span>
        <span style='font-size: 11px; color: #848e9c;'>⚡ Live</span>
    </div>
    """, unsafe_allow_html=True)

    cum_bid = 0
    bid_rows = []
    for p, a in bids:
        cum_bid += a
        bid_rows.append((p, a, cum_bid))

    max_bid_cum = bid_rows[-1][2] if bid_rows else 1.0

    for idx, (p, a, c) in enumerate(bid_rows):
        pct = min(100.0, (c / max_bid_cum) * 100) if max_bid_cum > 0 else 0
        st.markdown(f"""
        <style>
            div.ob-bid-{idx} > button {{
                background: linear-gradient(90deg, rgba(0, 192, 118, 0.22) {pct:.1f}%, rgba(12, 22, 17, 0.8) {pct:.1f}%) !important;
            }}
        </style>
        """, unsafe_allow_html=True)

        row_str = f"{p:,.2f}".ljust(11) + f"{a:.4f}".rjust(9) + f"{c:.4f}".rjust(10)

        st.markdown(f'<div class="ob-bid-{idx}">', unsafe_allow_html=True)
        if st.button(row_str, key=f"bid_row_{idx}_{p:.2f}", use_container_width=True):
            st.session_state.limit_price_val = float(p)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- [RIGHT: 주문 패널 카드 (오른쪽 OKX 스타일 분리)] ---
with trade_col:
    st.markdown("<div style='font-weight: bold; font-size: 13px; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #282e38;'>⚡ Trade Panel</div>", unsafe_allow_html=True)
    
    leverage = st.slider("🎯 레버리지 배율 (1x ~ 50x)", min_value=1, max_value=50, value=10, step=1)
    order_mode = st.radio("주문 타입", ["지정가 (Limit)", "시장가 (Market)"], horizontal=True)
    
    limit_price = st.number_input("지정가 (USDT)", value=float(st.session_state.limit_price_val), step=10.0, key="limit_price_input")

    trade_tab1, trade_tab2 = st.tabs(["🟢 Buy / Long", "🔴 Sell / Short"])
    
    with trade_tab1:
        buy_percent = st.slider("USDT 매수 비중 (%)", 10, 100, 25, 5, key="b_percent")
        if st.button(f"🚀 {leverage}x Long 매수 실행", use_container_width=True, type="primary"):
            try:
                buy_usdt_amount = usdt_balance * (buy_percent / 100) * leverage
                buy_btc_amount = buy_usdt_amount / (limit_price if "지정가" in order_mode else current_price)
                
                if "시장가" in order_mode:
                    order = exchange.create_market_buy_order(ccxt_symbol, buy_btc_amount)
                else:
                    order = exchange.create_limit_buy_order(ccxt_symbol, buy_btc_amount, limit_price)
                st.success(f"✅ 매수 성공! ID: {order['id']}")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매수 실패: {e}")

    with trade_tab2:
        sell_percent = st.slider("BTC 매도 비중 (%)", 10, 100, 100, 5, key="s_percent")
        if st.button(f"📉 {leverage}x Short 매도 실행", use_container_width=True):
            try:
                sell_btc_amount = btc_balance * (sell_percent / 100)
                
                if "시장가" in order_mode:
                    order = exchange.create_market_sell_order(ccxt_symbol, sell_btc_amount)
                else:
                    order = exchange.create_limit_sell_order(ccxt_symbol, sell_btc_amount, limit_price)
                st.success(f"✅ 매도 성공! ID: {order['id']}")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매도 실패: {e}")

st.divider()

# --- 4. AI 분석 및 판단 섹션 ---
st.subheader("🤖 AI 차트 분석 및 추천 엔진")

if st.button("🔍 AI 차트 분석 시작하기 (Gemini / OpenRouter)", type="primary", use_container_width=True):
    with st.status("🤖 AI가 OKX 실시간 차트 데이터를 분석 중입니다...", expanded=True) as status:
        try:
            status.write("📊 1. 선택된 타임프레임 시세 수집 중...")
            market_data = {
                "symbol": display_symbol,
                "timeframe": timeframe,
                "current_price": current_price,
                "leverage": leverage,
                "usdt_balance": usdt_balance,
                "btc_balance": btc_balance,
                "recent_candles": [
                    {"open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
                    for c in ohlcv[-15:]
                ]
            }

            prompt = f"""
            당신은 신중하고 전문적인 암호화폐 트레이더입니다.
            아래 전달된 실시간 시장 데이터와 잔고 상태를 분석하여 매매 전략을 결정하세요.

            [시장 데이터]
            {json.dumps(market_data, indent=2)}

            [분석 규칙]
            1. 모든 분석 이유("reason")와 판단 설명은 반드시 100% 한국어(한글)로만 작성해야 합니다.
            2. 추세와 거래량을 고려하여 확실한 매수 타점일 때만 "buy", 매도 타점일 때 "sell", 불확실하면 "hold"를 선택하세요.
            3. 응답은 오직 아래 지정된 JSON 양식으로만 응답해야 합니다. 다른 설명은 금지합니다.

            {{
                "decision": "buy" 또는 "sell" 또는 "hold",
                "reason": "기술적 분석에 기반한 구체적인 한국어 판단 이유",
                "percentage": 10~100 사이의 권장 주문 비중 (hold인 경우 0)
            }}
            """

            raw_text = None

            if ai_client:
                try:
                    status.write("🧠 1. Gemini Flash 모델 분석 시도 중...")
                    res = ai_client.models.generate_content(model='gemini-3.8-flash', contents=prompt)
                    raw_text = res.text
                except Exception:
                    status.write("⏳ Gemini 한도 소진/대기. OpenRouter 무료 AI 모음으로 우회합니다.")

            if not raw_text and openrouter_key:
                free_models = ["openrouter/free", "google/gemma-4-31b-it:free", "qwen/qwen3.8-27b:free"]
                headers = {
                    "Authorization": f"Bearer {openrouter_key.strip()}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://streamlit.io",
                    "X-Title": "OKX AI Trading Pro"
                }

                for model_slug in free_models:
                    status.write(f"🧠 OpenRouter 모델({model_slug})에 분석 요청 중...")
                    payload = {"model": model_slug, "messages": [{"role": "user", "content": prompt}]}
                    try:
                        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
                        res_json = res.json()
                        if "choices" in res_json and len(res_json["choices"]) > 0:
                            raw_text = res_json["choices"][0]["message"]["content"]
                            break
                    except Exception:
                        continue

            if not raw_text:
                raise Exception("모든 AI 모델 연결에 실패했습니다. 키 설정을 확인해주세요.")

            clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
            json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            
            if json_match:
                st.session_state.ai_result = json.loads(json_match.group(0))
            else:
                clean_text = clean_text.replace("```json", "").replace("```", "").strip()
                st.session_state.ai_result = json.loads(clean_text)

            status.update(label="✅ AI 차트 분석 완료!", state="complete", expanded=False)

        except Exception as e:
            status.update(label="❌ AI 분석 실패", state="error", expanded=True)
            st.error(f"오류 상세 내용: {e}")

if st.session_state.ai_result:
    result = st.session_state.ai_result
    decision = str(result.get("decision", "hold")).upper()
    reason = result.get("reason", "")
    percentage = result.get("percentage", 0)

    if decision == "BUY":
        st.success(f"### AI 추천: 🟢 {decision} (매수 추천)")
    elif decision == "SELL":
        st.warning(f"### AI 추천: 🔴 {decision} (매도 추천)")
    else:
        st.info(f"### AI 추천: 🟡 {decision} (관망 추천)")

    st.markdown(f"**💡 AI 판단 근거:**\n>{reason}")
    st.markdown(f"**📊 권장 매매 비중:** `{percentage}%`")

st.divider()

# --- 5. 하단 탭: Orders & Assets ---
st.subheader("📋 Orders & Account History")

tab_open, tab_hist, tab_asset = st.tabs(["⏳ 미체결 주문 (Open Orders)", "📜 체결 히스토리 (Order History)", "💼 자산 잔고 (Assets)"])

with tab_open:
    try:
        open_orders = exchange.fetch_open_orders(ccxt_symbol)
        if open_orders:
            open_data = []
            for o in open_orders:
                dt_str = datetime.datetime.fromtimestamp(o['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                open_data.append({
                    "주문 ID": o['id'],
                    "주문 시간": dt_str,
                    "구분": "🟢 Buy" if o['side'] == 'buy' else "🔴 Sell",
                    "가격 (USDT)": f"${o['price']:,.2f}",
                    "수량 (BTC)": f"{o['amount']:.6f}",
                    "상태": o['status']
                })
            st.dataframe(pd.DataFrame(open_data), use_container_width=True)
        else:
            st.info("대기 중인 미체결 주문이 없습니다.")
    except Exception as e:
        st.caption(f"미체결 주문 정보: {e}")

with tab_hist:
    try:
        closed_orders = exchange.fetch_closed_orders(ccxt_symbol, limit=10)
        if closed_orders:
            hist_data = []
            for c in reversed(closed_orders):
                dt_str = datetime.datetime.fromtimestamp(c['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                filled_qty = c.get('filled', c.get('amount', 0))
                avg_p = c.get('price', current_price)
                hist_data.append({
                    "체결 시간": dt_str,
                    "구분": "🟢 Buy" if c['side'] == 'buy' else "🔴 Sell",
                    "평균 체결가": f"${avg_p:,.2f}",
                    "체결 수량": f"{filled_qty:.6f} BTC",
                    "총 체결 금액": f"${filled_qty * avg_p:,.2f} USDT",
                    "상태": c['status']
                })
            st.dataframe(pd.DataFrame(hist_data), use_container_width=True)
        else:
            st.info("최근 체결된 주문 내역이 없습니다.")
    except Exception as e:
        st.caption(f"히스토리 정보: {e}")

with tab_asset:
    btc_val = btc_balance * current_price
    st.markdown(f"""
    | 자산 명 | 보유 수량 | 평가 금액 (USDT) | 비 중 |
    | :--- | :--- | :--- | :--- |
    | **USDT** | `{usdt_balance:,.2f} USDT` | `${usdt_balance:,.2f}` | `{(usdt_balance/total_asset_usdt*100) if total_asset_usdt > 0 else 0:.1f}%` |
    | **BTC** | `{btc_balance:.6f} BTC` | `${btc_val:,.2f}` | `{(btc_val/total_asset_usdt*100) if total_asset_usdt > 0 else 0:.1f}%` |
    """)
