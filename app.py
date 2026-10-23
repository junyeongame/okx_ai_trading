import os
import datetime
import ccxt
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from dotenv import load_dotenv

# 1. 페이지 기본 설정 및 환경 변수 로드
load_dotenv()

st.set_page_config(
    page_title="OKX AI Pro Trading Floor",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 🔒 세션 상태 초기화
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Dark (다크 모드)"

if "active_tf" not in st.session_state:
    st.session_state.active_tf = "5m"

if "app_view" not in st.session_state:
    st.session_state.app_view = "trade"  # "trade" 또는 "office"

# 지표 토글 세션 상태 초기화
default_defaults = {
    'show_ma20': True,
    'show_ma50': True,
    'show_ma200': True,
    'show_ema20': True,
    'show_bollinger': True,
    'show_volume': True,
    'show_rsi': False,
    'show_macd': False
}

for k, default_val in default_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = default_val

# 동적 테마 색상 정의
is_dark = "Dark" in st.session_state.theme_mode

bg_color = "#000000" if is_dark else "#ffffff"
card_bg = "#08090c" if is_dark else "#f8f9fa"
input_bg = "#131722" if is_dark else "#f0f2f5"
text_color = "#d1d4dc" if is_dark else "#111827"
border_color = "#2a2e39" if is_dark else "#d1d5db"
grid_color = "#1e222d" if is_dark else "#e5e7eb"

# 기본 스타일 설정
st.markdown(f"""
<style>
    /* 1. 사이드바 숨기기 */
    [data-testid="stSidebar"] {{ display: none !important; }}
    
    /* 2. 메인 테마 */
    .stApp, div[data-testid="stHeader"], div[data-testid="stToolbar"] {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}

    div[data-testid="stHorizontalBlock"] {{ gap: 6px !important; }}

    div[data-testid="column"] > div {{
        background-color: {card_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
        padding: 6px 10px !important;
    }}

    label, p, span, h1, h2, h3, h4, h5, h6, div[data-testid="stWidgetLabel"], div[data-testid="stMarkdownContainer"] {{
        color: {text_color} !important;
    }}

    div[data-baseweb="input"], div[data-baseweb="input"] > div, div[data-baseweb="base-input"], input, textarea, select {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
    }}

    /* 버튼 기본 및 Active 불빛 스타일 */
    div.stButton > button {{
        background-color: {input_bg} !important;
        color: #848e9c !important;
        border: 1px solid #2a2e39 !important;
        border-radius: 3px !important;
        padding: 1px 4px !important;
        min-height: 24px !important;
        height: 24px !important;
        font-size: 11px !important;
        font-weight: 500 !important;
    }}

    div.stButton > button[kind="primary"] {{
        background-color: #f0b90b !important;
        color: #000000 !important;
        border: 1px solid #f0b90b !important;
        font-weight: bold !important;
        box-shadow: 0 0 6px rgba(240, 185, 11, 0.6) !important;
    }}

    div.stButton > button:hover {{
        border-color: #f0b90b !important;
        color: #ffffff !important;
    }}

    /* OKX Header Bar */
    .okx-header {{
        background-color: {input_bg};
        padding: 6px 14px;
        border-radius: 4px;
        border: 1px solid {border_color};
        margin-bottom: 6px;
    }}
    .okx-price-up {{ color: #26a69a; font-weight: bold; }}
    .okx-price-down {{ color: #ef5350; font-weight: bold; }}

    /* 🎮 픽셀/도트 테마 오피스 전용 CSS */
    .pixel-floor-container {{
        background-color: #3d2b1f;
        background-image: linear-gradient(rgba(0,0,0,0.3) 1px, transparent 1px),
                          linear-gradient(90deg, rgba(0,0,0,0.3) 1px, transparent 1px);
        background-size: 20px 20px;
        border: 3px solid #8b6b47;
        border-radius: 6px;
        padding: 12px;
        margin-top: 10px;
    }}

    .pixel-card {{
        background-color: #241a14;
        border: 2px solid #5c432d;
        border-radius: 4px;
        padding: 8px;
        color: #d1d4dc;
        font-family: 'Courier New', monospace;
        font-size: 11px;
    }}

    .pixel-card-header {{
        background-color: #17100b;
        border-bottom: 1px solid #5c432d;
        color: #f0b90b;
        font-weight: bold;
        padding: 2px 4px;
        margin-bottom: 6px;
        font-size: 11px;
    }}

    .agent-avatar {{
        display: inline-block;
        width: 18px;
        height: 18px;
        background-color: #f0b90b;
        border-radius: 2px;
        margin-right: 4px;
        vertical-align: middle;
    }}
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

# 거래소 클라이언트 초기화
@st.cache_resource
def get_clients():
    api_key = os.getenv("OKX_API_KEY") or st.secrets.get("OKX_API_KEY")
    secret_key = os.getenv("OKX_SECRET_KEY") or st.secrets.get("OKX_SECRET_KEY")
    passphrase = os.getenv("OKX_PASSPHRASE") or st.secrets.get("OKX_PASSPHRASE")

    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True)
    return exchange

try:
    exchange = get_clients()
except Exception as e:
    st.error(f"거래소 설정 오류: {e}")
    st.stop()

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

except Exception as e:
    st.error(f"거래소 데이터 로드 실패: {e}")
    st.stop()

# --- 1. Top Header Bar & 우측 상단 화면 전환 (투자 분석실 / 매매 화면) ---
change_class = "okx-price-up" if change_24h >= 0 else "okx-price-down"
change_sign = "+" if change_24h >= 0 else ""

header_col, nav_col = st.columns([8.2, 1.8])

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

with nav_col:
    is_office = (st.session_state.app_view == "office")
    btn_label = "📈 매매 화면으로 이동" if is_office else "🏢 투자 분석실 이동"
    btn_kind = "primary" if is_office else "secondary"
    
    if st.button(btn_label, key="toggle_app_view", type=btn_kind, use_container_width=True):
        st.session_state.app_view = "trade" if is_office else "office"
        st.rerun()

# ==============================================================================
# VIEW 1: [🏢 AI 투자 분석실 화면 (사무실 테마)]
# ==============================================================================
if st.session_state.app_view == "office":
    # 1. 상단 타임프레임 컨트롤
    tf_cols = st.columns([0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 11])
    primary_tfs = [("1s", "1s"), ("1m", "1m"), ("5m", "5m"), ("15m", "15m"), ("1h", "1h"), ("4h", "4h"), ("1D", "1d")]
    for idx, (label, code) in enumerate(primary_tfs):
        with tf_cols[idx]:
            is_active = (st.session_state.active_tf == code)
            b_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"btn_office_tf_{code}", type=b_type, use_container_width=True):
                st.session_state.active_tf = code
                st.rerun()

    timeframe = st.session_state.active_tf
    try:
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=80)
    except Exception:
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe='5m', limit=80)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
    std20 = df['close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (std20 * 2)
    df['BB_Lower'] = df['MA20'] - (std20 * 2)

    # 2. 분석실 상단 차트 (슬림형 트레이딩뷰 스타일)
    fig_office = make_subplots(rows=1, cols=1)
    fig_office.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name='BTC/USDT',
        increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',
        decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'
    ))
    fig_office.add_trace(go.Scatter(x=df['datetime'], y=df['MA20'], line=dict(color='#ff9800', width=1.2), name='MA20'))
    fig_office.add_trace(go.Scatter(x=df['datetime'], y=df['MA50'], line=dict(color='#2196f3', width=1.2), name='MA50'))
    fig_office.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Upper'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Upper'))
    fig_office.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Lower'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Lower'))

    fig_office.update_layout(
        paper_bgcolor=card_bg, plot_bgcolor=card_bg,
        font=dict(color=text_color, size=10),
        height=280,
        margin=dict(l=10, r=50, t=10, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=False, hovermode="x unified", dragmode='pan'
    )
    fig_office.update_yaxes(side="right", gridcolor=grid_color, showgrid=True)
    fig_office.update_xaxes(gridcolor=grid_color, showgrid=True)

    st.plotly_chart(fig_office, use_container_width=True, config={'scrollZoom': True, 'displaylogo': False})

    # 3. 하단 픽셀 아트 AI 분석 사무실 (ANALYST FLOOR)
    st.markdown("### 🏢 PIXEL TRADING FLOOR · AI 사무실")

    office_col1, office_col2, office_col3 = st.columns([3.5, 3.5, 3.0])

    with office_col1:
        st.markdown("""
        <div class="pixel-card">
            <div class="pixel-card-header">◆ 애널리스트 팀 (ANALYST TEAM)</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 6px;">
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 TARO (기술적 분석)</b><br>
                    <span style="color:#848e9c; font-size:10px;">MA20/MA50 정배열 확인 중. 최근 20일선 지지력 우수.</span>
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 DIANA (기본적 분석)</b><br>
                    <span style="color:#848e9c; font-size:10px;">BTC 시가총액 유입 지속, 24시간 거래량 견조함 유지.</span>
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 NOVA (뉴스 분석)</b><br>
                    <span style="color:#848e9c; font-size:10px;">주요 암호화폐 관련 매크로 호재성 뉴스 지속 모니터링.</span>
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 VIBE (센티먼트)</b><br>
                    <span style="color:#848e9c; font-size:10px;">공포 탐욕 지수: 58/100 (중립 이상 중기 매수심리).</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with office_col2:
        st.markdown("""
        <div class="pixel-card">
            <div class="pixel-card-header">◆ 리서치 & 리스크 분과 (RESEARCH & RISK)</div>
            <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 6px;">
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#26a69a;">🟢 BULL (매수 근거)</b>: MA20 상승 돌파 및 거래량 동반 매수세 형성.
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#ef5350;">🔴 BEAR (매도 근거)</b>: 볼린저밴드 상단 저항선 접근에 따른 단기 조정 가능성.
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">🛡️ SAFE / RISKY</b>: 변동성 관리 상향, 레버리지 10x 이하 권장.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with office_col3:
        st.markdown("""
        <div class="pixel-card">
            <div class="pixel-card-header">◆ 트레이딩 본부 (AGENT CONSOLE)</div>
            <div style="background:#17100b; padding:8px; border:1px solid #3d2b1f; text-align:center; margin-top:6px;">
                <span style="color:#848e9c; font-size:10px;">최종 매매 수석 추천</span><br>
                <b style="font-size:18px; color:#26a69a;">LONG (매수)</b><br>
                <span style="color:#f0b90b; font-size:11px;">신뢰도 점수: 78%</span>
            </div>
            <div style="margin-top:8px; color:#848e9c; font-size:10px;">
                * <b>ACE (수석 트레이더)</b>: 이평선 및 모멘텀 우위 판단.<br>
                * <b>PM (포트폴리오 매니저)</b>: 1회 주문 비중 25% 이내 권장.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.stop()

# ==============================================================================
# VIEW 2: [📈 매매 화면 (기존 매매 트레이딩 패널)]
# ==============================================================================

# --- 2. 상단 타임프레임 및 지표 온/오프 토글 바 ---
tf_cols = st.columns([0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.9, 0.65, 0.65, 0.7, 0.7, 0.7, 0.7, 0.65, 0.65])

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

# 지표 토글 버튼
indicators = [
    ("MA20", "show_ma20", 8),
    ("MA50", "show_ma50", 9),
    ("MA200", "show_ma200", 10),
    ("EMA20", "show_ema20", 11),
    ("볼린저", "show_bollinger", 12),
    ("거래량", "show_volume", 13),
    ("RSI", "show_rsi", 14),
    ("MACD", "show_macd", 15)
]

for label, key, col_idx in indicators:
    with tf_cols[col_idx]:
        is_on = st.session_state[key]
        b_type = "primary" if is_on else "secondary"
        if st.button(label, key=f"btn_ind_{key}", type=b_type, use_container_width=True):
            st.session_state[key] = not st.session_state[key]
            st.rerun()

# --- 3. 메인 2컬럼 레이아웃 (차트 | 주문 패널) ---
chart_col, trade_col = st.columns([7.8, 2.2])

# --- [LEFT: 차트 패널] ---
with chart_col:
    timeframe = st.session_state.active_tf

    try:
        limit_cnt = 100
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit_cnt)
    except Exception:
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe='5m', limit=100)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['MA200'] = df['close'].rolling(window=200).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()

    std20 = df['close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (std20 * 2)
    df['BB_Lower'] = df['MA20'] - (std20 * 2)

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    rows_cnt = 1
    row_heights = [0.7]

    has_volume = st.session_state.show_volume
    has_rsi = st.session_state.show_rsi
    has_macd = st.session_state.show_macd

    extra_rows = [has_volume, has_rsi, has_macd].count(True)
    if extra_rows > 0:
        rows_cnt += extra_rows
        sub_h = 0.3 / extra_rows
        row_heights = [0.7] + [sub_h] * extra_rows

    fig = make_subplots(
        rows=rows_cnt, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=row_heights
    )

    fig.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name='BTC/USDT',
        increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',
        decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'
    ), row=1, col=1)

    if st.session_state.show_ma20:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA20'], line=dict(color='#ff9800', width=1.5), name='MA20'), row=1, col=1)
    if st.session_state.show_ma50:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA50'], line=dict(color='#2196f3', width=1.5), name='MA50'), row=1, col=1)
    if st.session_state.show_ma200:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA200'], line=dict(color='#9c27b0', width=1.5), name='MA200'), row=1, col=1)
    if st.session_state.show_ema20:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['EMA20'], line=dict(color='#00e676', width=1.5), name='EMA20'), row=1, col=1)
    if st.session_state.show_bollinger:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Upper'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Upper'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Lower'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Lower'), row=1, col=1)

    fig.add_hline(
        y=current_price, line_dash="dash", line_color="#26a69a", line_width=1.2,
        annotation_text=f" {current_price:,.1f}", annotation_position="right",
        annotation_font=dict(color="#ffffff", size=11), annotation_bgcolor="#26a69a",
        row=1, col=1
    )

    curr_row = 2
    if has_volume:
        vol_colors = ['#26a69a' if r['close'] >= r['open'] else '#ef5350' for _, r in df.iterrows()]
        fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=vol_colors, name='Volume'), row=curr_row, col=1)
        curr_row += 1

    if has_rsi:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['RSI'], line=dict(color='#f0b90b', width=1.2), name='RSI'), row=curr_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#ef5350", line_width=1, row=curr_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#26a69a", line_width=1, row=curr_row, col=1)
        curr_row += 1

    if has_macd:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MACD'], line=dict(color='#2196f3', width=1.2), name='MACD'), row=curr_row, col=1)
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MACD_Signal'], line=dict(color='#ff9800', width=1.2), name='Signal'), row=curr_row, col=1)
        hist_colors = ['#26a69a' if v >= 0 else '#ef5350' for v in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df['datetime'], y=df['MACD_Hist'], marker_color=hist_colors, name='Hist'), row=curr_row, col=1)

    fig.update_layout(
        paper_bgcolor=card_bg, plot_bgcolor=card_bg,
        font=dict(color=text_color, size=11),
        height=580,
        margin=dict(l=10, r=60, t=15, b=15),
        xaxis_rangeslider_visible=False,
        showlegend=False, hovermode="x unified", dragmode='pan'
    )

    fig.update_yaxes(side="right", gridcolor=grid_color, zerolinecolor=grid_color, showgrid=True, fixedrange=False)
    fig.update_xaxes(gridcolor=grid_color, zerolinecolor=grid_color, showgrid=True, fixedrange=False)

    st.plotly_chart(
        fig, use_container_width=True,
        config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToRemove': ['select2d', 'lasso2d'], 'displaylogo': False}
    )

# --- [RIGHT: 수동 주문 패널 카드] ---
with trade_col:
    st.markdown("<div style='font-weight: bold; font-size: 13px; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #2a2e39;'>⚡ Trade Panel</div>", unsafe_allow_html=True)
    
    leverage = st.slider("🎯 레버리지 배율 (1x ~ 50x)", min_value=1, max_value=50, value=10, step=1)
    order_mode = st.radio("주문 타입", ["지정가 (Limit)", "시장가 (Market)"], horizontal=True)
    
    limit_price = st.number_input("지정가 (USDT)", value=float(current_price), step=10.0, key="limit_price_input")

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
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매도 실패: {e}")

st.divider()

# --- 4. 하단 탭: Orders & Assets ---
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
