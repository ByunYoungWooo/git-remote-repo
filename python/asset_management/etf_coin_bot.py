import os
import re
import requests
from bs4 import BeautifulSoup


# =========================================================
# 환경변수
# =========================================================
# 프로젝트 디렉터리의 .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_FILE = os.path.join(BASE_DIR, ".env")

if os.path.exists(DOTENV_FILE):
    from dotenv import load_dotenv
    load_dotenv(DOTENV_FILE)

# 공통 환경파일
ENV_FILE = "/home/wooba/.config/etf_coin_bot.env"

if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


# =========================================================
# HTTP 헤더
# =========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}


# =========================================================
# 네이버 HTML 페이지 가져오기
# =========================================================
def get_soup(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"네이버 요청 오류({url}): {e}")
        return None


# =========================================================
# 원/달러 환율
# =========================================================
def get_exchange_rate():
    soup = get_soup("https://finance.naver.com/marketindex/")
    if not soup:
        return "조회 실패", ""

    try:
        usd_el = soup.select_one("a.head.usd")
        if not usd_el:
            raise ValueError("USD 정보를 찾을 수 없습니다.")

        rate_el = usd_el.select_one(".value")
        change_el = usd_el.select_one(".change")

        if not rate_el:
            raise ValueError("환율 값을 찾을 수 없습니다.")

        cur_float = float(rate_el.get_text(strip=True).replace(",", ""))
        change_text = change_el.get_text(strip=True) if change_el else "0"

        match = re.search(r"([+-]?\d+(?:\.\d+)?)", change_text)
        change = float(match.group(1)) if match else 0

        pct = (change / cur_float * 100) if cur_float != 0 else 0

        sign_change = "+" if change >= 0 else "-"
        sign_pct = "+" if pct >= 0 else "-"

        return (
            f"{cur_float:,.2f}",
            f"{sign_change}{abs(change):.0f},{sign_pct}{abs(pct):.1f}%"
        )
    except Exception as e:
        print(f"환율 파싱 오류: {e}")
        return "조회 실패", ""


# =========================================================
# 지수 (코스피/코스닥 네이버 API)
# =========================================================
def get_index(code: str):
    url = f"https://m.stock.naver.com/api/index/{code}/price?pageSize=1&page=1"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data:
            raise ValueError("지수 데이터가 없습니다.")

        today = data[0]

        cur_str = today.get("closePrice", "0").replace(",", "")
        cur_float = float(cur_str)

        change_str = today.get("compareToPreviousClosePrice", "0").replace(",", "")
        change = float(change_str)

        fluctuations_type = str(today.get("compareToPreviousPrice", {}).get("code", ""))
        if fluctuations_type in ["4", "5"]:
            change = -abs(change)

        prev_close = cur_float - change
        pct = (change / prev_close * 100) if prev_close != 0 else 0

        sign_change = "+" if change >= 0 else "-"
        sign_pct = "+" if pct >= 0 else "-"

        return (
            f"{cur_float:,.2f}",
            f"{sign_change}{abs(change):.2f},{sign_pct}{abs(pct):.2f}%"
        )
    except Exception as e:
        print(f"지수 API 조회 오류({code}): {e}")
        return "조회 실패", ""


# =========================================================
# ETF / 주식
# =========================================================
def get_stock_price(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    soup = get_soup(url)
    if not soup:
        return "조회 실패", ""

    try:
        price_el = soup.select_one(".no_today .blind")
        if not price_el:
            raise ValueError("현재 가격을 찾을 수 없습니다.")

        cur_float = float(price_el.get_text(strip=True).replace(",", ""))

        change_el = soup.select_one(".no_exday .blind")
        if not change_el:
            return f"{cur_float:,.2f}", "+0,+0.0%"

        change_text = change_el.get_text(strip=True)
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", change_text)
        change = float(match.group(1)) if match else 0

        pct = (change / cur_float * 100) if cur_float != 0 else 0

        sign_change = "+" if change >= 0 else "-"
        sign_pct = "+" if pct >= 0 else "-"

        return (
            f"{cur_float:,.2f}",
            f"{sign_change}{abs(change):.0f},{sign_pct}{abs(pct):.1f}%"
        )
    except Exception as e:
        print(f"주식 파싱 오류(code={code}): {e}")
        return "조회 실패", ""


# =========================================================
# 코인 - Upbit API
# =========================================================
def get_crypto(market):
    try:
        url = f"https://api.upbit.com/v1/ticker?markets={market}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()

        data = r.json()[0]
        price = float(data["trade_price"])
        change = float(data["signed_change_price"])
        pct = float(data["signed_change_rate"]) * 100

        sign_change = "+" if change >= 0 else "-"
        sign_pct = "+" if pct >= 0 else "-"

        return (
            f"{price:,.0f}",
            f"{sign_change}{abs(change):,.0f},{sign_pct}{abs(pct):.2f}%"
        )
    except Exception as e:
        print(f"코인 조회 오류({market}): {e}")
        return "조회 실패", ""


# =========================================================
# ETF 목록
# =========================================================
ETF_MAP = {
    "코스피200": "278530",
    "코스닥150": "229200",
    "PLUS방산": "449450",
    "ACE금현물": "411060",
    "S&P500": "360750",
    "SOFR금리": "438570",
    "국고채10년": "385550"
}


# =========================================================
# 모바일 맞춤 여백 조절 함수
# =========================================================
def format_title(text, target_width=10):
    w = sum(2 if ord(c) > 127 else 1 for c in text)
    spaces = max(0, target_width - w)
    return text + (" " * spaces)

def make_line(name, price, change):
    # 영문명(Bit, Ether)은 공백 폭을 좁게 보정
    if name in ["Bit", "Ether"]:
        title = format_title(name, 8)
    else:
        title = format_title(name, 10)
        
    return f"{title}: {price:>11s} ({change})"


# =========================================================
# 메시지 생성
# =========================================================
lines = []

rate, rate_chg = get_exchange_rate()
lines.append(make_line("원달러환율", rate, rate_chg))

kospi_price, kospi_chg = get_index("KOSPI")
lines.append(make_line("코스피지수", kospi_price, kospi_chg))

kosdaq_price, kosdaq_chg = get_index("KOSDAQ")
lines.append(make_line("코스닥지수", kosdaq_price, kosdaq_chg))

for name, code in ETF_MAP.items():
    price, change = get_stock_price(code)
    lines.append(make_line(name, price, change))

# Bit, Ether 줄바꿈 방지용 공백 축소 적용
btc_price, btc_change = get_crypto("KRW-BTC")
lines.append(make_line("Bit", btc_price, btc_change))

eth_price, eth_change = get_crypto("KRW-ETH")
lines.append(make_line("Ether", eth_price, eth_change))

msg = "\n".join(lines)


# =========================================================
# 콘솔 출력 및 Telegram 전송
# =========================================================
print(msg)

try:
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    if not CHAT_ID:
        CHAT_ID = "8526301346"  # 현재 채널 ID 사용
    r = requests.post(
        telegram_url,
        data={
            "chat_id": CHAT_ID,
            "text": msg
        },
        timeout=10
    )
    if r.status_code == 200:
        print("✅ 텔레그램 전송 완료!")
        print(f"📤 전송 대상: {CHAT_ID}")
        print(f"📊 데이터 수: {len(msg.split(chr(10)))} 줄")
    else:
        print(f"❌ 전송 오류 (상태코드 {r.status_code}): {r.text[:200]}")
except Exception as e:
    print(f"⚠️  텔레그램 전송 실패: {e}")
