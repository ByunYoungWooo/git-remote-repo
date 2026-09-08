import requests
from bs4 import BeautifulSoup

BOT_TOKEN = "8729803081:AAFC7k810CNGYhpvyLPp0MyVYJ09bhajpHg"
CHAT_ID = "8526301346"

headers = {
    "User-Agent": "Mozilla/5.0"
}

def get_price(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    res = requests.get(url, headers=headers, timeout=5)
    
    if res.status_code != 200:
        return "조회 실패", ""

    soup = BeautifulSoup(res.text, "html.parser")

    try:
        price = soup.select_one(".no_today .blind").text.strip()
        change_value = soup.select(".no_exday .blind")[1].text.strip()

        # 상승/하락 판단
        if soup.select_one(".no_exday .no_up"):
            sign = "+"
        elif soup.select_one(".no_exday .no_down"):
            sign = "-"
        else:
            sign = "➖"

        return price, f"{sign}{change_value}%"

    except Exception as e:
        return "조회 실패", ""

# 종목 리스트
stocks = {
    "KODEX 200TR": "278530",
    "KODEX 코스닥150": "229200",
    "PLUS K방산": "449450",
    "ACE 금현물": "411060",
    "TIGER S&P500": "360750",
    "SOFR 금리": "438570",
    "국고채10년": "385550"
}

msg = "보유상품 변동현황\n\n"

for name, code in stocks.items():
    price, change = get_price(code)
    msg += f"{name}: {price}원 ({change})\n"

# 텔레그램 전송
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

# 콘솔 출력 (디버깅용)
print(msg)
