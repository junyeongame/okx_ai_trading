import os
import json
import time
import re
import datetime
import requests
import ccxt
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from google import genai

# 1. 환경 변수 로드 및 페이지 기본 설정
load_dotenv()

st.set_page_config(
    page_title="OKX AI 트레이딩 대시보드",
    page_icon="📈",
    layout="wide"
)

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

st.title("📈 OKX AI 트레이딩 대시보드")
st.caption("실시간 차트와 주문 히스토리를 확인하고 AI 판단에 따라 매매를 승인하세요.")

# 거래소 심볼 정의 (표시용: BTCUSDT, CCXT용: BTC/USDT)
display_symbol = 'BTCUSDT'
ccxt_symbol = 'BTC/USDT'

# 시세 및 잔고 조회
try:
    ticker = exchange.fetch_ticker(ccxt_symbol)
    balance = exchange.fetch_balance()
    
    current_price = ticker['last']
    usdt_balance = balance['total'].get('USDT', 0)
    btc_balance = balance['total'].get('BTC', 0)
    total_asset_usdt = usdt_balance + (btc_balance * current_price)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"현재 비트코인({display_symbol}) 시세", f"${current_price:,.2f} USDT")
    col2.metric("보유 USDT 잔고", f"${usdt_balance:,.2f} USDT")
    col3.metric("보유 BTC 잔고", f"{btc_balance:.6f} BTC")
    col4.metric("총 평가 자산", f"${total_asset_usdt:,.2f} USDT")

except Exception as e:
    st.error(f"거래소 데이터 로드 실패: {e}")

st.divider()

# --- 1. 실시간 트레이딩뷰 차트 섹션 ---
st.subheader("📊 실시간 OKX BTCUSDT 차트")

tradingview_html = """
<div class="tradingview-widget-container" style="height:500px;width:100%;">
  <div id="tradingview_chart" style="height:calc(100% - 32px);width:100%;"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget(
  {
  "autosize": true,
  "symbol": "OKX:BTCUSDT",
  "interval": "60",
  "timezone": "Asia/Seoul",
  "theme": "dark",
  "style": "1",
  "locale": "kr",
  "toolbar_bg": "#f1f3f6",
  "enable_publishing": false,
  "hide_legend": false,
  "save_image": false,
  "container_id": "tradingview_chart"
}
  );
  </script>
</div>
"""
components.html(tradingview_html, height=520)

st.divider()

# --- 2. AI 차트 분석 및 추천 섹션 ---
st.subheader("🤖 AI 차트 분석 및 추천")

if st.button("🔍 AI 차트 분석 시작하기", type="primary", use_container_width=True):
    with st.status("🤖 AI 분석을 진행하고 있습니다...", expanded=True) as status:
        try:
            status.write("📊 1. OKX 거래소에서 1시간봉 차트 데이터를 불러오는 중...")
            ohlcv = exchange.fetch_ohlcv(ccxt_symbol, timeframe='1h', limit=15)
            
            market_data = {
                "symbol": display_symbol,
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

            [분석 및 응답 규칙]
            1. 모든 분석 이유("reason")와 판단 설명은 반드시 100% 한국어(한글)로만 작성해야 합니다. 영어나 다른 언어 사용은 절대 금지합니다.
            2. 추세와 거래량을 고려하여 확실한 매수 타점일 때만 "buy", 매도 타점일 때 "sell", 불확실하면 "hold"를 선택하세요.
            3. 응답은 오직 아래 지정된 JSON 양식으로만 작성해야 하며, 서론이나 설명글, 코드 블록 표식은 절대 포함하지 마세요.

            {{
                "decision": "buy" 또는 "sell" 또는 "hold",
                "reason": "기술적 분석에 기반한 구체적인 한국어 판단 이유",
                "percentage": 10~100 사이의 권장 주문 비중 (hold인 경우 0)
            }}
            """

            raw_text = None

            # [1순위] Gemini 3.8 Flash 시도
            if ai_client:
                try:
                    status.write("🧠 1. Gemini 3.8 Flash 모델 분석 시도 중...")
                    res = ai_client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=prompt
                    )
                    raw_text = res.text
                except Exception:
                    status.write("⏳ Gemini 무료 한도(20회) 소진/오류. OpenRouter 무료 AI 모음으로 전환합니다.")

            # [2순위] OpenRouter 무료 모델 우회 시도
            if not raw_text:
                if not openrouter_key:
                    raise Exception("OPENROUTER_API_KEY가 Streamlit Secrets에 설정되어 있지 않습니다.")

                free_models = [
                    "openrouter/free",
                    "google/gemma-4-31b-it:free",
                    "qwen/qwen3.8-27b:free",
                    "nvidia/nemotron-3-super-120b-a12b:free"
                ]

                headers = {
                    "Authorization": f"Bearer {openrouter_key.strip()}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://streamlit.io",
                    "X-Title": "OKX AI Trading Dashboard"
                }

                last_error = ""
                for model_slug in free_models:
                    status.write(f"🧠 OpenRouter 모델({model_slug})에 요청 중...")
                    payload = {
                        "model": model_slug,
                        "messages": [
                            {"role": "system", "content": "너는 암호화폐 전문 트레이더 AI다. 모든 판단 이유(reason)와 답변은 반드시 100% 한국어로만 작성해라."},
                            {"role": "user", "content": prompt}
                        ]
                    }
                    try:
                        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
                        res_json = res.json()
                        
                        if "choices" in res_json and len(res_json["choices"]) > 0:
                            raw_text = res_json["choices"][0]["message"]["content"]
                            break
                        else:
                            err_info = res_json.get("error", {}).get("message", str(res_json))
                            last_error = f"{model_slug}: {err_info}"
                            status.write(f"⚠️ {model_slug} 실패 ➔ {err_info}")
                    except Exception as err:
                        last_error = str(err)
                        status.write(f"⚠️ {model_slug} 연결 예외 ➔ {err}")
                        continue

            if not raw_text:
                raise Exception(f"모든 AI 모델 연결에 실패했습니다. 마지막 오류: {last_error}")

            status.write("📥 3. AI 분석 결과 정리 중...")

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

# AI 분석 결과 출력
if st.session_state.ai_result:
    result = st.session_state.ai_result
    decision = str(result.get("decision", "hold")).upper()
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
                
                order = exchange.create_market_buy_order(ccxt_symbol, buy_btc_amount)
                st.success(f"✅ 매수 성공! {buy_usdt_amount:.2f} USDT치 BTC 구매 완료 (주문 ID: {order['id']})")
                time.sleep(1)
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
                
                order = exchange.create_market_sell_order(ccxt_symbol, sell_btc_amount)
                st.success(f"✅ 매도 성공! {sell_btc_amount:.6f} BTC 매도 완료 (주문 ID: {order['id']})")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ 매도 실패: {e}")
        else:
            st.error("보유한 BTC 수량이 부족합니다.")

st.divider()

# --- 4. 포지션 & 미체결 주문 & 매매 히스토리 섹션 ---
st.subheader("📋 계좌 포지션 및 매매 히스토리")

tab1, tab2, tab3 = st.tabs(["💼 보유 포지션 / 잔고", "⏳ 미체결 주문", "📜 매매 히스토리"])

with tab1:
    st.markdown("##### 🪙 현재 코인 보유 상태")
    btc_value_usdt = btc_balance * current_price
    btc_ratio = (btc_value_usdt / total_asset_usdt * 100) if total_asset_usdt > 0 else 0
    usdt_ratio = (usdt_balance / total_asset_usdt * 100) if total_asset_usdt > 0 else 0

    st.markdown(f"""
    | 자산 | 보유 수량 | 평가 금액 (USDT) | 자산 비중 |
    | :--- | :--- | :--- | :--- |
    | **USDT** | `{usdt_balance:,.2f} USDT` | `${usdt_balance:,.2f}` | `{usdt_ratio:.1f}%` |
    | **BTC** | `{btc_balance:.6f} BTC` | `${btc_value_usdt:,.2f}` | `{btc_ratio:.1f}%` |
    """)

with tab2:
    st.markdown("##### ⏳ 대기 중인 미체결 지정가 주문")
    try:
        open_orders = exchange.fetch_open_orders(ccxt_symbol)
        if open_orders:
            order_rows = []
            for ord_item in open_orders:
                dt_str = datetime.datetime.fromtimestamp(ord_item['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                side_str = "🟢 매수" if ord_item['side'] == 'buy' else "🔴 매도"
                order_rows.append(f"| `{ord_item['id']}` | {dt_str} | {side_str} | `${ord_item['price']:,.2f}` | `{ord_item['amount']:.6f}` | `{ord_item['status']}` |")
            
            table_header = "| 주문 ID | 시각 | 구 분 | 주문 가격 | 수 량 | 상 태 |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            st.markdown(table_header + "\n".join(order_rows))
        else:
            st.info("현재 대기 중인 미체결 주문이 없습니다.")
    except Exception as oe:
        st.warning(f"미체결 주문 조회 중 안내: {oe}")

with tab3:
    st.markdown("##### 📜 최근 체결된 주문 내역")
    try:
        closed_orders = exchange.fetch_closed_orders(ccxt_symbol, limit=10)
        if closed_orders:
            history_rows = []
            for c_ord in reversed(closed_orders):
                dt_str = datetime.datetime.fromtimestamp(c_ord['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                side_str = "🟢 매수" if c_ord['side'] == 'buy' else "🔴 매도"
                filled_qty = c_ord.get('filled', c_ord.get('amount', 0))
                avg_price = c_ord.get('price', current_price)
                total_cost = filled_qty * avg_price
                history_rows.append(f"| {dt_str} | {side_str} | `${avg_price:,.2f}` | `{filled_qty:.6f} BTC` | `${total_cost:,.2f} USDT` | `{c_ord['status']}` |")
            
            hist_header = "| 체결 시각 | 구 분 | 평균 체결가 | 체결 수량 | 총 체결금액 | 상 태 |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            st.markdown(hist_header + "\n".join(history_rows))
        else:
            st.info("최근 체결된 매매 내역이 없습니다.")
    except Exception as he:
        st.warning(f"매매 히스토리 조회 중 안내: {he}")
