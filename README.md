Refill Spot 크롤러 (1단계 MVP - PostGIS 버전)
다이닝코드에서 무한리필 가게 정보를 수집하는 Python 크롤링 프로그램입니다.
기존 프로젝트의 PostGIS 기반 스키마와 완전 호환됩니다.
🚀 빠른 시작

1. 자동 설정 (추천)
   bash# 실행 권한 부여 후 자동 설정
   chmod +x setup.sh
   ./setup.sh
2. 수동 설정
   bash# Python 3.12 가상환경 생성
   python3 -m venv venv
   source venv/bin/activate # Windows: venv\Scripts\activate

# 의존성 설치

pip install -r requirements.txt

# Docker로 PostGIS 지원 PostgreSQL 시작

docker-compose up -d postgres

# 환경변수 설정

cp .env.example .env

# .env 파일 수정 (기본값으로도 동작함)

3. 환경 테스트
   bash# 전체 환경 검증
   python test_connection.py

# 데이터베이스만 테스트

python main.py db 4. 크롤링 실행
bash# 단일 가게 테스트
python main.py test

# 전체 MVP 크롤링 실행

python main.py full

# 또는

python main.py
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
python# 테스트 지역 (강남구)
TEST_RECT = "37.4979,127.0276,37.5279,127.0576"

# 검색 키워드

KEYWORDS = ["무한리필", "고기무한리필", "초밥뷔페", ...]

# 크롤링 지연 (IP 차단 방지)

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

이제 크롤링을 시작해보세요! 🎉# Refill Spot 크롤러 (1단계 MVP)
다이닝코드에서 무한리필 가게 정보를 수집하는 Python 크롤링 프로그램입니다.
🚀 빠른 시작

1. 자동 설정 (추천)
   bash# 실행 권한 부여 후 자동 설정
   chmod +x setup.sh
   ./setup.sh
2. 수동 설정
   bash# Python 3.12 가상환경 생성
   python3 -m venv venv
   source venv/bin/activate # Windows: venv\Scripts\activate

# 의존성 설치

pip install -r requirements.txt

# Docker로 PostgreSQL 시작

docker-compose up -d postgres

# 환경변수 설정

cp .env.example .env

# .env 파일 수정 (기본값으로도 동작함)

3. ChromeDriver 설치
   macOS (Homebrew):
   bashbrew install chromedriver
   Ubuntu/Debian:
   bashsudo apt-get install chromium-chromedriver
   Windows:

ChromeDriver 다운로드
PATH에 추가하거나 프로젝트 폴더에 배치

4. 실행
   bash# 데이터베이스 연결 테스트
   python -c "from database import DatabaseManager; db = DatabaseManager(); db.test_connection(); db.close()"

# 단일 가게 테스트

python main.py test

# 전체 MVP 크롤링 실행

python main.py
🐳 Docker 관리
bash# PostgreSQL 시작
docker-compose up -d postgres

# pgAdmin 시작 (웹 관리도구)

docker-compose up -d pgadmin

# 접속: http://localhost:5050

# 이메일: admin@example.com, 비밀번호: admin123

# 모든 서비스 종료

docker-compose down

# 데이터까지 완전 삭제

docker-compose down -v
📁 파일 구조
refill-spot-crawler/
├── requirements.txt # Python 3.12 호환 의존성
├── config.py # 설정 파일 (Docker 환경)
├── crawler.py # 크롤링 로직
├── database.py # PostgreSQL 전용 처리
├── main.py # 메인 실행 스크립트
├── docker-compose.yml # PostgreSQL + pgAdmin
├── init.sql # 데이터베이스 초기 스키마
├── setup.sh # 자동 설정 스크립트
├── .env.example # 환경변수 예시
└── README.md # 이 파일
🔧 환경설정
.env 파일 (Docker 기본값)
bashDB_HOST=localhost
DB_PORT=5432
DB_NAME=refill_spot
DB_USER=postgres
DB_PASSWORD=password123
config.py 주요 설정

TEST_RECT: 테스트용 강남구 좌표 범위
KEYWORDS: 검색 키워드 목록
MIN_DELAY, MAX_DELAY: 크롤링 지연 시간 (3-5초)

📊 데이터베이스 스키마
stores 테이블 (메인)

diningcode_place_id: 다이닝코드 가게 ID (유니크 키)
name: 가게 이름
address: 주소
position_lat, position_lng: 위도, 경도
phone_number: 전화번호
diningcode_rating: 다이닝코드 평점
raw_categories_diningcode: 원본 카테고리 태그 배열
status: 운영 상태 ('운영중', '휴업', '폐업')

categories 테이블

기본 카테고리들이 자동으로 삽입됨 (무한리필, 한식, 중식 등)

store_categories 테이블

가게와 카테고리 다대다 연결

🎯 크롤링 결과
bash# 결과 파일들
mvp_crawling_result.csv # 크롤링된 데이터 CSV
crawler.log # 크롤링 로그
refill_spot_crawler.log # 메인 프로세스 로그
🐛 트러블슈팅
Docker PostgreSQL 연결 오류
bash# 컨테이너 상태 확인
docker-compose ps

# 로그 확인

docker-compose logs postgres

# 포트 충돌 시 (5432 포트가 이미 사용중)

docker-compose down
sudo service postgresql stop # 기존 PostgreSQL 중지
docker-compose up -d postgres
ChromeDriver 오류
bash# Chrome과 ChromeDriver 버전 확인
google-chrome --version
chromedriver --version

# 버전이 맞지 않으면 ChromeDriver 업데이트

Python 3.12 호환성

모든 패키지가 Python 3.12와 호환되도록 버전 조정됨
특별한 추가 설정 불필요

📝 로그 확인
bash# 실시간 로그 확인
tail -f refill_spot_crawler.log

# Docker 로그

docker-compose logs -f postgres
🎯 다음 단계 (2단계)

더 많은 지역 추가: 서울 전체, 부산, 대구 등
상세 정보 강화: 메뉴, 가격, 영업시간 파싱 추가
성능 최적화: 병렬 처리, 배치 크기 조정
모니터링: 크롤링 성공률, 데이터 품질 검증

⚠️ 주의사항

Python 3.12 사용: 최신 버전 호환성 확보
Docker 환경: Supabase 대신 로컬 PostgreSQL 사용
robots.txt 준수: 3-5초 지연으로 과도한 요청 방지
개인정보 보호: 수집된 데이터 적절한 관리
