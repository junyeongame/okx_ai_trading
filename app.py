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
    st.session_state.theme_mode = "Light (밝은 모드)"

if "active_tf" not in st.session_state:
    st.session_state.active_tf = "1m"

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

if "app_view" not in st.session_state:
    st.session_state.app_view = "trade"

if "ai_result_timeframe" not in st.session_state:
    st.session_state.ai_result_timeframe = None

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

# 동적 CSS 테마 색상 설정
is_dark = "Dark" in st.session_state.theme_mode

bg_color = "#0b0e11" if is_dark else "#ffffff"
card_bg = "#11151c" if is_dark else "#ffffff"
input_bg = "#1e2329" if is_dark else "#f5f7fa"
text_color = "#eaecef" if is_dark else "#1e2329"
muted_color = "#848e9c" if is_dark else "#707a8a"
border_color = "#2b3139" if is_dark else "#e1e5eb"
grid_color = "#252a32" if is_dark else "#e8ecf1"

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ display: none !important; }}

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"] {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}

    [data-testid="stHorizontalBlock"] {{ gap: 6px !important; }}

    [data-testid="column"] > div {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 5px;
        padding: 6px 10px;
    }}

    /* 텍스트 색상은 상속시키되 span의 인라인 색상(상승/하락색)은 덮어쓰지 않음 */
    label, p, h1, h2, h3, h4, h5, h6,
    [data-testid="stWidgetLabel"],
    [data-testid="stMarkdownContainer"] {{
        color: {text_color} !important;
    }}

    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] * {{ color: {muted_color}; }}

    [data-baseweb="input"] > div,
    [data-baseweb="base-input"],
    [data-baseweb="select"] > div,
    input, textarea, select {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border-color: {border_color} !important;
        border-radius: 4px !important;
    }}

    [data-testid="stButton"] > button {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
        padding: 1px 4px !important;
        min-height: 26px !important;
        height: 26px !important;
        font-size: 11px !important;
        font-weight: 500 !important;
    }}

    [data-testid="stButton"] > button[kind="primary"] {{
        background-color: #f0b90b !important;
        color: #111111 !important;
        border-color: #f0b90b !important;
        font-weight: 700 !important;
        box-shadow: 0 0 6px rgba(240, 185, 11, 0.35) !important;
    }}

    [data-testid="stButton"] > button:hover {{
        border-color: #f0b90b !important;
    }}

    button[data-testid="stBaseButton-popover"],
    [data-testid="stPopover"] > button {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        min-height: 26px !important;
        height: 26px !important;
        font-size: 11px !important;
        padding: 0 6px !important;
        border-radius: 4px !important;
    }}

    [data-testid="stPopoverBody"],
    [data-baseweb="popover"] {{
        background-color: {card_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 6px !important;
    }}

    .okx-header {{
        background-color: {input_bg};
        color: {text_color};
        padding: 7px 12px;
        border-radius: 5px;
        border: 1px solid {border_color};
        margin-bottom: 6px;
    }}
    .okx-price-up {{ color: #26a69a !important; font-weight: bold; }}
    .okx-price-down {{ color: #ef5350 !important; font-weight: bold; }}
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

except Exception as e:
    st.error(f"거래소 데이터 로드 실패: {e}")
    st.stop()

# --- 화면 전환: 매매 화면 / AI 분석 차트실 ---
nav_left, nav_right = st.columns([1, 1])
with nav_left:
    if st.button("📈 매매 화면", type="primary" if st.session_state.app_view == "trade" else "secondary", use_container_width=True, key="nav_trade"):
        st.session_state.app_view = "trade"
        st.rerun()
with nav_right:
    if st.button("🤖 AI 분석 차트실", type="primary" if st.session_state.app_view == "analysis" else "secondary", use_container_width=True, key="nav_analysis"):
        st.session_state.app_view = "analysis"
        st.rerun()

if st.session_state.app_view == "analysis":
    st.markdown("""
    <style>
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background: #090a0d !important; color: #e7d7b1 !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] > div {
            background: #17130e !important; border: 2px solid #9a7947 !important;
            border-radius: 0 !important; box-shadow: 3px 3px 0 #050506;
        }
        [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], label,
        h1, h2, h3, h4, p { color: #e7d7b1 !important; }
        [data-testid="stButton"] > button {
            background: #17130e !important; color: #f0c75e !important;
            border: 2px solid #a98242 !important; border-radius: 0 !important;
            font-family: 'Courier New', monospace !important; font-weight: 700 !important;
            box-shadow: 2px 2px 0 #050506 !important;
        }
        [data-testid="stButton"] > button[kind="primary"] {
            background: #e0b441 !important; color: #15110a !important;
        }
        .pixel-banner {
            background: #08090d; border: 2px solid #bd984d; padding: 10px 14px;
            margin: 4px 0 10px; font-family: 'Courier New', monospace;
            box-shadow: 4px 4px 0 #030304; color: #f1ce70;
        }
        .pixel-floor {
            background-color: #674f31;
            background-image: linear-gradient(rgba(18,13,8,.24) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(18,13,8,.24) 1px, transparent 1px);
            background-size: 18px 18px; border: 2px solid #b2935b;
            padding: 10px; margin: 8px 0; box-shadow: inset 0 0 0 3px #382a1b;
        }
        .pixel-agent {
            background: #3f301e; border: 2px solid #c2a16a; padding: 9px;
            min-height: 100px; font-family: 'Courier New', monospace;
            box-shadow: 3px 3px 0 #080808;
        }
        .pixel-console {
            background: #111117; border: 2px solid #6f6048; padding: 9px;
            min-height: 100px; font-family: 'Courier New', monospace;
            box-shadow: 3px 3px 0 #080808;
        }
        .pixel-agent-title { color: #f0c75e; font-weight: bold; font-size: 13px; }
        .pixel-agent-body { color: #ddd3bd; font-size: 11px; line-height: 1.45; }
        .pixel-console { border-left: 4px solid #f0c75e; }
        [data-testid="stPlotlyChart"] { border: 2px solid #a98242; box-shadow: 3px 3px 0 #050506; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="pixel-banner">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap">
        <div><b>◆ BTC AI ANALYSIS ROOM</b><br><span style="color:#aaa080">AGENT FLOOR · TECHNICAL SIGNALS · LIVE MARKET</span></div>
        <div style="text-align:right"><b style="font-size:20px">BTC/USDT&nbsp; ${current_price:,.2f}</b><br>
          <span style="color:{'#35d07f' if change_24h >= 0 else '#ff6464'}">24H {change_24h:+.2f}%</span>
          &nbsp; <span style="color:#7bd8b0">● DEMO MARKET</span>
        </div>
      </div>
    </div>
    <div style="color:#c6b58f;font:12px 'Courier New',monospace;margin:0 0 8px">
      차트 분석과 판단 근거는 이 분석실에서 확인하고, 주문은 <b>매매 화면</b>에서 진행하세요.
    </div>
    """, unsafe_allow_html=True)

    analysis_tf_options = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "2d", "3d"]
    if st.session_state.active_tf not in analysis_tf_options:
        st.session_state.active_tf = "5m"
    analysis_tf = st.selectbox(
        "분석 타임프레임",
        analysis_tf_options,
        index=analysis_tf_options.index(st.session_state.active_tf),
        key="analysis_tf_select",
    )
    st.session_state.active_tf = analysis_tf

    try:
        analysis_ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe=analysis_tf, limit=150)
        analysis_df = pd.DataFrame(
            analysis_ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        analysis_df["datetime"] = pd.to_datetime(analysis_df["timestamp"], unit="ms")
        analysis_df["MA20"] = analysis_df["close"].rolling(window=20).mean()
        analysis_df["MA50"] = analysis_df["close"].rolling(window=50).mean()
        analysis_df["EMA20"] = analysis_df["close"].ewm(span=20, adjust=False).mean()
        std20 = analysis_df["close"].rolling(window=20).std()
        analysis_df["BB_Upper"] = analysis_df["MA20"] + 2 * std20
        analysis_df["BB_Lower"] = analysis_df["MA20"] - 2 * std20

        delta = analysis_df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        analysis_df["RSI"] = 100 - (100 / (1 + rs))
        ema12 = analysis_df["close"].ewm(span=12, adjust=False).mean()
        ema26 = analysis_df["close"].ewm(span=26, adjust=False).mean()
        analysis_df["MACD"] = ema12 - ema26
        analysis_df["MACD_Signal"] = analysis_df["MACD"].ewm(span=9, adjust=False).mean()
        analysis_df["MACD_Hist"] = analysis_df["MACD"] - analysis_df["MACD_Signal"]

        analysis_fig = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.025,
            row_heights=[0.58, 0.14, 0.14, 0.14],
            subplot_titles=("BTC/USDT · 가격 및 추세", "거래량", "RSI (14)", "MACD (12, 26, 9)"),
        )
        analysis_fig.add_trace(
            go.Candlestick(
                x=analysis_df["datetime"],
                open=analysis_df["open"],
                high=analysis_df["high"],
                low=analysis_df["low"],
                close=analysis_df["close"],
                name="BTC/USDT",
                increasing_line_color="#26a69a",
                increasing_fillcolor="#26a69a",
                decreasing_line_color="#ef5350",
                decreasing_fillcolor="#ef5350",
            ),
            row=1,
            col=1,
        )
        for name, color in (("MA20", "#ff9800"), ("MA50", "#2196f3"), ("EMA20", "#00a86b")):
            analysis_fig.add_trace(
                go.Scatter(x=analysis_df["datetime"], y=analysis_df[name], name=name, line=dict(color=color, width=1.3)),
                row=1,
                col=1,
            )
        analysis_fig.add_trace(
            go.Scatter(x=analysis_df["datetime"], y=analysis_df["BB_Upper"], name="볼린저 상단", line=dict(color="#7e57c2", width=1, dash="dot")),
            row=1,
            col=1,
        )
        analysis_fig.add_trace(
            go.Scatter(x=analysis_df["datetime"], y=analysis_df["BB_Lower"], name="볼린저 하단", line=dict(color="#7e57c2", width=1, dash="dot")),
            row=1,
            col=1,
        )
        vol_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(analysis_df["close"], analysis_df["open"])]
        analysis_fig.add_trace(
            go.Bar(x=analysis_df["datetime"], y=analysis_df["volume"], marker_color=vol_colors, name="거래량"),
            row=2,
            col=1,
        )
        analysis_fig.add_trace(
            go.Scatter(x=analysis_df["datetime"], y=analysis_df["RSI"], name="RSI", line=dict(color="#f0b90b", width=1.3)),
            row=3,
            col=1,
        )
        analysis_fig.add_hline(y=70, line_dash="dash", line_color="#ef5350", row=3, col=1)
        analysis_fig.add_hline(y=30, line_dash="dash", line_color="#26a69a", row=3, col=1)
        analysis_fig.add_trace(
            go.Scatter(x=analysis_df["datetime"], y=analysis_df["MACD"], name="MACD", line=dict(color="#2196f3", width=1.2)),
            row=4,
            col=1,
        )
        analysis_fig.add_trace(
            go.Scatter(x=analysis_df["datetime"], y=analysis_df["MACD_Signal"], name="Signal", line=dict(color="#ff9800", width=1.2)),
            row=4,
            col=1,
        )
        macd_colors = ["#26a69a" if value >= 0 else "#ef5350" for value in analysis_df["MACD_Hist"].fillna(0)]
        analysis_fig.add_trace(
            go.Bar(x=analysis_df["datetime"], y=analysis_df["MACD_Hist"], marker_color=macd_colors, name="MACD 히스토그램"),
            row=4,
            col=1,
        )
        analysis_fig.update_layout(
            paper_bgcolor="#11100d",
            plot_bgcolor="#11100d",
            font=dict(color="#e7d7b1", size=10, family="Courier New, monospace"),
            height=640,
            margin=dict(l=8, r=45, t=35, b=8),
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        )
        analysis_fig.update_yaxes(side="right", gridcolor="#403725", zerolinecolor="#403725", showgrid=True)
        analysis_fig.update_xaxes(gridcolor="#403725", zerolinecolor="#403725", showgrid=True)
        latest = analysis_df.iloc[-1]
        chart_room_col, console_room_col = st.columns([3.25, 1])
        with chart_room_col:
            st.plotly_chart(analysis_fig, use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
        with console_room_col:
            rsi_console = f"{float(latest['RSI']):.1f}" if pd.notna(latest["RSI"]) else "N/A"
            macd_state = "BULLISH / MACD ABOVE SIGNAL" if pd.notna(latest["MACD"]) and pd.notna(latest["MACD_Signal"]) and latest["MACD"] >= latest["MACD_Signal"] else "CAUTION / MACD BELOW SIGNAL"
            st.markdown(f"""
            <div class="pixel-console">
              <div style="color:#f0c75e;font-weight:bold;font-size:13px">◆ AGENT CONSOLE</div>
              <hr style="border-color:#4c412e">
              <div class="pixel-agent-body"><b>STATUS</b> · MARKET LINKED<br>
              <b>PAIR</b> · BTC/USDT<br><b>TF</b> · {analysis_tf}<br>
              <b>RSI</b> · {rsi_console}<br><b>MACD</b> · {macd_state}</div>
              <hr style="border-color:#4c412e">
              <div style="color:#8fe0ac;font-size:11px">▶ 분석 대기 중<br>AI 버튼을 눌러 판단 논리를 생성하세요.</div>
            </div>
            """, unsafe_allow_html=True)
        metric_cols = st.columns(4)
        metric_cols[0].metric("최근가", f"${float(latest['close']):,.2f}")
        metric_cols[1].metric("RSI(14)", f"{float(latest['RSI']):.1f}" if pd.notna(latest["RSI"]) else "계산 중")
        metric_cols[2].metric("MACD", f"{float(latest['MACD']):.2f}" if pd.notna(latest["MACD"]) else "계산 중")
        metric_cols[3].metric("타임프레임", analysis_tf)

        ma20_status = "가격이 20주기선 위" if pd.notna(latest["MA20"]) and latest["close"] >= latest["MA20"] else "가격이 20주기선 아래"
        rsi_status = "과매수 주의" if pd.notna(latest["RSI"]) and latest["RSI"] >= 70 else "과매도 주의" if pd.notna(latest["RSI"]) and latest["RSI"] <= 30 else "중립 모멘텀"
        macd_status = "MACD 우위" if pd.notna(latest["MACD"]) and pd.notna(latest["MACD_Signal"]) and latest["MACD"] >= latest["MACD_Signal"] else "시그널 우위"
        st.markdown('<div class="pixel-floor"><b style="color:#ffe08a;font-family:Courier New,monospace">◆ ANALYST FLOOR · 기술 지표 담당 에이전트</b></div>', unsafe_allow_html=True)
        floor_cols = st.columns([1, 1, 1, 1.15])
        floor_cards = [
            ("🧭 TARO · TREND", ma20_status + f"<br>MA20 {float(latest['MA20']):,.2f}" if pd.notna(latest["MA20"]) else "MA20 데이터 대기"),
            ("📈 DIANA · MOMENTUM", rsi_status + (f"<br>RSI {float(latest['RSI']):.1f}" if pd.notna(latest["RSI"]) else "")),
            ("⚡ BULL · MACD", macd_status + (f"<br>MACD {float(latest['MACD']):.2f}" if pd.notna(latest["MACD"]) else "")),
            ("🛡️ RISKY · RISK", "변동성과 거래량을 함께 확인<br>단일 지표로 매매 결정 금지"),
        ]
        for floor_col, (agent_name, agent_text) in zip(floor_cols, floor_cards):
            with floor_col:
                st.markdown(f'<div class="pixel-agent"><div class="pixel-agent-title">{agent_name}</div><div class="pixel-agent-body">{agent_text}</div></div>', unsafe_allow_html=True)

        if st.button("▶ AI 에이전트 분석 시작", type="primary", use_container_width=True, key="run_room_analysis"):
            with st.status("🤖 분석 차트실에서 시장 데이터를 분석 중입니다...", expanded=True) as status:
                try:
                    last_candles = [
                        {"open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
                        for c in analysis_ohlcv[-20:]
                    ]
                    indicators_snapshot = {
                        "MA20": None if pd.isna(latest["MA20"]) else float(latest["MA20"]),
                        "MA50": None if pd.isna(latest["MA50"]) else float(latest["MA50"]),
                        "EMA20": None if pd.isna(latest["EMA20"]) else float(latest["EMA20"]),
                        "RSI14": None if pd.isna(latest["RSI"]) else float(latest["RSI"]),
                        "MACD": None if pd.isna(latest["MACD"]) else float(latest["MACD"]),
                        "MACD_signal": None if pd.isna(latest["MACD_Signal"]) else float(latest["MACD_Signal"]),
                        "bollinger_upper": None if pd.isna(latest["BB_Upper"]) else float(latest["BB_Upper"]),
                        "bollinger_lower": None if pd.isna(latest["BB_Lower"]) else float(latest["BB_Lower"]),
                    }
                    analysis_payload = {
                        "symbol": display_symbol,
                        "timeframe": analysis_tf,
                        "current_price": current_price,
                        "balances": {"USDT": usdt_balance, "BTC": btc_balance},
                        "latest_indicators": indicators_snapshot,
                        "recent_candles": last_candles,
                    }
                    analysis_prompt = f"""
당신은 신중한 시장 분석 도우미입니다. 아래 자료를 분석하되 수익을 보장하거나 확정적인 표현을 하지 마세요.
추세, 거래량, RSI, MACD, 볼린저 밴드의 근거와 서로 상충하는 신호를 한국어로 설명하세요.
판단은 buy, sell, hold 중 하나로 하고, 불확실하면 hold를 선택하세요.
응답은 JSON만 반환하세요: {{"decision":"buy|sell|hold","reason":"한국어 분석 논리","percentage":0}}
시장 자료:
{json.dumps(analysis_payload, ensure_ascii=False, indent=2)}
"""
                    raw_text = None
                    if ai_client:
                        try:
                            status.write("🧠 Gemini 분석 요청 중...")
                            ai_response = ai_client.models.generate_content(model="gemini-3.8-flash", contents=analysis_prompt)
                            raw_text = ai_response.text
                        except Exception as ai_error:
                            status.write(f"⏳ Gemini 요청 실패, OpenRouter로 전환합니다: {ai_error}")

                    if not raw_text and openrouter_key:
                        headers = {
                            "Authorization": f"Bearer {openrouter_key.strip()}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://streamlit.io",
                            "X-Title": "OKX AI Analysis Room",
                        }
                        for model_slug in ["openrouter/free", "google/gemma-4-31b-it:free", "qwen/qwen3.8-27b:free"]:
                            status.write(f"🧠 OpenRouter 분석 요청 중: {model_slug}")
                            try:
                                response = requests.post(
                                    "https://openrouter.ai/api/v1/chat/completions",
                                    headers=headers,
                                    json={"model": model_slug, "messages": [{"role": "user", "content": analysis_prompt}]},
                                    timeout=20,
                                )
                                response.raise_for_status()
                                response_json = response.json()
                                if response_json.get("choices"):
                                    raw_text = response_json["choices"][0]["message"]["content"]
                                    break
                            except Exception:
                                continue
                    if not raw_text:
                        raise RuntimeError("AI 연결에 실패했습니다. API 키 또는 네트워크 설정을 확인해주세요.")

                    clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
                    json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
                    if json_match:
                        parsed_result = json.loads(json_match.group(0))
                    else:
                        clean_text = clean_text.replace("```json", "").replace("```", "").strip()
                        parsed_result = json.loads(clean_text)
                    st.session_state.ai_result = parsed_result
                    st.session_state.ai_result_timeframe = analysis_tf
                    status.update(label="✅ 분석 완료", state="complete", expanded=False)
                except Exception as error:
                    status.update(label="❌ 분석 실패", state="error", expanded=True)
                    st.error(f"분석 중 오류가 발생했습니다: {error}")

        if st.session_state.ai_result:
            result = st.session_state.ai_result
            decision = str(result.get("decision", "hold")).upper()
            reason = result.get("reason", "분석 근거가 반환되지 않았습니다.")
            percentage = result.get("percentage", 0)
            st.markdown("---")
            st.subheader("🧠 AI 분석 결과와 판단 논리")
            if decision == "BUY":
                st.success(f"AI 의견: 🟢 {decision} · 권장 비중 {percentage}%")
            elif decision == "SELL":
                st.warning(f"AI 의견: 🔴 {decision} · 권장 비중 {percentage}%")
            else:
                st.info(f"AI 의견: 🟡 {decision} · 권장 비중 {percentage}%")
            if st.session_state.ai_result_timeframe:
                st.caption(f"분석 당시 타임프레임: {st.session_state.ai_result_timeframe}")
            st.markdown(f"**AI 판단 근거**\n\n{reason}")

            st.markdown('<div class="pixel-banner"><b>◆ AI AGENT CONSOLE · 판단 결과 기록 완료</b></div>', unsafe_allow_html=True)
            st.markdown("#### 지표를 읽는 기준")
            logic_lines = []
            close_value = float(latest["close"])
            for ma_name in ("MA20", "MA50", "EMA20"):
                ma_value = latest[ma_name]
                if pd.notna(ma_value):
                    relation = "위" if close_value >= float(ma_value) else "아래"
                    logic_lines.append(f"- 종가는 **{ma_name} {relation}**입니다 ({float(ma_value):,.2f}).")
            if pd.notna(latest["RSI"]):
                rsi_value = float(latest["RSI"])
                rsi_text = "과매수 주의 구간" if rsi_value >= 70 else "과매도 주의 구간" if rsi_value <= 30 else "중립 구간"
                logic_lines.append(f"- **RSI {rsi_value:.1f}:** {rsi_text}. RSI 하나만으로 매수·매도를 결정하지 않습니다.")
            if pd.notna(latest["MACD"]) and pd.notna(latest["MACD_Signal"]):
                macd_relation = "시그널선 위" if float(latest["MACD"]) >= float(latest["MACD_Signal"]) else "시그널선 아래"
                logic_lines.append(f"- **MACD:** 현재 MACD가 시그널선 {macd_relation}에 있습니다.")
            if pd.notna(latest["BB_Upper"]) and pd.notna(latest["BB_Lower"]):
                if close_value > float(latest["BB_Upper"]):
                    band_text = "상단 밴드 밖이며 변동성 확대 가능성을 확인해야 합니다."
                elif close_value < float(latest["BB_Lower"]):
                    band_text = "하단 밴드 밖이며 추가 하락 및 반등 가능성을 함께 확인해야 합니다."
                else:
                    band_text = "가격이 밴드 안에 있습니다."
                logic_lines.append(f"- **볼린저 밴드:** {band_text}")
            st.markdown("\n".join(logic_lines))
            st.caption("AI 의견과 기술 지표는 참고용입니다. 자동 주문을 실행하지 않으며 수익을 보장하지 않습니다.")

    except Exception as error:
        st.error(f"분석 차트 데이터를 불러오지 못했습니다: {error}")

    st.stop()

# --- 1. Top Header Bar & 설정(다크모드) 창 ---
change_class = "okx-price-up" if change_24h >= 0 else "okx-price-down"
change_sign = "+" if change_24h >= 0 else ""

header_col, settings_col = st.columns([9.1, 0.9])

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

# --- 2. 상단 타임프레임 및 지표 불빛 토글 바 ---
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

# --- 🔥 지표 토글 버튼 (켜지면 골드/주황 불빛 들어옴) ---
indicators = [
    ("20일선", "show_ma20", 8),
    ("50일선", "show_ma50", 9),
    ("200일선", "show_ma200", 10),
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

    # 보조 지표 계산
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['MA200'] = df['close'].rolling(window=200).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()

    # 선택한 차트 주기와 별개로 실제 일봉 기준 20/50/200일 이동평균선을 계산
    try:
        daily_ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe="1d", limit=250)
        daily_df = pd.DataFrame(daily_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        daily_df["day"] = pd.to_datetime(daily_df["timestamp"], unit="ms").dt.date
        for period in (20, 50, 200):
            daily_col = f"MA{period}D"
            daily_df[daily_col] = daily_df["close"].rolling(window=period).mean()
            daily_values = daily_df.set_index("day")[daily_col]
            df[daily_col] = df["datetime"].dt.date.map(daily_values)
    except Exception:
        for period in (20, 50, 200):
            df[f"MA{period}D"] = float("nan")

    std20 = df['close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (std20 * 2)
    df['BB_Lower'] = df['MA20'] - (std20 * 2)

    # RSI 지표
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD 지표
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 서브차트 개수 계산
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

    # 1. 메인 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name='BTC/USDT',
        increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',
        decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'
    ), row=1, col=1)

    # 지표 온/오프 반영
    if st.session_state.show_ma20:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA20D'], line=dict(color='#ff9800', width=1.7), name='20일선'), row=1, col=1)
    if st.session_state.show_ma50:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA50D'], line=dict(color='#2196f3', width=1.7), name='50일선'), row=1, col=1)
    if st.session_state.show_ma200:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA200D'], line=dict(color='#9c27b0', width=1.7), name='200일선'), row=1, col=1)
    if st.session_state.show_ema20:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['EMA20'], line=dict(color='#00e676', width=1.5), name='EMA20'), row=1, col=1)
    if st.session_state.show_bollinger:
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Upper'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Upper'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Lower'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Lower'), row=1, col=1)

    # 현재가 점선 라인
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
        paper_bgcolor=card_bg,
        plot_bgcolor=card_bg,
        font=dict(color=text_color, size=11),
        height=430,
        margin=dict(l=10, r=60, t=15, b=15),
        xaxis_rangeslider_visible=False,
        showlegend=False,
        hovermode="x unified",
        dragmode='pan'
    )

    fig.update_yaxes(side="right", gridcolor=grid_color, zerolinecolor=grid_color, showgrid=True, fixedrange=False)
    fig.update_xaxes(gridcolor=grid_color, zerolinecolor=grid_color, showgrid=True, fixedrange=False)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            'scrollZoom': True,
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
            'displaylogo': False
        }
    )
    st.caption("20일선·50일선·200일선은 실제 1일봉 기준 이동평균입니다. EMA20은 선택한 차트 주기 기준입니다.")

# --- [RIGHT: 주문 패널 카드] ---
with trade_col:
    st.markdown(f"<div style='font-weight: bold; font-size: 13px; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid {border_color};'>⚡ Trade Panel</div>", unsafe_allow_html=True)
    
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
