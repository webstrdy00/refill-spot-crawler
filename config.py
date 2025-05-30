import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# 환경 변수 로드
load_dotenv()

# PostgreSQL 연결 설정 (DATABASE_URL 우선, 개별 설정 fallback)
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password123@localhost:5432/refill_spot')

# DATABASE_URL 파싱
parsed_url = urlparse(DATABASE_URL)

DB_HOST = parsed_url.hostname or os.getenv('DB_HOST', 'localhost')
DB_PORT = parsed_url.port or int(os.getenv('DB_PORT', '5432'))
DB_NAME = parsed_url.path.lstrip('/') or os.getenv('DB_NAME', 'refill_spot')
DB_USER = parsed_url.username or os.getenv('DB_USER', 'postgres')
DB_PASSWORD = parsed_url.password or os.getenv('DB_PASSWORD', 'password123')

# 크롤링 설정
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
]

# 크롤링 지연 시간 (초)
MIN_DELAY = 3
MAX_DELAY = 5

# 테스트용 강남구 rect 좌표 (좌하단lat, 좌하단lng, 우상단lat, 우상단lng)
TEST_RECT = "37.4979,127.0276,37.5279,127.0576"

# 검색 키워드
KEYWORDS = [
    "무한리필"
]