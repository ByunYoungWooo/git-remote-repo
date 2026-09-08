import requests
from bs4 import BeautifulSoup

BOT_TOKEN = "8729803081:AAFC7k810CNGYhpvyLPp0MyVYJ09bhajpHg"
CHAT_ID = "8526301346"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# -----------------------
# 주식/ETF (네이버)
# -----------------------
def get_price(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    res = requests.get(url, headers=headers, timeout=5)
    
    if res.status_code != 200:
        return "조회 실패", ""

    soup = BeautifulSoup(res.text, "html.parser")

    try:
        price = soup.select_one(".no_today .blind").text.strip()
        change_value = soup.select(".no_exday .blind")[1].text.strip()

        if soup.select_one(".no_exday .no_up"):
            sign = "+"
        elif soup.select_one(".no_exday .no_down"):
            sign = "-"
        else:
            sign = "➖"

        return price, f"{sign}{change_value}%"

    except:
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
msg += f"이더리움: {eth_price}원 ({eth_change})\n"


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
