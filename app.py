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

# 🎨 OKX 스타일 다크 테마 커스텀 CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0b0e11;
        color: #eaeaea;
    }
    div[data-testid="stHeader"] {
        background-color: #0b0e11;
    }
    /* OKX Header Bar */
    .okx-header {
        background-color: #12161c;
        padding: 12px 20px;
        border-radius: 6px;
        border-bottom: 1px solid #1e2329;
        margin-bottom: 15px;
    }
    .okx-price-up { color: #00c076; font-weight: bold; }
    .okx-price-down { color: #ff4d4f; font-weight: bold; }
    .stButton>button {
        background-color: #1e232a;
        color: #ffffff;
        border: 1px solid #2b313a;
        border-radius: 4px;
        padding: 4px 10px;
    }
    .stButton>button:hover {
        background-color: #2b313a;
        border-color: #3b424d;
    }
    /* Tabs Customization */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #848e9c !important;
        font-size: 14px !important;
    }
    button[aria-selected="true"] {
        color: #f0b90b !important;
        border-bottom-color: #f0b90b !important;
    }
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

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

# 클라이언트 초기화
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
    exchange.set_sandbox_mode(True)  # 데모 계좌 모드

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

# 시세 및 계좌 잔고 가져오기
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

# --- 1. Top Header Bar (OKX 트레이딩 스펙 헤더) ---
change_class = "okx-price-up" if change_24h >= 0 else "okx-price-down"
change_sign = "+" if change_24h >= 0 else ""

st.markdown(f"""
<div class="okx-header">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 20px; font-weight: bold; color: #ffffff;">⬛ {display_symbol}</span>
            <span style="background-color: #2b313a; color: #f0b90b; font-size: 11px; padding: 2px 6px; border-radius: 3px;">Demo Trading</span>
            <span style="background-color: #1e232a; color: #848e9c; font-size: 11px; padding: 2px 6px; border-radius: 3px;">Perp</span>
        </div>
        <div style="display: flex; gap: 25px; font-size: 13px;">
            <div><span style="color: #848e9c;">최근가</span><br><span class="{change_class}" style="font-size: 16px;">${current_price:,.2f}</span></div>
            <div><span style="color: #848e9c;">24h 변동률</span><br><span class="{change_class}">{change_sign}{change_24h:.2f}%</span></div>
            <div><span style="color: #848e9c;">24h 고가</span><br><span style="color: #eaeaea;">${high_24h:,.2f}</span></div>
            <div><span style="color: #848e9c;">24h 저가</span><br><span style="color: #eaeaea;">${low_24h:,.2f}</span></div>
            <div><span style="color: #848e9c;">24h 거래량(BTC)</span><br><span style="color: #eaeaea;">{volume_24h:,.2f} BTC</span></div>
            <div><span style="color: #848e9c;">총 평가 자산</span><br><span style="color: #f0b90b; font-weight: bold;">${total_asset_usdt:,.2f} USDT</span></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 2. 메인 3컬럼 레이아웃 (차트 | 호가창 | 주문 패널) ---
chart_col, orderbook_col, trade_col = st.columns([5, 2.5, 2.5])

# --- [LEFT: 차트 & 타임프레임 컨트롤] ---
with chart_col:
    st.markdown("##### 📊 OKX 차트 및 타임프레임")
    
    # ⏱️ 1초부터 1달봉까지 지원하는 타임프레임 바
    tf_options = {
        "1s (1초)": "1s",
        "1m (1분)": "1m",
        "5m (5분)": "5m",
        "15m (15분)": "15m",
        "30m (30분)": "30m",
        "1h (1시간)": "1h",
        "4h (4시간)": "4h",
        "1d (1일)": "1d",
        "1w (1주)": "1w",
        "1M (1달)": "1M"
    }
    
    selected_tf_label = st.select_slider(
        "타임프레임 선택 (1초 ~ 1달봉)",
        options=list(tf_options.keys()),
        value="1h (1시간)",
        label_visibility="collapsed"
    )
    timeframe = tf_options[selected_tf_label]

    # OHLCV 데이터 수집 (초봉/분봉 예외 처리)
    try:
        limit_cnt = 40 if timeframe in ['1s', '1m'] else 60
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe=timeframe, limit=limit_cnt)
    except Exception as e:
        # 1초봉 등 거래소 API 미지원 제한 시 1분봉으로 유연 자동 전환
        st.caption(f"⚠️ {selected_tf_label} 수집 대기 중 (1분봉 대체 로드)")
        ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe='1m', limit=50)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # 이동평균선(MA5, MA10, MA20) 계산
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()

    # Plotly 서브플롯 (캔들스틱 + 거래량)
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        subplot_titles=('', ''), row_width=[0.2, 0.8]
    )

    # 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name=display_symbol,
        increasing_line_color='#00c076', decreasing_line_color='#ff4d4f'
    ), row=1, col=1)

    # 이동평균선 추가
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA5'], line=dict(color='#f0b90b', width=1), name='MA(5)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA10'], line=dict(color='#17a2b8', width=1), name='MA(10)'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['MA20'], line=dict(color='#e83e8c', width=1), name='MA(20)'), row=1, col=1)

    # 거래량 바 차트
    colors = ['#00c076' if row['close'] >= row['open'] else '#ff4d4f' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=colors, name='Volume'), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

# --- [MIDDLE: 실시간 호가창 (Order Book)] ---
with orderbook_col:
    st.markdown("##### 📖 Order Book (호가창)")
    try:
        orderbook = exchange.fetch_order_book(ccxt_symbol, limit=7)
        bids = orderbook['bids']  # 매수 호가
        asks = orderbook['asks']  # 매도 호가

        st.markdown("<div style='font-size: 11px; color: #848e9c; display:flex; justify-size: space-between;'><span>Price(USDT)</span><span>Amount(BTC)</span></div>", unsafe_allow_html=True)
        
        # 매도 호가 (Asks - 역순)
        for price, amount in reversed(asks):
            st.markdown(f"<div style='display:flex; justify-content:space-between; font-size: 12px; color:#ff4d4f;'><span>${price:,.2f}</span><span>{amount:.4f}</span></div>", unsafe_allow_html=True)
        
        st.markdown(f"<div style='text-align:center; padding: 6px 0; font-size: 15px; font-weight:bold;' class='{change_class}'>${current_price:,.2f} ⚡</div>", unsafe_allow_html=True)
        
        # 매수 호가 (Bids)
        for price, amount in bids:
            st.markdown(f"<div style='display:flex; justify-content:space-between; font-size: 12px; color:#00c076;'><span>${price:,.2f}</span><span>{amount:.4f}</span></div>", unsafe_allow_html=True)

    except Exception as ob_err:
        st.caption("호가창 데이터를 불러오는 중...")

# --- [RIGHT: 주문 실행 및 레버리지 설정 패널] ---
with trade_col:
    st.markdown("##### ⚡ Trade Panel (주문창)")
    
    # 레버리지 및 마진 선택
    leverage = st.slider("🎯 레버리지 배율 (1x ~ 50x)", min_value=1, max_value=50, value=10, step=1)
    
    order_mode = st.radio("주문 타입", ["시장가 (Market)", "지정가 (Limit)"], horizontal=True, label_visibility="collapsed")
    
    limit_price = current_price
    if "지정가" in order_mode:
        limit_price = st.number_input("지정가 (USDT)", value=current_price, step=10.0)

    trade_tab1, trade_tab2 = st.tabs(["🟢 Buy / Long", "🔴 Sell / Short"])
    
    with trade_tab1:
        buy_percent = st.slider("USDT 매수 비중 (%)", 10, 100, 25, 5, key="b_percent")
        if st.button(f"🚀 {leverage}x Long 매수 실행", use_container_width=True, type="primary"):
            try:
                buy_usdt_amount = usdt_balance * (buy_percent / 100) * leverage
                buy_btc_amount = buy_usdt_amount / current_price
                
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

# --- 3. AI 분석 및 판단 섹션 ---
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

            [분석 및 응답 규칙]
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

            # [1순위] Gemini 시도
            if ai_client:
                try:
                    status.write("🧠 1. Gemini Flash 모델 분석 시도 중...")
                    res = ai_client.models.generate_content(model='gemini-3.8-flash', contents=prompt)
                    raw_text = res.text
                except Exception:
                    status.write("⏳ Gemini 한도 소진/대기. OpenRouter 무료 AI 모음으로 우회합니다.")

            # [2순위] OpenRouter 무료 우회
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

# --- 4. 하단 탭: 미체결 주문 / 체결 히스토리 / 자산 잔고 ---
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
