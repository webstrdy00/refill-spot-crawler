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

# 지역별 검색 설정
REGIONS = {
    "강남": {
        "name": "서울 강남",
        "rect": "37.4979,127.0276,37.5279,127.0576",  # 강남구 영역
        "keywords": [
            "서울 강남 무한리필",
            "강남 고기무한리필", 
            "강남 소고기무한리필",
            "강남 삼겹살무한리필",
            "강남 뷔페",
            "강남역 무한리필"
        ]
    },
    "홍대": {
        "name": "서울 홍대",  
        "rect": "37.5520,126.9200,37.5620,126.9300",  # 홍대 영역
        "keywords": [
            "서울 홍대 무한리필",
            "홍대 고기무한리필",
            "홍대 삼겹살무한리필", 
            "홍대 뷔페"
        ]
    },
    "강북": {
        "name": "서울 강북",
        "rect": "37.6350,127.0250,37.6450,127.0350",  # 강북구 영역  
        "keywords": [
            "서울 강북 무한리필",
            "강북 고기무한리필",
            "강북 뷔페"
        ]
    }
}

# MVP 테스트용 기본 설정 (강남)
TEST_REGION = "강남"
TEST_RECT = REGIONS[TEST_REGION]["rect"] 
TEST_KEYWORDS = REGIONS[TEST_REGION]["keywords"]

# 기본 무한리필 키워드 (지역명 없이)
BASIC_KEYWORDS = [
    "무한리필",
    "고기무한리필", 
    "소고기무한리필",
    "삼겹살무한리필",
    "초밥뷔페",
    "해산물무한리필"
]