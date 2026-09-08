import requests
from bs4 import BeautifulSoup

BOT_TOKEN = "***"
CHAT_ID = "8526301346"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

# -----------------------
# 주식/ETF/지수 (네이버)
# -----------------------
def get_price(code):
    # 지수(KOSPI, KOSDAQ)와 일반 종목 구분
    if code in ["KOSPI", "KOSDAQ"]:
        # 모바일 페이지가 구조가 훨씬 단순하고 안정적입니다.
        url = f"https://m.stock.naver.com/domestic/index/{code}/total"
    else:
        url = f"https://finance.naver.com/item/main.naver?code=***}"
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return "조회 실패", ""
        soup = BeautifulSoup(res.text, "html.parser")

        if code in ["KOSPI", "KOSDAQ"]:
            # 모바일 페이지 구조에 맞춘 선택자
            # 보통 'price' 클래스나 특정 span 안에 가격이 위치합니다.
            price_element = soup.select_one(".price_info .num") or soup.select_one(".price_info .cur_price")
            if not price_element:
                # 구조가 바뀔 경우를 대비한 대체 선택자
                price_element = soup.select_one(".price_info .no_today .blind")
            
            if not price_element:
                return "조회 실패", ""
            
            price = price_element.text.strip().replace(",", "")
            
            # 변동률 추출 (모바일은 구조가 조금 다를 수 있어 단순화)
            change_element = soup.select_one(".price_info .rate")
            if change_element:
                change_value = change_element.text.strip().replace("%", "")
                # 양수/음수 판단 (텍스트에 +나 -가 포함됨)
                if "-" in change_value or "▲" in change_value: # 사실 모바일은 보통 색상이나 기호로 표시
                    # 간단하게 수치만 추출
                    sign = "-" if "-" in change_value else "+"
                else:
                    sign = "+"
                return price, f"{sign}{change_value}%"
            else:
                return price, "변동률 확인 불가"
        else:
            # 일반 종목 페이지용 선택자
            price_element = soup.select_one(".no_today .blind")
            if not price_element:
                return "조회 실패", ""
            
            price = price_element.text.strip()
            
            # 변동률 추출
            change_element = soup.select_one(".no_exday .blind")
            if change_element:
                change_value = change_element.text.strip()
                if soup.select_one(".no_exday .no_up"):
                    sign = "+"
                elif soup.select_one(".no_exday .no_down"):
                    sign = "-"
                else:
                    sign = "➖"
                return price, f"{sign}{change_value}%"
            else:
                return price, "변동률 확인 불가"

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
    "코스피(KOSPI)": "KOSPI",
    "코스닥(KOSDAQ)": "KOSDAQ",
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
msg = "상품 모니터링\n\n"

# 환율
rate = get_exchange_rate()
msg += f"💱 원/달러 환율: {rate}\n\n"

# ETF / 주식
for name, code in stocks.items():
    price, change = get_price(code)
    msg += f"{name}: {price}원 ({change})\n"

# 코인
btc_price, btc_change = get_crypto("KRW-BTC")
eth_price, eth_change = get_crypto("KRW-ETH")

msg += "\n🪙 코인\n"
msg += f"비트코인: {btc_price}원 ({btc_change})\n"
msg += f"이더리움: {eth_price}원 ({btc_change})\n"


# -----------------------
# 텔레그램 전송
# -----------------------
try:
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": msg
        },
        timeout=5
    )
except Exception as e:
    print("텔레그램 전송 실패:", e)

# 콘솔 출력
print(msg)
