import os, re
import requests
from bs4 import BeautifulSoup

if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}

def get_soup(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"네이버 요청 오류({url}): {e}")
        return None

def get_exchange_rate():
    soup = get_soup("https://finance.naver.com/marketindex/")
    if not soup:
        return "조회 실패", ""
    try:
        usd_el = soup.select_one("a.head.usd")
        rate_str  = usd_el.select_one(".value").get_text(strip=True)
        change_el = usd_el.select_one(".change").get_text(strip=True).replace(",", "")
        cur_float = float(rate_str.replace(",", ""))
        chg_float = float(change_el)
        pct = (chg_float / cur_float) * 100
        sign_str = "+" if pct > 0 else "-"
        change_val = int(abs(chg_float))
        return f"{cur_float:.2f}", f"({change_val}, {sign_str}{abs(pct):.0f}%)"
    except Exception as e:
        print(f"환율 파싱 오류: {e}")
        return "조회 실패", ""

def get_index(code: str):
    url = f"https://finance.naver.com/sise/sise_index.naver?code={code}"
    soup = get_soup(url)
    if not soup:
        return "조회 실패", ""
    try:
        cur_text   = soup.select_one("#now_value").get_text(strip=True).replace(",", "")
        cur_float  = float(cur_text.replace(",", ""))
        change_el  = soup.select_one("#change_value_and_rate")
        match = re.search(r"([+-]?\d+\.?\d*)", change_el.get_text())
        if match:
            pct_val = float(match.group(1))
            # 코스피/코스닥은 + 부호만 표시 (실제 값이 -라도 +로 표시)
            sign_str = "+"
            abs_pct = abs(pct_val)
            int_part = int(abs_pct)
            return f"{cur_float:.2f}", f"({int_part}, {sign_str}{abs_pct:.0f}%)"
        return f"{cur_float:.2f}", "(4, +0.0%)"
    except Exception as e:
        print(f"지수 파싱 오류({code}): {e}")
        return "조회 실패", ""

def get_stock_price(code: str):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    soup = get_soup(url)
    if not soup:
        return "조회 실패", ""
    try:
        price_el  = soup.select_one(".no_today .blind")
        cur_text = price_el.get_text(strip=True).replace(",", "")
        cur_float = float(cur_text.replace(",", ""))

        change_el = soup.select_one(".no_exday .blind")
        chg_txt   = change_el.get_text(strip=True)
        
        match1 = re.search(r"([+-]?\d+(?:\.\d+)?)", chg_txt)
        if match1:
            abs_chg_float = float(match1.group(1))
        else:
            abs_chg_float = 0
        
        # ETF는 변동량 부호 없이, 변동률에는 부호 표시
        sign_str_pct = "+" if abs_chg_float > 0 else "-"
        
        if cur_float != 0:
            pct = (abs_chg_float / cur_float) * 100
        else:
            pct = 0
        
        int_part = int(abs(pct))
        
        return f"{cur_float:.2f}", f"({int(abs_chg_float):.0f}, {sign_str_pct}{int_part:.0f}%)"
    except Exception as e:
        print(f"주식 파싱 오류({code}): {e}")
        return "조회 실패", ""

def get_crypto(market: str):
    try:
        r = requests.get(f"https://api.upbit.com/v1/ticker?markets={market}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()[0]
        price   = float(data["trade_price"]) / 100
        pct    = float(data["signed_change_rate"]) * 100
        sign_str = "+" if pct > 0 else "-"
        abs_pct_val = abs(pct)
        int_part = int(abs_pct_val)
        # 코인은 변동량 부호 없이, 변동률에는 부호 표시
        return f"{price:.2f}", f"({int_part}, {sign_str}{abs_pct_val:.0f}%)"
    except Exception as e:
        print(f"코인 조회 오류({market}): {e}")
        return "조회 실패", ""

ETF_MAP = {
    "KODEX 200TR": "278530",
    "KODEX 코스닥150": "229200",
    "PLUS K방산": "449450",
    "ACE 금현물": "411060",
    "TIGER S&P500": "360750",
    "SOFR 금리": "438570",
    "국고채10년": "385550"
}

msg = "상품 모니터링\n\n"

rate, rate_chg = get_exchange_rate()
msg += f"원/달러 환율: {rate} ({rate_chg})\n\n"

kospi_price, kospi_chg = get_index("200")
kosdaq_price, kosdaq_chg = get_index("202")
msg += f"코스피         :   {kospi_price} ({kospi_chg})\n"
msg += f"코스닥         :   {kosdaq_price} ({kosdaq_chg})\n"

for name, code in ETF_MAP.items():
    p, chg = get_stock_price(code)
    msg += f"{name:12s}: {str(p):6s} ({chg})\n"

btc_p, btc_c = get_crypto("KRW-BTC")
eth_p, eth_c = get_crypto("KRW-ETH")
msg += "\n🪙 코인\n"
msg += f"비트코인       : {btc_p} ({btc_c})\n"
msg += f"이더리움       :   {eth_p} ({eth_c})\n"

print(msg)

try:
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(telegram_url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    r.raise_for_status()
    print("텔레그램 전송 완료")
except Exception as e:
    print(f"텔레그램 전송 실패: {e}")
