import os
import json
import datetime
import ccxt
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from dotenv import load_dotenv
from google import genai

# 1. 환경 변수 로드 및 페이지 설정
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
    st.session_state.active_tf = "1h"

if "candle_count" not in st.session_state:
    st.session_state.candle_count = 100

# 기본 화면: "office" (차트 분석실)
if "app_view" not in st.session_state:
    st.session_state.app_view = "office"

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

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

# 커스텀 CSS
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
</style>
""", unsafe_allow_html=True)

# 🔒 비밀번호 잠금 기능
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.title("🔒 로그인 필요")
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

# 거래소 및 Gemini AI 클라이언트 초기화
@st.cache_resource
def get_clients():
    api_key = st.secrets.get("OKX_API_KEY") or os.getenv("OKX_API_KEY")
    secret_key = st.secrets.get("OKX_SECRET_KEY") or os.getenv("OKX_SECRET_KEY")
    passphrase = st.secrets.get("OKX_PASSPHRASE") or os.getenv("OKX_PASSPHRASE")
    gemini_api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True)

    ai_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None
    return exchange, ai_client

try:
    exchange, ai_client = get_clients()
except Exception as e:
    st.error(f"거래소/AI 설정 불러오기 실패: {e}")
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

# --- 1. Top Header Bar & 우측 작은 상단 네비게이션 버튼 (🤖 차트분석실 / 📈 매매화면) ---
change_class = "okx-price-up" if change_24h >= 0 else "okx-price-down"
change_sign = "+" if change_24h >= 0 else ""

header_col, btn_office_col, btn_trade_col = st.columns([7.6, 1.2, 1.2])

with header_col:
    st.markdown(f"""
    <div class="okx-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 15px; font-weight: bold;">⬛ {display_symbol}</span>
                <span style="background-color: #2b313a; color: #f0b90b; font-size: 10px; padding: 1px 4px; border-radius: 3px;">Demo Trading</span>
                <span style="background-color: #1e232a; color: #848e9c; font-size: 10px; padding: 1px 4px; border-radius: 3px;">Perp</span>
            </div>
            <div style="display: flex; gap: 12px; font-size: 11px;">
                <div><span style="color: #848e9c;">최근가</span> <span class="{change_class}">${current_price:,.2f}</span></div>
                <div><span style="color: #848e9c;">24h 변동률</span> <span class="{change_class}">{change_sign}{change_24h:.2f}%</span></div>
                <div><span style="color: #848e9c;">총 자산</span> <span style="color: #f0b90b; font-weight: bold;">${total_asset_usdt:,.2f}</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

is_office = (st.session_state.app_view == "office")

with btn_office_col:
    office_btn_kind = "primary" if is_office else "secondary"
    if st.button("🤖 차트분석실", key="nav_office_btn", type=office_btn_kind, use_container_width=True):
        st.session_state.app_view = "office"
        st.rerun()

with btn_trade_col:
    trade_btn_kind = "secondary" if is_office else "primary"
    if st.button("📈 매매화면", key="nav_trade_btn", type=trade_btn_kind, use_container_width=True):
        st.session_state.app_view = "trade"
        st.rerun()


# ==============================================================================
# VIEW 1: [🤖 AI 차트 분석실 화면]
# ==============================================================================
if st.session_state.app_view == "office":
    # 1. 상단 타임프레임 및 과거 봉 개수 옵션
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 3, 5])
    with ctrl_col1:
        selected_tf = st.selectbox("⏱️ 타임프레임(봉)", ["15m", "1h", "4h", "1d"], index=1, key="office_tf_select")
        st.session_state.active_tf = selected_tf
    with ctrl_col2:
        selected_count = st.slider("📊 과거 봉 개수 불러오기", min_value=30, max_value=300, value=100, step=10, key="office_count_select")
        st.session_state.candle_count = selected_count

    timeframe = st.session_state.active_tf
    limit_cnt = st.session_state.candle_count

    try:
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit_cnt)
    except Exception:
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe='1h', limit=100)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA50'] = df['close'].rolling(window=50).mean()
    std20 = df['close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (std20 * 2)
    df['BB_Lower'] = df['MA20'] - (std20 * 2)

    # 2. 분석실 상단 넓은 과거 차트
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
        height=320,
        margin=dict(l=10, r=50, t=10, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=False, hovermode="x unified", dragmode='pan'
    )
    fig_office.update_yaxes(side="right", gridcolor=grid_color, showgrid=True)
    fig_office.update_xaxes(gridcolor=grid_color, showgrid=True)

    st.plotly_chart(fig_office, use_container_width=True, config={'scrollZoom': True, 'displaylogo': False})

    # 3. 과거 차트 기반 AI 분석 실행 버튼
    if st.button(f"🔍 과거 {limit_cnt}개 봉 기반 AI 분석 실행하기", type="primary", use_container_width=True):
        if ai_client:
            with st.spinner("AI가 불러온 과거 시세 흐름과 지지/저항 라인을 정밀 분석 중입니다..."):
                try:
                    market_data = {
                        "symbol": ccxt_symbol,
                        "current_price": current_price,
                        "usdt_balance": usdt_balance,
                        "btc_balance": btc_balance,
                        "timeframe": timeframe,
                        "candle_count": limit_cnt,
                        "lowest_price": min(df['low']),
                        "highest_price": max(df['high']),
                        "recent_candles": [
                            {"open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
                            for c in ohlcv[-20:]
                        ]
                    }

                    prompt = f"""
                    당신은 암호화폐 전문 트레이더 AI입니다.
                    전달된 과거 {limit_cnt}개의 시세 흐름 및 차트 데이터를 바탕으로 종합 분석 판단을 내리세요.

                    [시장 데이터]
                    {json.dumps(market_data, indent=2)}

                    [응답 규칙]
                    반드시 아래 JSON 양식으로만 응답해야 합니다.
                    {{
                        "decision": "buy" 또는 "sell" 또는 "hold",
                        "reason": "과거 지지/저항 라인 및 흐름에 기반한 상세한 판단 이유",
                        "percentage": 10~100 사이의 권장 주문 비중 (hold인 경우 0)
                    }}
                    """

                    response = ai_client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=prompt
                    )

                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    st.session_state.ai_result = json.loads(raw_text)

                except Exception as e:
                    st.error(f"AI 분석 중 오류가 발생했습니다: {e}")

    # AI 결과 표시
    if st.session_state.ai_result:
        res = st.session_state.ai_result
        dec = res.get("decision", "hold").upper()
        reas = res.get("reason", "")
        perc = res.get("percentage", 0)

        if dec == "BUY":
            st.success(f"### 🟢 AI 추천: BUY (매수 추천) - 권장 비중 {perc}%")
        elif dec == "SELL":
            st.warning(f"### 🔴 AI 추천: SELL (매도 추천) - 권장 비중 {perc}%")
        else:
            st.info(f"### 🟡 AI 추천: HOLD (관망 추천)")
        st.markdown(f"**💡 판단 근거:** {reas}")

    # 4. 하단 픽셀 아트 AI 분석 사무실 (ANALYST FLOOR)
    st.markdown("### 🏢 PIXEL TRADING FLOOR · AI 사무실")

    office_col1, office_col2, office_col3 = st.columns([3.5, 3.5, 3.0])

    with office_col1:
        st.markdown("""
        <div class="pixel-card">
            <div class="pixel-card-header">◆ 애널리스트 팀 (ANALYST TEAM)</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 6px;">
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 TARO (기술적 분석)</b><br>
                    <span style="color:#848e9c; font-size:10px;">MA20/MA50 이동평균선 및 과거 차트 지지선 체크 중.</span>
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 DIANA (기본적 분석)</b><br>
                    <span style="color:#848e9c; font-size:10px;">24시간 거래량 및 계좌 USDT 비중 추적.</span>
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 NOVA (뉴스 분석)</b><br>
                    <span style="color:#848e9c; font-size:10px;">주요 암호화폐 관련 매크로 호재 및 악재 트래킹.</span>
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">👾 VIBE (센티먼트)</b><br>
                    <span style="color:#848e9c; font-size:10px;">시장 심리지수 반영 및 변동성 평가.</span>
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
                    <b style="color:#26a69a;">🟢 BULL (매수 근거)</b>: 과거 지지선 부근 가격 형성 시 반등 시도.
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#ef5350;">🔴 BEAR (매도 근거)</b>: 볼린저밴드 상단 도달 시 단기 조정 주의.
                </div>
                <div style="background:#17100b; padding:6px; border:1px solid #3d2b1f;">
                    <b style="color:#f0b90b;">🛡️ SAFE / RISKY</b>: 손절 한도 설정 필수 및 레버리지 노출 관리.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with office_col3:
        st.markdown("""
        <div class="pixel-card">
            <div class="pixel-card-header">◆ 트레이딩 본부 (AGENT CONSOLE)</div>
            <div style="background:#17100b; padding:8px; border:1px solid #3d2b1f; text-align:center; margin-top:6px;">
                <span style="color:#848e9c; font-size:10px;">수석 추천 상태</span><br>
                <b style="font-size:18px; color:#26a69a;">분석 준비 완료</b><br>
                <span style="color:#f0b90b; font-size:11px;">상단 AI 분석 버튼을 클릭하세요</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.stop()


# ==============================================================================
# VIEW 2: [📈 매매 화면]
# ==============================================================================

# 상단 지표 및 타임프레임 바
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

# 차트 및 수동 주문 패널
chart_col, trade_col = st.columns([7.8, 2.2])

with chart_col:
    timeframe = st.session_state.active_tf
    limit_cnt = st.session_state.get("candle_count", 100)

    try:
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

    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name='BTC/USDT',
        increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',
        decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'
    ))

    if st.session_state.show_ma20:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA20'], line=dict(color='#ff9800', width=1.5), name='MA20'))
    if st.session_state.show_ma50:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA50'], line=dict(color='#2196f3', width=1.5), name='MA50'))

    fig.update_layout(
        paper_bgcolor=card_bg, plot_bgcolor=card_bg,
        font=dict(color=text_color, size=11),
        height=580,
        margin=dict(l=10, r=60, t=15, b=15),
        xaxis_rangeslider_visible=False,
        showlegend=False, hovermode="x unified", dragmode='pan'
    )
    fig.update_yaxes(side="right", gridcolor=grid_color, showgrid=True)
    fig.update_xaxes(gridcolor=grid_color, showgrid=True)

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displaylogo': False})

# 우측 주문 패널
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
