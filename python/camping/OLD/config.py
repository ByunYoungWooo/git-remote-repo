"""
캠핑장 예약 자동화 시스템 - 설정 파일 (Python)

이 파일은 Selenium 기반 웹 크롤링과 Telegram 알림을 위한 설정 정보를 포함합니다.
"""

# =========================================================
# Selenium 설정
# =========================================================
SELENIUM_DRIVER_NAME = "chromedriver"  # 브라우저 드라이버명 (Chrome/Edge/Firefox)
SELENIUM_HEADLESS = False              # 실행 시 브라우저 창 표시 여부 (False = 표시, True = 숨김)
SELENIUM_IMPLICIT_WAIT = 10            # 요소 로드 대기 시간 (초)
SELENIUM_TIMEOUT = 30                  # 최대 대기 시간 (초)

# =========================================================
# 웹 페이지 URL 설정
# =========================================================
TARGET_URL = "https://reservation.knps.or.kr"        # 캠핑장 예약 사이트 기본 URL
LOGIN_URL = f"{TARGET_URL}/reservation/login.do"      # 로그인 페이지 URL
RESERVATION_SEARCH_URL = (
    f"{TARGET_URL}/reservation/searchSimpleCampReservation.do"  # 검색 및 예약 페이지
)

# =========================================================
# Telegram Bot 설정
# =========================================================
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"      # Telegram Bot Token (구독 필요)
TELEGRAM_CHAT_ID = "8526301346"                     # 알림 받을 Telegram Chat ID

# =========================================================
# 데이터베이스 설정 (MariaDB)
# =========================================================
DATABASE_CONFIG = {
    "driver": "mysql+pymysql",                      # PyMySQL 드라이버 사용
    "host": "localhost",                            # DB 호스트명
    "port": 3306,                                   # DB 포트번호
    "database": "camping_reservation_db",           # DB 이름 (생성 예정)
    "user": "root",                                 # DB 사용자
    "password": "",                                 # DB 비밀번호 (.env 에서 읽음 권장)
    "charset": "utf8mb4",                           # 문자셋
}

# =========================================================
# 예약 사이트 설정
# =========================================================
RESERVATION_CONFIG = {
    "space_types": ["카운터", "천막", "텐트", "가게"],  # 공간 유형 목록
    "capacity_limit": 50,                          # 최대 수용 인원 (기본값)
    "checkin_deadline": 23,                        # 체크인 마감 시간 (시)
    "checkout_time": 10,                           # 체크아웃 시간 (시)
    "cancellation_allowed_days": 3,                # 환불 가능 일수
}

# =========================================================
# 알림 설정
# =========================================================
NOTIFICATION_CONFIG = {
    "reservation_success": True,                   # 예약 성공 시 알림 발송
    "reservation_failed": True,                    # 예약 실패 시 알림 발송
    "cancellation_alert": True,                    # 취소 알림 발송
    "checkin_reminder": True,                      # 체크인 리마인더 발송
    "reminder_days_before_checkin": 1,             # 리마인더 일수 전 (예: 1 일 전)
}

# =========================================================
# 자동 예약 규칙 설정
# =========================================================
AUTOMATION_CONFIG = {
    "check_available_spaces": True,               # 가용 공간 자동 확인
    "auto_reservation_rules": [                    # 자동 예약 규칙 목록
        {"space_type": "카운터", "capacity": 10, "days_advance": 3},  # 카운터 10 명 이상, 3 일 전부터 예약
        {"space_type": "천막", "capacity": 5, "days_advance": 2},     # 천막 5 명 이상, 2 일 전부터 예약
        {"space_type": "텐트", "capacity": 3, "days_advance": 2},     # 텐트 3 명 이상, 2 일 전부터 예약
        {"space_type": "가게", "capacity": 10, "days_advance": 5},    # 가게 10 명 이상, 5 일 전부터 예약
    ],
    "max_concurrent_requests": 1,                 # 동시 요청 수 (경쟁 방지)
}

# =========================================================
# 로그 및 모니터링 설정
# =========================================================
LOGGING_CONFIG = {
    "log_file": "logs/reservation_bot.log",         # 로그 파일 경로
    "log_level": "INFO",                             # 로그 수준 (DEBUG/INFO/ERROR)
    "rotation_max_size_mb": 10,                      # 로그 파일 최대 크기 (MB)
    "rotation_backup_count": 5,                      # 백업 파일 수
}

# =========================================================
# 보안 설정
# =========================================================
SECURITY_CONFIG = {
    "enable_captcha_bypass": True,                   # CAPTCHA 우회 활성화 (필요시 사용)
    "session_timeout_seconds": 1800,                # 세션 타임아웃 (초, 30 분)
    "max_failed_attempts": 3,                        # 최대 실패 시도 수 (초과 시 잠금)
    "lockout_minutes": 5,                           # 잠금 기간 (분)
}

# =========================================================
# 외부 서비스 설정
# =========================================================
EXTERNAL_SERVICES = {
    "payment_gateway": None,                       # 결제 게이트웨이 (Stripe/PayPal 등)
    "calendar_sync": None,                         # 캘린더 연동 (Google Calendar 등)
    "crm_system": None,                            # CRM 시스템 연동 (Salesforce 등)
}

# =========================================================
# 환경변수 로딩 (처음에 실행)
# =========================================================
def load_environment_variables():
    """환경변수 (.env 파일) 로딩 함수"""
    import os
    
    # DB 비밀번호 (비밀번호는 .env 파일에서 읽음 권장)
    if not DATABASE_CONFIG["password"]:
        DATABASE_CONFIG["password"] = os.getenv(
            "CAMPING_DB_PASSWORD", 
            ""  # 기본값: 빈 문자열
        )
    
    # Telegram Bot Token (.env 파일에서 읽음 권장)
    TELEGRAM_BOT_TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        "YOUR_TELEGRAM_BOT_TOKEN"  # 기본값: 환경변수 사용 시 필요
    )

# =========================================================
# 주요 함수 및 유틸리티
# =========================================================

def get_available_spaces():
    """가용 공간 목록 조회 (Selenium)"""
    from selenium import webdriver
    from bs4 import BeautifulSoup
    
    driver = webdriver.Chrome()
    try:
        driver.get(RESERVATION_SEARCH_URL)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        # 공간 정보 추출 (실제 사이트 구조에 따라 수정 필요)
        available_spaces = []
        space_elements = soup.select("div.space-info")  # 실제 선택자 변경 필요
        
        for element in space_elements:
            space_info = {
                "type": element.find(class_="space-type").text.strip(),
                "capacity": int(element.find(class_="capacity").text),
                "available": element.find(class_="available").text == "가용"
            }
            available_spaces.append(space_info)
        
        return available_spaces
        
    except Exception as e:
        print(f"[오류] 가용 공간 조회 실패: {e}")
        return []
    
    finally:
        driver.quit()

def check_reservation_status():
    """예약 상태 확인"""
    # 실제 구현 시 Selenium 으로 페이지 접근 및 데이터 파싱 필요
    pass

def auto_make_reservation(space_type, capacity, date):
    """자동 예약 요청"""
    # Selenium 을 사용하여 자동 예약 로직 구현
    pass

# =========================================================
# 설정 파일 로드 및 초기화
# =========================================================
if __name__ == "__main__":
    load_environment_variables()
    print("캠핑장 예약 자동화 시스템 설정이 완료되었습니다!")
    
    # 설정 정보 출력 (테스트용)
    print(f"🎯 목표 사이트: {TARGET_URL}")
    print(f"📱 Telegram 알림 Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"🗄️ 데이터베이스: {DATABASE_CONFIG['database']}")
