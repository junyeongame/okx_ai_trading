import os
import json
import ccxt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from google import genai

# 1. 환경 변수 로드 및 페이지 설정
load_dotenv()

st.set_page_config(
    page_title="OKX AI 트레이딩 대시보드",
    page_icon="📈",
    layout="wide"
)

# 세션 상태 초기화
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

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

# OKX & Gemini 클라이언트 초기화
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
    exchange.set_sandbox_mode(True)  # 데모 계좌 모드

    ai_client = genai.Client(api_key=gemini_api_key)
    return exchange, ai_client

try:
    exchange, ai_client = get_clients()
except Exception as e:
    st.error(f"설정 불러오기 실패: {e}")
    st.stop()

# --- 대시보드 헤더 ---
st.title("📈 OKX AI 트레이딩 대시보드")
st.caption("실시간 시세 및 과거 차트를 확인하고 AI 분석을 통해 안전하게 매매를 진행하세요.")

symbol = 'BTC/USDT'

# --- 1. 실시간 계좌 잔고 정보 ---
try:
    ticker = exchange.fetch_ticker(symbol)
    balance = exchange.fetch_balance()
    
    current_price = ticker['last']
    usdt_balance = balance['total'].get('USDT', 0)
    btc_balance = balance['total'].get('BTC', 0)

    col1, col2, col3 = st.columns(3)
    col1.metric("현재 비트코인(BTC) 시세", f"${current_price:,.2f} USDT")
    col2.metric("보유 USDT 잔고", f"${usdt_balance:,.2f} USDT")
    col3.metric("보유 BTC 잔고", f"{btc_balance:.6f} BTC")

except Exception as e:
    st.error(f"거래소 잔고 로드 실패: {e}")

st.divider()

# --- 2. 과거 차트 그래프 표시 (15분봉 / 1시간봉 선택 가능) ---
st.subheader("📊 비트코인 과거 시세 차트")

tf_col, count_col = st.columns([1, 1])
with tf_col:
    timeframe = st.selectbox("타임프레임(봉) 선택", ["15m", "1h", "4h", "1d"], index=1)
with count_col:
    candle_count = st.slider("조회할 과거 봉 개수", min_value=30, max_value=300, value=100, step=10)

try:
    # OKX에서 과거 데이터 가져오기 (limit 조절로 과거 시세까지 로드)
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=candle_count)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Plotly 캔들차트 생성
    fig = go.Figure(data=[go.Candlestick(
        x=df['datetime'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color='#26a69a', 
        decreasing_line_color='#ef5350'
    )])

    fig.update_layout(
        title=f"BTC/USDT ({timeframe} 차트)",
        yaxis_title="가격 (USDT)",
        xaxis_title="시간",
        height=450,
        template="plotly_dark",
        xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"차트 데이터 조회 중 오류 발생: {e}")

st.divider()

# --- 3. AI 차트 분석 및 추천 ---
st.subheader("🤖 AI 차트 분석 및 추천")

if st.button("🔍 과거 차트 전체 기반 AI 분석 시작하기", type="primary", use_container_width=True):
    with st.spinner("AI가 최근 100개의 과거 차트 패턴과 기술적 데이터를 분석 중입니다..."):
        try:
            # AI 분석용 과거 1시간봉 100개 수집
            analysis_ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
            
            market_data = {
                "symbol": symbol,
                "current_price": current_price,
                "usdt_balance": usdt_balance,
                "btc_balance": btc_balance,
                "recent_1h_candles_summary": [
                    {"open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
                    for c in analysis_ohlcv[-20:]  # 직근 20개 세부 봉
                ],
                "lowest_price_in_period": min([c[3] for c in analysis_ohlcv]),
                "highest_price_in_period": max([c[2] for c in analysis_ohlcv])
            }

            prompt = f"""
            당신은 암호화폐 전문 트레이더입니다.
            전달된 최근 과거 차트 데이터의 흐름, 지지/저항 라인 및 현재 가격을 분석하여 매매 판단을 내리세요.

            [시장 데이터]
            {json.dumps(market_data, indent=2)}

            [응답 규칙]
            오직 아래 JSON 형태로만 답변하세요.
            {{
                "decision": "buy" 또는 "sell" 또는 "hold",
                "reason": "과거 차트 패턴과 지지/저항에 기반한 상세한 판단 이유",
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

# AI 분석 결과 출력
if st.session_state.ai_result:
    result = st.session_state.ai_result
    decision = result.get("decision", "hold").upper()
    reason = result.get("reason", "")
    percentage = result.get("percentage", 0)

    st.markdown("---")
    if decision == "BUY":
        st.success(f"### AI 추천: 🟢 {decision} (매수 추천)")
    elif decision == "SELL":
        st.warning(f"### AI 추천: 🔴 {decision} (매도 추천)")
    else:
        st.info(f"### AI 추천: 🟡 {decision} (관망 추천)")

    st.markdown(f"**💡 AI 판단 근거:**\n>{reason}")
    st.markdown(f"**📊 권장 매매 비중:** `{percentage}%`")

st.divider()

# --- 4. 수동 매매 버튼 ---
st.subheader("👆 직접 매매 승인 및 주문")

trade_col1, trade_col2 = st.columns(2)

with trade_col1:
    st.markdown("#### 🟢 매수 실행")
    buy_percent = st.slider("USDT 매수 비중 (%)", 10, 100, 25, 5, key="buy_slider")
    if st.button("🚀 시장가 매수", use_container_width=True):
        if usdt_balance > 10:
            try:
                buy_usdt_amount = usdt_balance * (buy_percent / 100)
                buy_btc_amount = buy_usdt_amount / current_price
                order = exchange.create_market_buy_order(symbol, buy_btc_amount)
                st.success(f"✅ 매수 성공! (주문 ID: {order['id']})")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매수 실패: {e}")
        else:
            st.error("USDT 잔고가 부족합니다 (최소 10 USDT 필요).")

with trade_col2:
    st.markdown("#### 🔴 매도 실행")
    sell_percent = st.slider("BTC 매도 비중 (%)", 10, 100, 100, 5, key="s_slider")
    if st.button("📉 시장가 매도", use_container_width=True):
        if btc_balance > 0.0001:
            try:
                sell_btc_amount = btc_balance * (sell_percent / 100)
                order = exchange.create_market_sell_order(symbol, sell_btc_amount)
                st.success(f"✅ 매도 성공! (주문 ID: {order['id']})")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매도 실패: {e}")
        else:
            st.error("보유 BTC 수량이 부족합니다.")
