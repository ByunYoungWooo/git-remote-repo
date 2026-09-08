import requests
from bs4 import BeautifulSoup

# 실제 토큰과 ID를 입력해주세요. (보안을 위해 실제 실행 시에는 환경변수 사용을 권장합니다)
BOT_TOKEN = "872980…jpHg"
CHAT_ID = "8526301346"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# -----------------------
# 주식/ETF (네이버)
# -----------------------
def get_price(code):
    # 네이버 금융 페이지 URL (코드값이 숫자인 경우를 위해 문자열 변환)
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return "조회 실패", ""

        soup = BeautifulSoup(res.text, "html.parser")

        # 현재가 추출 (네이버 금융 구조에 따라 .no_today .blind 또는 .nv_now 사용)
        price_element = soup.select_one(".no_today .blind")
        if not price_element:
            # 지수 등의 다른 구조 대응
            price_element = soup.select_one(".nv_now")
            
        if price_element:
            price = price_element.get_text().replace(",", "").strip()
        else:
            return "조회 실패", ""

        # 변동률 추출
        sign = "➖"
        change_value = ""
        
        # 변동률이 있는 요소 찾기
        ex_day_element = soup.select_one(".no_exday")
        if ex_day_element:
            # 변동률 텍스트가 포함된 요소 찾기 (보통 .blind에 있음)
            blinds = ex_day_element.select(".blind")
            if len(blinds) > 1:
                change_value = blinds[1].get_text().strip()
            
            if ".no_up" in ex_day_element.get("class", "") or soup.select_one(".no_exday.no_up"):
                sign = "+"
            elif ".no_down" in ex_day_element.get("class", "") or soup.select_one(".no_exday.no_down"):
                sign = "-"

        # 변동률에 포함된 기호 제거 후 출력 (나중에 합침)
        clean_change = change_value.replace("+", "").replace("-", "").replace("%", "").strip()
        return price, f"{sign}{clean_change}%"

    except Exception as e:
        return "조회 실패", ""


# -----------------------
# 코인 (업비트)
# -----------------------
def get_crypto(market):
    url = f"https://api.upbit.com/v1/ticker?markets={market}"
    
    try:
        res = requests.get(url, timeout=5).json()[0]
        price = format(int(res["trade_price"]), ",")
        change = res["signed_change_rate"] * 100

        if change > 0:
            sign = "+"
        elif change < 0:
            sign = "-"
        else:
            sign = "➖"

        return price, f"{sign}{abs(change):.2f}%"

    except:
        return "조회 실패", ""


# -----------------------
# 환율 (USD/KRW)
# -----------------------
def get_exchange_rate():
    url = "https://open.er-api.com/v6/latest/USD"
    try:
        res = requests.get(url, timeout=5).json()
        rate = res["rates"]["KRW"]
        return f"{rate:,.2f}"
    except:
        return "조회 실패"

# -----------------------
# 종목 리스트
# -----------------------
stocks = {
    "코스피(KOSPI)": "001",
    "코스닥(KOSDAQ)": "002",
    "KODEX 200TR": "278530",
    "KODEX 코스닥150": "229200",
    "PLUS K방산": "449450",
    "ACE 금현물": "411060",
    "TIGER S&P500": "360750",
    "SOFR 금리": "438570",
    "국고채10년": "385550"
}

# -----------------------
# 메시지 생성
# -----------------------
msg = "📦 상품 모니터링\n\n"

# 환율
rate = get_exchange_rate()
msg += f"💱 원/달러 환율: {rate}\n\n"

# ETF / 주식 / 지수
for name, code in stocks.items():
    price, change = get_price(code)
    msg += f"{name}: {price}원 ({change})\n"

# 코인
btc_price, btc_change = get_crypto("KRW-BTC")
eth_price, eth_change = get_crypto("KRW-ETH")

msg += "\n🪙 코인\n"
msg += f"비트코인: {btc_price}원 ({btc_change})\n"
msg += f"이더리움: {eth_price}원 ({btc_change})\n" # 이더리움도 btc_change로 잘못 들어간 것 같으니 수정 필요

# 수정: 이더리움 변동률 적용
msg = msg.replace(f"({btc_change})", f"({eth_change})")
# 위 라인은 문법적으로 복잡할 수 있으니 아래처럼 다시 구성하겠습니다.

# 재구성된 메시지 생성 부분
msg = "📦 상품 모니터링\n\n"
msg += f"💱 원/달러 환율: {get_exchange_rate()}\n\n"

for name, code in stocks.items():
    p, c = get_price(code)
    msg += f"{name}: {p}원 ({c})\n"

msg += "\n🪙 코인\n"
msg += f"비트코인: {get_crypto('KRW-BTC')[0]}원 ({get_crypto('KRW-BTC')[1]})\n"
msg += f"이더리움: {get_crypto('KRW-ETH')[0]}원 ({get_crypto('KRW-ETH')[1]})\n"

# 위 로직을 통합하여 최종적으로 clean하게 다시 씁니다.
# (아래는 실제 파일에 들어갈 내용입니다)
