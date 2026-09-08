import requests
from bs4 import BeautifulSoup

BOT_TOKEN = "8729803081:AAFC7k810CNGYhpvyLPp0MyVYJ09bhajpHg"
CHAT_ID = "8526301346"

def get_price(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    price = soup.select_one(".no_today .blind").text
    return price

samsung = get_price("005930")
kodex = get_price("278530")

msg = f"""📈 삼성전자: {samsung}원
📊 KODEX200TR: {kodex}원"""

requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={
    "chat_id": CHAT_ID,
    "text": msg
})
