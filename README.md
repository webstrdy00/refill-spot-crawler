# 다이닝코드 무한리필 크롤러 (개선 버전)

다이닝코드 웹사이트에서 무한리필 가게 정보를 수집하는 Python 크롤링 프로그램입니다.

## 🚀 빠른 시작

### 1. 가상환경 설정 (Windows)

```bash
# 자동 설정 스크립트 실행 (추천)
setup_venv.bat

# 또는 수동 설정
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 가상환경 설정 (Linux/Mac)

```bash
# 자동 설정
chmod +x setup.sh
./setup.sh

# 또는 수동 설정
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 크롤링 테스트

```bash
# 가상환경 활성화 후
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 개선된 크롤러 테스트 (추천)
python test_improved_crawler.py

# 단일 가게 상세 테스트
python test_improved_crawler.py single

# 기존 간단한 테스트
python test_simple_crawler.py
```

## 🔧 주요 개선사항

### 크롤링 성능 개선

- **다중 선택자 지원**: 여러 CSS 선택자로 정보 추출 시도
- **강화된 좌표 추출**: JavaScript 변수에서 위도/경도 정확히 추출
- **개선된 주소 파싱**: 한국 주소 패턴 인식 강화
- **전화번호 정규화**: 다양한 형식의 전화번호 추출
- **에러 처리 강화**: 상세한 오류 로그 및 복구 로직

### 데이터 품질 향상

- **품질 점수 시스템**: 수집된 데이터의 완성도 평가
- **무한리필 관련성 검증**: 키워드 기반 관련성 자동 체크
- **중복 제거**: 동일 가게 중복 수집 방지
- **데이터 검증**: 좌표 범위, 전화번호 형식 등 유효성 검사

## 📊 테스트 결과 분석

### 데이터 품질 지표

- 좌표 정보 수집률
- 주소 정보 수집률
- 전화번호 수집률
- 카테고리 정보 수집률
- 이미지 수집률
- 무한리필 관련성 비율

### 결과 파일

- `improved_crawler_test_YYYYMMDD_HHMMSS.json`: 전체 테스트 결과
- `single_store_test.json`: 단일 가게 상세 테스트 결과
- `test_improved_crawler.log`: 상세 실행 로그

## 🎯 지역별 키워드 시스템

### 왜 지역별 키워드가 필요한가?

다이닝코드에서는 "무한리필"만 검색하면 결과가 잘 나오지 않습니다.
"서울 강남 무한리필" 처럼 지역명을 포함해야 정확한 검색 결과를 얻을 수 있습니다.

### 지원 지역 및 키워드

```python
# config.py에서 설정
REGIONS = {
    "강남": {
        "name": "서울 강남",
        "keywords": [
            "서울 강남 무한리필",
            "강남 고기무한리필",
            "강남 소고기무한리필",
            "강남 삼겹살무한리필",
            "강남 뷔페",
            "강남역 무한리필"
        ]
    }
}
```

### 키워드 테스트

```bash
# 모든 키워드의 검색 결과 수 확인
python main.py keywords

# 결과 예시:
# 서울 강남 무한리필: 15개
# 강남 고기무한리필: 8개
# 강남 삼겹살무한리필: 12개
# 추천 키워드: '서울 강남 무한리필' (15개 가게)
```

🗺️ PostGIS 기능
공간 데이터 처리

자동 좌표 변환: 위도/경도 → PostGIS GEOMETRY
공간 인덱싱: GIST 인덱스로 빠른 위치 검색
거리 계산: 반경 기반 가게 검색 지원

제공되는 공간 함수
sql-- 반경 1km 내 가게 검색
SELECT \* FROM stores_within_radius(37.5665, 126.9780, 1000);

-- 필터링 검색 (거리 + 평점 + 카테고리)
SELECT \* FROM stores_filter(37.5665, 126.9780, 2000, 4.0, ARRAY['무한리필', '고기']);

-- 카테고리별 가게 검색
SELECT \* FROM stores_by_categories(ARRAY['무한리필']);
📊 데이터베이스 스키마 (기존 프로젝트 호환)
stores 테이블
sql- id: 기본키

- name: 가게 이름
- address: 주소
- position_lat/lng: 위도/경도 (필수)
- position_x/y: 카카오맵 좌표 (선택)
- naver_rating: 네이버 평점
- kakao_rating: 카카오 평점
- diningcode_rating: 다이닝코드 평점 ⭐ 크롤링
- diningcode_place_id: 다이닝코드 고유 ID ⭐ 크롤링
- raw_categories_diningcode: 원본 카테고리 ⭐ 크롤링
- geom: PostGIS 공간 데이터 (자동 생성)
  크롤링 추가 테이블

crawling_logs: 크롤링 세션 로그 및 통계
categories: 카테고리 마스터 데이터
store_categories: 가게-카테고리 연결

🐳 Docker 관리
기본 명령어
bash# PostGIS 지원 PostgreSQL 시작
docker-compose up -d postgres

# pgAdmin 웹 관리도구

docker-compose up -d pgadmin

# 접속: http://localhost:5050

# 이메일: admin@example.com, 비밀번호: admin123

# 컨테이너 상태 확인

docker-compose ps

# 로그 확인

docker-compose logs postgres

# 모든 서비스 종료

docker-compose down
데이터베이스 연결 정보 (DATABASE_URL)
bash# 로컬 Docker
DATABASE_URL=postgresql://postgres:password123@localhost:5432/refill_spot

# Supabase

DATABASE_URL=postgresql://postgres:your-password@db.your-project-id.supabase.co:5432/postgres

# 기타 예시는 DATABASE_URL_EXAMPLES.md 참조

📁 파일 구조
refill-spot-crawler/
├── requirements.txt # Python 3.12 호환 의존성
├── config.py # 설정 파일
├── crawler.py # 크롤링 로직
├── database.py # PostGIS 지원 DB 처리
├── main.py # 메인 실행 스크립트
├── test_connection.py # 환경 검증 스크립트
├── docker-compose.yml # PostGIS + pgAdmin
├── init.sql # PostGIS 기반 스키마
├── setup.sh # 자동 설정 스크립트
├── .env.example # 환경변수 예시
└── README.md # 이 파일
🎯 크롤링 결과
파일 출력
bashmvp_crawling_result.csv # 크롤링된 데이터 CSV
crawler.log # 크롤링 상세 로그
refill_spot_crawler.log # 메인 프로세스 로그
데이터베이스 저장

PostGIS 자동 처리: 위도/경도 → 공간 데이터 변환
중복 방지: diningcode_place_id 기반
카테고리 자동 매핑: 무한리필 + 원본 카테고리
크롤링 로그: 세션별 통계 및 오류 추적

📈 통계 및 모니터링
실시간 통계 조회
bash# 데이터베이스 통계 확인
python -c "
from database import DatabaseManager
db = DatabaseManager()
stats = db.get_crawling_stats()
for k, v in stats.items(): print(f'{k}: {v}')
db.close()
"
주요 통계 항목

총 가게 수
좌표 있는 가게 수
전화번호 있는 가게 수
평점 있는 가게 수
평균 평점
카테고리 수
마지막 크롤링 시간

🔧 고급 설정
config.py 주요 설정
python# 현재 테스트 지역
TEST_REGION = "강남" # "강남", "홍대", "강북" 중 선택

# 지역별 좌표 및 키워드 설정

REGIONS = {
"강남": {
"name": "서울 강남",
"rect": "37.4979,127.0276,37.5279,127.0576",
"keywords": ["서울 강남 무한리필", "강남 고기무한리필", ...]
}
}

# 크롤링 지연 (IP 차단 방지)

MIN_DELAY = 3 # 최소 3초
MAX_DELAY = 5 # 최대 5초
🔄 지역 확장 방법
새로운 지역 추가
python# config.py에 새 지역 추가
REGIONS = { # 기존 지역들...
"신촌": {
"name": "서울 신촌",
"rect": "37.5580,126.9330,37.5680,126.9430", # 신촌 좌표
"keywords": [
"서울 신촌 무한리필",
"신촌 고기무한리필",
"신촌 뷔페"
]
}
}

# 테스트 지역 변경

TEST_REGION = "신촌"
좌표 찾는 방법

Google Maps에서 지역 확인
좌하단, 우상단 좌표 추출
"lat1,lng1,lat2,lng2" 형식으로 입력

📊 크롤링 성능 최적화
키워드 우선순위
크롤링 결과에 따라 키워드 우선순위를 조정할 수 있습니다:
bash# 키워드 테스트로 최적 키워드 찾기
python main.py keywords

# 결과 기반으로 config.py 수정

# 가장 많은 결과를 가져오는 키워드를 첫 번째로 배치

검색 결과 개선 팁

지역명 포함 필수: "강남 무한리필" > "무한리필"
구체적 키워드: "고기무한리필" > "무한리필"
역명 활용: "강남역 무한리필"
음식 카테고리: "삼겹살무한리필", "초밥뷔페"

🎯 크롤링 결과 품질
예상 수집량 (강남 지역 기준)

서울 강남 무한리필: 10-20개 가게
강남 고기무한리필: 5-15개 가게
강남 뷔페: 8-18개 가게

데이터 품질 지표

좌표 정확도: 90%+ (JavaScript에서 직접 추출)
전화번호: 70%+
평점 정보: 80%+
카테고리 태그: 95%+

🔍 문제 해결 가이드
검색 결과가 없을 때
bash# 1. 키워드 테스트로 문제 확인
python main.py keywords

# 2. 다른 지역으로 테스트

# config.py에서 TEST_REGION 변경

# 3. 네트워크 및 ChromeDriver 확인

python test_connection.py
검색 결과가 적을 때

키워드 추가: 더 다양한 키워드 조합 시도
검색 영역 확장: rect 좌표 범위 넓히기
다른 지역 시도: 강남, 홍대, 강북 순으로 테스트

IP 차단 대응
python# config.py에서 지연 시간 증가
MIN_DELAY = 5 # 5초로 증가
MAX_DELAY = 8 # 8초로 증가

# User-Agent 로테이션 (자동)

USER_AGENTS = [...] # 이미 설정됨
📈 확장 로드맵
2단계: 서울 전체
python# 추가할 주요 지역들
"종로", "중구", "용산", "성동", "광진", "동대문",
"중랑", "성북", "강북", "도봉", "노원", "은평",
"서대문", "마포", "양천", "강서", "구로", "금천",
"영등포", "동작", "관악", "서초", "강남", "송파", "강동"
3단계: 전국 확장
python# 광역시 추가
"부산", "대구", "인천", "광주", "대전", "울산"

# 주요 도시 추가

"수원", "성남", "고양", "용인", "부천", "안산", "안양"
4단계: 고도화

병렬 처리: 멀티스레딩으로 성능 향상
실시간 모니터링: 크롤링 상태 대시보드
자동 스케줄링: 주기적 업데이트
다중 플랫폼: 네이버, 카카오맵 추가

⚡ 실제 사용 시나리오
시나리오 1: 강남 지역 무한리필 맛집 수집
bash# 1. 강남 지역 설정 확인
python -c "import config; print(config.REGIONS['강남'])"

# 2. 키워드 테스트

python main.py keywords

# 3. 실제 크롤링 (3-5개 가게)

python main.py test

# 4. 더 많은 데이터 수집

python main.py full
시나리오 2: 새로운 지역 추가
bash# 1. config.py에 새 지역 추가

# 2. TEST_REGION 변경

# 3. 키워드 테스트로 검증

python main.py keywords

# 4. 결과가 좋으면 본격 크롤링

python main.py full
시나리오 3: 데이터 품질 검증
bash# 1. 통계 확인
python main.py db

# 2. CSV 파일 분석

head mvp_crawling_result.csv

# 3. 데이터베이스에서 직접 확인

docker-compose exec postgres psql -U postgres -d refill_spot -c "
SELECT name, address, diningcode_rating,
cardinality(raw_categories_diningcode) as tag_count
FROM stores
ORDER BY created_at DESC
LIMIT 10;
"

🎉 정리
핵심 개선사항:

✅ 지역별 키워드: "서울 강남 무한리필" 방식으로 검색 정확도 향상
✅ 키워드 테스트: python main.py keywords로 최적 키워드 찾기
✅ 다중 지역 지원: 강남, 홍대, 강북 등 확장 가능한 구조
✅ 검색 결과 최적화: 지역명 포함으로 더 정확한 데이터 수집

이제 "서울 강남 무한리필" 키워드로 정확한 검색 결과를 얻을 수 있습니다! 🚀
먼저 python main.py keywords로 어떤 키워드가 가장 많은 결과를 가져오는지 확인해보세요! 차단 방지)
MIN_DELAY = 3 # 최소 3초
MAX_DELAY = 5 # 최대 5초
MIN_DELAY = 3 # 최소 3초
MAX_DELAY = 5 # 최대 5초
🐛 트러블슈팅
PostGIS 관련 오류
bash# PostGIS 확장 확인
docker-compose exec postgres psql -U postgres -d refill_spot -c "SELECT PostGIS_Version();"

# 수동 확장 설치

docker-compose exec postgres psql -U postgres -d refill_spot -c "CREATE EXTENSION IF NOT EXISTS postgis;"
크롤링 오류
bash# ChromeDriver 버전 확인
chromedriver --version
google-chrome --version

# 로그 실시간 모니터링

tail -f refill_spot_crawler.log
성능 최적화
sql-- 공간 인덱스 재구성
REINDEX INDEX idx_stores_geom;

-- 통계 업데이트
ANALYZE stores;
🎯 다음 단계 (2단계)
확장 계획

지역 확장: 서울 전체 → 전국 주요 도시
상세 정보 강화: 메뉴, 가격, 영업시간 파싱
다중 플랫폼: 네이버, 카카오맵 추가 크롤링
실시간 업데이트: 주기적 상태 확인
성능 최적화: 병렬 처리, 배치 최적화

기술 개선

공간 분할: shapely 기반 지역 자동 분할
좌표계 변환: WGS84 ↔ EPSG:5179 지원
캐싱: Redis 기반 중간 결과 캐시
모니터링: Grafana 대시보드

⚠️ 주의사항

Python 3.12 최적화: 최신 버전 활용
PostGIS 필수: 공간 데이터 처리를 위한 확장
robots.txt 준수: 3-5초 지연으로 서버 부하 최소화
데이터 품질: 좌표 유효성 검증 필수
법적 준수: 개인정보보호법, 저작권법 준수

🤝 기존 프로젝트와의 호환성
이 크롤러는 기존 Refill Spot 프로젝트의 스키마와 완전 호환됩니다:
✅ 호환되는 기능

PostGIS 공간 데이터: geom 컬럼 자동 생성
반경 검색 함수: stores_within_radius() 동일
필터링 함수: stores_filter() 동일
카테고리 시스템: 기존 구조 유지
평점 시스템: naver_rating, kakao_rating, diningcode_rating 지원

🆕 추가된 기능

크롤링 로그: crawling_logs 테이블로 모니터링
다이닝코드 특화: diningcode_place_id, raw_categories_diningcode
통계 함수: get_crawling_stats() 추가
자동 업데이트: updated_at 트리거

🔄 마이그레이션 가이드
기존 데이터베이스가 있다면:
sql-- 크롤링 필드 추가
ALTER TABLE stores ADD COLUMN IF NOT EXISTS diningcode_place_id TEXT UNIQUE;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS diningcode_rating FLOAT;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS raw_categories_diningcode TEXT[];
ALTER TABLE stores ADD COLUMN IF NOT EXISTS open_hours_raw TEXT;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS status TEXT DEFAULT '운영중';

-- 크롤링 로그 테이블 생성
CREATE TABLE crawling_logs (
-- 위의 init.sql 내용 참조
);
🚀 실제 사용 예시

1. 환경 설정 및 실행
   bash# 1. 저장소 클론
   git clone <repository-url>
   cd refill-spot-crawler

# 2. 자동 설정

./setup.sh

# 3. 환경 검증

python test_connection.py

# 4. 크롤링 실행

python main.py test # 1개 가게 테스트
python main.py full # 5개 가게 크롤링 2. 결과 확인
bash# CSV 파일 확인
head mvp_crawling_result.csv

# 데이터베이스 확인

docker-compose exec postgres psql -U postgres -d refill_spot -c "
SELECT name, address, diningcode_rating,
array_length(raw_categories_diningcode, 1) as category_count
FROM stores
ORDER BY created_at DESC
LIMIT 5;
" 3. 공간 검색 테스트
bash# 강남역 반경 1km 내 무한리필 가게 검색
docker-compose exec postgres psql -U postgres -d refill_spot -c "
SELECT name, address, distance
FROM stores_within_radius(37.4979, 127.0276, 1000)
ORDER BY distance
LIMIT 10;
"
📊 예상 성능
MVP 단계 (1단계)

처리 속도: 가게당 5-8초 (지연 시간 포함)
수집량: 시간당 약 500-700개 가게
정확도: 좌표 추출 90%+, 기본 정보 95%+
메모리 사용량: 100-200MB

확장 후 (2-3단계)

처리 속도: 병렬화로 3-5배 향상 예상
수집량: 일일 10,000-50,000개 가게 목표
커버리지: 전국 주요 도시 95%+

🔍 데이터 품질 관리
자동 검증

좌표 유효성: 한국 영토 내 좌표만 허용
무한리필 관련성: 키워드 기반 필터링
중복 제거: diningcode_place_id 기준

수동 검토 포인트

주소 정규화: 도로명주소 vs 지번주소
카테고리 매핑: 다이닝코드 → 표준 카테고리
영업시간 파싱: 다양한 형식 통일

💡 개발자 팁
디버깅
bash# 특정 가게 ID로 디버깅
python -c "
from crawler import DiningCodeCrawler
crawler = DiningCodeCrawler()
store = {'diningcode_place_id': 'TARGET_ID', 'detail_url': '/TARGET_URL'}
result = crawler.get_store_detail(store)
print(result)
crawler.close()
"
성능 모니터링
bash# 크롤링 로그 분석
docker-compose exec postgres psql -U postgres -d refill_spot -c "
SELECT keyword, rect_area, stores_found, stores_processed,
errors, (completed_at - started_at) as duration
FROM crawling_logs
ORDER BY started_at DESC
LIMIT 10;
"
백업 및 복구
bash# 데이터베이스 백업
docker-compose exec postgres pg_dump -U postgres refill_spot > backup.sql

# 복구

docker-compose exec -T postgres psql -U postgres refill_spot < backup.sql

📞 지원 및 문의
로그 파일 위치

refill_spot_crawler.log: 메인 프로세스 로그
crawler.log: 크롤링 상세 로그

디버깅 체크리스트

✅ ChromeDriver 버전 확인
✅ Docker PostgreSQL 실행 상태
✅ PostGIS 확장 설치 확인
✅ 네트워크 연결 상태
✅ 다이닝코드 사이트 접근 가능성

이제 크롤링을 시작해보세요! 🎉
