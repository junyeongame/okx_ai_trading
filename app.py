import os
import json
import time
import ccxt
import streamlit as st
from dotenv import load_dotenv
from google import genai

# 1. 환경 변수 로드 및 페이지 기본 설정
load_dotenv()

st.set_page_config(
    page_title="OKX AI 트레이딩 대시보드",
    page_icon="📈",
    layout="wide"
)

# 🔒 비밀번호 잠금 기능 (비밀번호를 입력해야만 화면이 열림)
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.title("🔒 로그인 필요")
        pwd = st.text_input("대시보드 비밀번호를 입력하세요:", type="password")
        if st.button("로그인"):
            correct_pwd = st.secrets.get("APP_PASSWORD", "1234")
            if pwd == correct_pwd:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 올바르지 않습니다.")
        return False
    return True

# 비밀번호가 일치하지 않으면 아래 코드를 실행하지 않고 멈춤
if not check_password():
    st.stop()

# 세션 상태 초기화 (AI 분석 결과를 화면에 유지하기 위함)
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

# OKX & Gemini 클라이언트 초기화 함수
@st.cache_resource
def get_clients():
    api_key = os.getenv("OKX_API_KEY")
    secret_key = os.getenv("OKX_SECRET_KEY")
    passphrase = os.getenv("OKX_PASSPHRASE")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': secret_key,
        'password': passphrase,
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True)  # 데모 계좌 모드 (실전 매매 시 주석 처리 또는 False)

    ai_client = genai.Client(api_key=gemini_api_key)
    return exchange, ai_client

try:
    exchange, ai_client = get_clients()
except Exception as e:
    st.error(f".env 파일 설정을 확인해주세요: {e}")
    st.stop()

# --- 웹 화면 헤더 ---
st.title("📈 OKX AI 트레이딩 대시보드")
st.caption("AI의 차트 분석 및 판단 근거를 확인하고, 승인 후 매매를 진행하세요.")

# --- 1. 실시간 계좌 및 시세 정보 섹션 ---
symbol = 'BTC/USDT'

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
    st.error(f"거래소 데이터를 불러오는 중 오류 발생: {e}")

st.divider()

# --- 2. AI 차트 분석 및 판단 섹션 ---
st.subheader("🤖 AI 차트 분석 및 추천")

if st.button("🔍 AI 차트 분석 시작하기", type="primary", use_container_width=True):
    with st.status("🤖 AI 분석을 진행하고 있습니다...", expanded=True) as status:
        try:
            status.write("📊 1. OKX 거래소에서 1시간봉 차트 데이터를 불러오는 중...")
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=15)
            
            market_data = {
                "symbol": symbol,
                "current_price": current_price,
                "usdt_balance": usdt_balance,
                "btc_balance": btc_balance,
                "recent_1h_candles": [
                    {"open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
                    for c in ohlcv
                ]
            }

            prompt = f"""
            당신은 신중하고 전문적인 암호화폐 트레이더입니다.
            아래 전달된 실시간 시장 데이터와 잔고 상태를 분석하여 매매 전략을 결정하세요.

            [시장 데이터]
            {json.dumps(market_data, indent=2)}

            [분석 규칙]
            1. 추세와 거래량을 고려하여 확실한 매수 타점일 때만 "buy", 매도 타점일 때 "sell", 불확실하면 "hold"를 선택하세요.
            2. 응답은 오직 아래 JSON 양식으로만 응답해야 합니다.

            {{
                "decision": "buy" 또는 "sell" 또는 "hold",
                "reason": "기술적 분석에 기반한 구체적인 판단 이유",
                "percentage": 10~100 사이의 권장 주문 비중 (hold인 경우 0)
            }}
            """

            # 올바른 구글 API 소문자 모델명 목록 (유효 한도 있는 모델 우선 우회)
            candidate_models = [
                'gemini-2.5-flash',
                'gemini-2.5-flash-lite',
                'gemini-1.5-flash',
                'gemini-3.8-flash'
            ]
            
            response = None
            success = False

            for model_name in candidate_models:
                status.write(f"🧠 AI 모델({model_name})에 분석 요청 중...")
                try:
                    response = ai_client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    success = True
                    break  # 성공 시 재시도 루프 탈출
                except Exception as e:
                    status.write(f"⚠️ {model_name} 연결 거부/한도 초과. 다음 모델로 전환합니다.")
                    continue

            if not success or not response:
                raise Exception("모든 무료 모델의 하루 이용 한도가 소진되었거나 서버 접속이 원활하지 않습니다.")

            status.write("📥 2. AI 분석 결과 정리 중...")
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            st.session_state.ai_result = json.loads(raw_text)

            status.update(label="✅ AI 차트 분석 완료!", state="complete", expanded=False)

        except Exception as e:
            status.update(label="❌ AI 분석 실패", state="error", expanded=True)
            st.error(f"오류 상세 내용: {e}")

# AI 분석 결과 출력
if st.session_state.ai_result:
    result = st.session_state.ai_result
    decision = result.get("decision", "hold").upper()
    reason = result.get("reason", "")
    percentage = result.get("percentage", 0)

    st.markdown("---")
    
    # 추천 상태에 따른 배지 및 색상 설정
    if decision == "BUY":
        st.success(f"### AI 추천: 🟢 {decision} (매수 추천)")
    elif decision == "SELL":
        st.warning(f"### AI 추천: 🔴 {decision} (매도 추천)")
    else:
        st.info(f"### AI 추천: 🟡 {decision} (관망 추천)")

    st.markdown(f"**💡 AI 판단 근거:**\n>{reason}")
    st.markdown(f"**📊 권장 매매 비중:** `{percentage}%`")

st.divider()

# --- 3. 사용자 수동 매매 버튼 섹션 ---
st.subheader("👆 직접 매매 승인 및 주문")

trade_col1, trade_col2 = st.columns(2)

with trade_col1:
    st.markdown("#### 🟢 매수 실행")
    buy_percent = st.slider("USDT 매수 비중 선택 (%)", min_value=10, max_value=100, value=25, step=5, key="buy_slider")
    
    if st.button("🚀 선택한 비중으로 시장가 매수", use_container_width=True):
        if usdt_balance > 10:
            try:
                buy_usdt_amount = usdt_balance * (buy_percent / 100)
                buy_btc_amount = buy_usdt_amount / current_price
                
                order = exchange.create_market_buy_order(symbol, buy_btc_amount)
                st.success(f"✅ 매수 성공! {buy_usdt_amount:.2f} USDT치 BTC 구매 완료 (주문 ID: {order['id']})")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매수 실패: {e}")
        else:
            st.error("보유한 USDT 잔고가 부족합니다 (최소 10 USDT 필요).")

with trade_col2:
    st.markdown("#### 🔴 매도 실행")
    sell_percent = st.slider("BTC 매도 비중 선택 (%)", min_value=10, max_value=100, value=100, step=5, key="sell_slider")
    
    if st.button("📉 선택한 비중으로 시장가 매도", use_container_width=True):
        if btc_balance > 0.0001:
            try:
                sell_btc_amount = btc_balance * (sell_percent / 100)
                
                order = exchange.create_market_sell_order(symbol, sell_btc_amount)
                st.success(f"✅ 매도 성공! {sell_btc_amount:.6f} BTC 매도 완료 (주문 ID: {order['id']})")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매도 실패: {e}")
        else:
            st.error("보유한 BTC 수량이 부족합니다.")
