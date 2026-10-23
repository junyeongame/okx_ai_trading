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
    st.session_state.active_tf = "5m"

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

# 동적 CSS 테마 색상 설정 (TradingView Dark Theme)
bg_color = "#000000"
card_bg = "#000000"
input_bg = "#131722"
text_color = "#d1d4dc"
border_color = "#2a2e39"

st.markdown(f"""
<style>
    /* 1. 사이드바 숨기기 */
    [data-testid="stSidebar"] {{
        display: none !important;
    }}
    
    /* 2. 전체 메인 앱 배경 (TradingView 딥블랙) */
    .stApp, div[data-testid="stHeader"], div[data-testid="stToolbar"] {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}

    /* 3. 컬럼 레이아웃 간격 최적화 */
    div[data-testid="stHorizontalBlock"] {{
        gap: 10px !important;
    }}

    /* 4. 영역 분리 카드 디자인 */
    div[data-testid="column"] > div {{
        background-color: {card_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
        padding: 8px 12px !important;
    }}

    /* 5. 텍스트 글자색 적용 */
    label, p, span, h1, h2, h3, h4, h5, h6, div[data-testid="stWidgetLabel"] {{
        color: {text_color} !important;
    }}

    /* 6. 입력창, 선택박스 스타일 */
    div[data-baseweb="input"], 
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"],
    input, textarea, select {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
    }}

    /* 7. 타임프레임 및 버튼 스타일 */
    div.stButton > button {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
        padding: 2px 8px !important;
        min-height: 26px !important;
        height: 26px !important;
        font-size: 11px !important;
    }}
    div.stButton > button:hover {{
        border-color: #f0b90b !important;
        color: #f0b90b !important;
    }}

    /* OKX Header Bar */
    .okx-header {{
        background-color: #131722;
        padding: 6px 14px;
        border-radius: 4px;
        border: 1px solid {border_color};
        margin-bottom: 8px;
    }}
    .okx-price-up {{ color: #26a69a; font-weight: bold; }}
    .okx-price-down {{ color: #ef5350; font-weight: bold; }}
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

# --- 1. Top Header Bar ---
change_class = "okx-price-up" if change_24h >= 0 else "okx-price-down"
change_sign = "+" if change_24h >= 0 else ""

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

# --- 2. 상단 타임프레임 컨트롤 바 ---
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

# --- 3. 메인 2컬럼 레이아웃 (좌: 와이드 차트 | 우: 주문 패널) ---
chart_col, trade_col = st.columns([7.8, 2.2])

# --- [LEFT: 전문 트레이딩뷰 스타일 차트 패널] ---
with chart_col:
    timeframe = st.session_state.active_tf

    try:
        limit_cnt = 80
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit_cnt)
    except Exception:
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe='5m', limit=80)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # 보조 지표 계산 (MA20, MA50, MA200, EMA20, 볼린저밴드)
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['MA200'] = df['close'].rolling(window=200).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()

    std20 = df['close'].rolling(window=20).std()
    df['BB_Upper'] = df['MA20'] + (std20 * 2)
    df['BB_Lower'] = df['MA20'] - (std20 * 2)

    fig = make_subplots(
        rows=1, cols=1, shared_xaxes=True
    )

    # 1. 캔들스틱 차트 (TradingView 테마 색상 적용)
    fig.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name='BTC/USDT',
        increasing_line_color='#26a69a', increasing_fillcolor='#26a69a',
        decreasing_line_color='#ef5350', decreasing_fillcolor='#ef5350'
    ))

    # 2. 이동평균선 & 이평선 추가
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA20'], line=dict(color='#ff9800', width=1.5), name='MA20'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA50'], line=dict(color='#2196f3', width=1.5), name='MA50'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA200'], line=dict(color='#9c27b0', width=1.5), name='MA200'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['EMA20'], line=dict(color='#00e676', width=1.5), name='EMA20'))

    # 3. 볼린저 밴드
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Upper'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Upper'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['BB_Lower'], line=dict(color='#7e57c2', width=1, dash='dot'), name='BB Lower'))

    # 4. 현재가 점선 라인
    fig.add_hline(
        y=current_price, line_dash="dash", line_color="#26a69a", line_width=1.2,
        annotation_text=f" {current_price:,.1f}", annotation_position="right",
        annotation_font=dict(color="#ffffff", size=11), annotation_bgcolor="#26a69a"
    )

    # 🔥 [핵심] 마우스 휠 확대/축소 + Y축 드래그 확대/축소 활성화
    fig.update_layout(
        paper_bgcolor='#000000',
        plot_bgcolor='#000000',
        font=dict(color="#b2b5be", size=11),
        height=580,
        margin=dict(l=10, r=60, t=25, b=20),
        xaxis_rangeslider_visible=False,
        showlegend=False,
        hovermode="x unified",
        
        # 확대/축소 및 인터랙티브 인터페이스 설정
        dragmode='pan',
        
        # Y축 금액 라벨 좌클릭 드래그 및 마우스 휠 줌 활성화
        yaxis=dict(
            side="right",
            gridcolor="#1e222d",
            zerolinecolor="#1e222d",
            showgrid=True,
            fixedrange=False # Y축 확대/축소 가능
        ),
        xaxis=dict(
            gridcolor="#1e222d",
            zerolinecolor="#1e222d",
            showgrid=True,
            fixedrange=False # X축 확대/축소 가능
        )
    )

    # Streamlit 차트 옵션: 마우스 휠 줌 활성화 (scrollZoom = True)
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            'scrollZoom': True,           # 휠로 차트 확대/축소
            'displayModeBar': True,       # 상단 트레이딩 툴바 표시
            'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
            'displaylogo': False
        }
    )

# --- [RIGHT: 주문 패널 카드] ---
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
