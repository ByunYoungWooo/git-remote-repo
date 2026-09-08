import requests
from bs4 import BeautifulSoup
import re

# ============================================================
# Telegram 설정
# ============================================================
BOT_TOKEN = "872980dnLE"
CHAT_ID = "8526301346"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}


# ============================================================
# 네이버 공통 요청
# ============================================================
def get_soup(url):
    try:
        res = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if res.status_code != 200:
            print(f"HTTP 오류: {res.status_code} - {url}")
            return None

        # 네이버 금융은 일부 페이지에서 EUC-KR/CP949 사용
        res.encoding = res.apparent_encoding

        return BeautifulSoup(res.text, "html.parser")

    except requests.RequestException as e:
        print(f"네이버 요청 오류: {e}")
        return None


# ============================================================
# ETF / 개별 종목
# ============================================================
def get_stock_price(code):
    """
    네이버 금융 개별 종목/ETF 조회

    반환:
        price  : 현재가
        change : 실제 등락률
    """

    url = f"https://finance.naver.com/item/main.naver?code={code}"

    soup = get_soup(url)

    if soup is None:
        return "조회 실패", ""

    try:
        # ----------------------------------------------------
        # 현재가
        # ----------------------------------------------------
        price_element = soup.select_one(".no_today .blind")

        if not price_element:
            return "조회 실패", ""

        price_text = price_element.get_text(strip=True)
        price = int(price_text.replace(",", ""))

        # ----------------------------------------------------
        # 전일 대비 가격
        # ----------------------------------------------------
        change_element = soup.select_one(".no_exday .blind")

        if not change_element:
            return f"{price:,}", "변동률 확인 불가"

        change_text = change_element.get_text(strip=True)
        change_price = float(
            change_text.replace(",", "").replace("+", "").replace("-", "")
        )

        # 상승/하락 방향
        exday = soup.select_one(".no_exday")

        if exday:
            if exday.select_one(".ico.up"):
                change_price = abs(change_price)
            elif exday.select_one(".ico.down"):
                change_price = -abs(change_price)

        # ----------------------------------------------------
        # 실제 등락률 계산
        #
        # 현재가 = 전일가 + 등락금액
        # 전일가 = 현재가 - 등락금액
        #
        # 등락률 = 등락금액 / 전일가 * 100
        # ----------------------------------------------------
        previous_price = price - change_price

        if previous_price != 0:
            change_percent = (change_price / previous_price) * 100

            if change_percent > 0:
                change = f"+{change_percent:.2f}%"
            elif change_percent < 0:
                change = f"{change_percent:.2f}%"
            else:
                change = "0.00%"
        else:
            change = "변동률 확인 불가"

        return f"{price:,}", change

    except Exception as e:
        print(f"{code} 파싱 오류: {e}")
        return "조회 실패", ""


# ============================================================
# KOSPI / KOSDAQ 지수
# ============================================================
def get_index(code):
    """
    네이버 금융 KOSPI / KOSDAQ 지수 조회
    """

    url = f"https://finance.naver.com/sise/sise_index.naver?code={code}"

    soup = get_soup(url)

    if soup is None:
        return "조회 실패", ""

    try:
        # 현재 지수
        price_element = soup.select_one("#now_value")

        if not price_element:
            print(f"{code}: 현재 지수 값을 찾지 못했습니다.")
            return "조회 실패", ""

        price = price_element.get_text(strip=True)

        # 전일 대비 + 등락률
        change_element = soup.select_one("#change_value_and_rate")

        if not change_element:
            print(f"{code}: 등락률을 찾지 못했습니다.")
            return price, "변동률 확인 불가"

        change_text = change_element.get_text(" ", strip=True)

        # 예:
        # "234.30 +3.56% 상승"
        # "2.46 +0.29% 상승"
        #
        # 등락률만 추출
        match = re.search(
            r"[+-]\d+(?:\.\d+)?%",
            change_text
        )

        if match:
            change = match.group(0)
        else:
            change = "변동률 확인 불가"

        return price, change

    except Exception as e:
        print(f"{code} 지수 파싱 오류: {e}")
        return "조회 실패", ""


# ============================================================
# 코인 (업비트)
# ============================================================
def get_crypto(market):
    url = f"https://api.upbit.com/v1/ticker?markets={market}"

    try:
        res = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        res.raise_for_status()

        data = res.json()

        if not data:
            return "조회 실패", ""

        ticker = data[0]

        price = format(
            int(ticker["trade_price"]),
            ","
        )

        change = ticker["signed_change_rate"] * 100

        if change > 0:
            sign = "+"
        elif change < 0:
            sign = "-"
        else:
            sign = "➖"

        return price, f"{sign}{abs(change):.2f}%"

    except Exception as e:
        print(f"{market} 코인 조회 오류: {e}")
        return "조회 실패", ""


# ============================================================
# 환율 (네이버 금융 및 API Fallback)
# ============================================================
def get_exchange_rate():
    # 1. 네이버 금융 시도
    naver_url = "https://finance.naver.com/marketfinance/exchange/exchange_info.naver"
    soup = get_soup(naver_url)
    
    if soup is not None:
        try:
            rows = soup.select(".bo_market table tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) > 1 and ("원/달러" in cells[0].get_text() or "USD" in cells[0].get_text()):
                    price_text = cells[2].get_text(strip=True)
                    change_text = cells[3].get_text(strip=True)
                    
                    price = int(price_text.replace(",", ""))
                    
                    match = re.search(r"[+-]?\d+(?:\.\d+)?%", change_text)
                    change = match.group(0) if match else "변동률 확인 불가"
                    
                    return f"{price:,}", change
            return "네이버 조회 실패", "변동률 확인 불가"
        except Exception as e:
            print(f"네이버 환율 파싱 오류: {e}")

    # 2. 실패 시 API Fallback (open.er-api.com)
    try:
        api_url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(api_url, timeout=10)
        res.raise_for_status()
        data = res.json()
        rate = data["rates"]["KRW"]
        return f"{rate:,.2f}", "변동률 확인 불가"
    except Exception as e:
        print(f"환율 API 조회 실패: {e}")
        return "조회 실패", ""


# ============================================================
# ETF 리스트
# ============================================================
stocks = {
    "KODEX 200TR": "278530",
    "KODEX 코스닥150": "229200",
    "PLUS K 방산": "449450",
    "ACE 금현물": "411060",
    "TIGER S&P500": "360750",
    "SOFR 금리": "438570",
    "국고채10년": "385550"
}


# ============================================================
# 메시지 생성
# ============================================================
msg = "상품 모니터링\n\n"


# ------------------------------------------------------------
# 환율
# ------------------------------------------------------------
rate, rate_change = get_exchange_rate()

msg += f"💱 원/달러 환율: {rate} ({rate_change})\n\n"


# ------------------------------------------------------------
# KOSPI
# ------------------------------------------------------------
kospi_price, kospi_change = get_index("KOSPI")

msg += (
    f"코스피(KOSPI): "
    f"{kospi_price} "
    f"({kospi_change})\n"
)


# ------------------------------------------------------------
# KOSDAQ
# ------------------------------------------------------------
kosdaq_price, kosdaq_change = get_index("KOSDAQ")

msg += (
    f"코스닥(KOSDAQ): "
    f"{kosdaq_price} "
    f"({kosdaq_change})\n"
)


# ------------------------------------------------------------
# ETF
# ------------------------------------------------------------
for name, code in stocks.items():

    price, change = get_stock_price(code)

    msg += (
        f"{name}: "
        f"{price}원 "
        f"({change})\n"
    )


# ------------------------------------------------------------
# 코인
# ------------------------------------------------------------
btc_price, btc_change = get_crypto("KRW-BTC")
eth_price, eth_change = get_crypto("KRW-ETH")

msg += "\n🪙 코인\n"

msg += (
    f"비트코인: "
    f"{btc_price}원 "
    f"({btc_change})\n"
)

msg += (
    f"이더리움: "
    f"{eth_price}원 "
    f"({eth_change})\n"
)


# ============================================================
# 콘솔 출력
# ============================================================
print(msg)


# ============================================================
# 텔레그램 전송
# ============================================================
try:

    telegram_url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        telegram_url,
        data={
            "chat_id": CHAT_ID,
            "text": msg
        },
        timeout=10
    )

    if response.status_code != 200:

        print(
            f"텔레그램 전송 실패 (Status: {response.status_code}): {response.text}"
        )

    else:

        print("텔레그램 전송 완료")

except Exception as e:

    print(f"텔레그램 전송 오류 발생: {e}")
