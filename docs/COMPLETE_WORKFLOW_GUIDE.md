# Refill Spot 크롤링부터 마이그레이션까지 완전 가이드

## 📖 목차
1. [프로젝트 구조](#프로젝트-구조)
2. [초기 설정](#초기-설정)
3. [데이터베이스 설정](#데이터베이스-설정)
4. [크롤링 실행](#크롤링-실행)
5. [데이터 마이그레이션](#데이터-마이그레이션)
6. [문제 해결](#문제-해결)

## 🏗️ 프로젝트 구조

```
refill-spot-crawler/
├── config/
│   ├── docker-compose.yml     # Docker 서비스 설정
│   ├── init.sql              # PostgreSQL 초기 스키마
│   ├── supabase_schema.sql   # Supabase 스키마
│   └── supabase_initial_data.sql
├── src/
│   ├── core/                 # 핵심 기능
│   │   ├── database.py       # 데이터베이스 연결
│   │   ├── optimized_database.py
│   │   └── data_enhancement.py
│   ├── utils/                # 유틸리티
│   │   ├── main.py          # 메인 실행 파일
│   │   ├── parallel_crawler.py
│   │   ├── seoul_scheduler.py
│   │   ├── supabase_migration.py
│   │   └── data_migration.py
│   ├── automation/           # 자동화 시스템
│   └── tests/               # 테스트 파일
├── docs/                    # 문서
└── run_crawler.py          # 간단 실행 스크립트
```

## 🚀 초기 설정

### 1. 가상환경 설정 (Windows)
```bash
# 가상환경 생성 및 활성화
setup_venv.bat

# 또는 수동으로:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Chrome WebDriver 설치
- Chrome 브라우저 최신 버전 설치
- ChromeDriver는 자동으로 관리됨 (selenium-manager)

## 🗄️ 데이터베이스 설정

### 1. Docker 컨테이너 시작
```bash
cd config
docker-compose up -d
```

### 2. 컨테이너 상태 확인
```bash
docker-compose ps
```

예상 출력:
```
NAME                  IMAGE                    STATUS
refill_spot_db        postgis/postgis:15-3.3   Up (healthy)
refill_spot_pgadmin   dpage/pgadmin4:latest    Up
refill_spot_redis     redis:7-alpine           Up
```

### 3. 데이터베이스 접속 정보
- **Host**: localhost
- **Port**: 5432
- **Database**: refill_spot
- **Username**: postgres
- **Password**: refillspot123

### 4. PgAdmin 접속 (옵션)
- URL: http://localhost:5050
- Email: admin@refillspot.com
- Password: admin123

### 5. 테이블 생성 확인 및 수정
기존 컨테이너에서 누락된 테이블이 있을 경우:

```bash
# 테이블 목록 확인
docker exec -i refill_spot_db psql -U postgres -d refill_spot -c "\dt"

# 누락된 테이블 수동 생성
docker exec -i refill_spot_db psql -U postgres -d refill_spot -c "
CREATE TABLE IF NOT EXISTS store_categories (
  store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
  category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (store_id, category_id)
);

CREATE TABLE IF NOT EXISTS crawling_logs (
  id SERIAL PRIMARY KEY,
  keyword VARCHAR(100),
  rect_area VARCHAR(200),
  stores_found INTEGER DEFAULT 0,
  stores_processed INTEGER DEFAULT 0,
  errors INTEGER DEFAULT 0,
  status VARCHAR(20) DEFAULT 'running',
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);"
```

## 🕷️ 크롤링 실행

### 1. 단계별 크롤링 실행

#### 1단계: 테스트 크롤링
```bash
python src/utils/main.py stage1
```

#### 2단계: 강남 지역 크롤링
```bash
python src/utils/main.py stage2
```

#### 3단계: 서울 주요 지역 크롤링
```bash
python src/utils/main.py stage3
```

#### 4단계: 서울 완전 커버리지
```bash
python src/utils/main.py stage4
```

#### 5단계: 전국 확장 (고급)
```bash
python src/utils/main.py stage5
```

### 2. 간단 실행 방법
```bash
python run_crawler.py
```

### 3. 크롤링 진행 상황 모니터링

#### 데이터베이스에서 확인:
```sql
-- 총 수집된 가게 수
SELECT COUNT(*) FROM stores;

-- 지역별 통계
SELECT 
  CASE 
    WHEN address LIKE '%강남%' THEN '강남'
    WHEN address LIKE '%홍대%' OR address LIKE '%마포%' THEN '홍대/마포'
    WHEN address LIKE '%강북%' THEN '강북'
    ELSE '기타'
  END as region,
  COUNT(*) as store_count
FROM stores 
GROUP BY region;

-- 크롤링 로그 확인
SELECT * FROM crawling_logs ORDER BY created_at DESC LIMIT 10;
```

#### 파이썬 스크립트로 확인:
```bash
python src/tests/check_db.py
```

### 4. 크롤링 결과 검증
```bash
# 데이터 품질 검사
python src/tests/stage5_mini_test.py

# 상세 데이터 검증
python src/utils/data_validator.py
```

## 📦 데이터 마이그레이션

### 1. Supabase로 마이그레이션

#### Supabase 프로젝트 설정:
1. [Supabase](https://supabase.com) 계정 생성
2. 새 프로젝트 생성
3. API URL과 anon key 확인

#### 환경 변수 설정:
```bash
# .env 파일 생성
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

#### 마이그레이션 실행:
```bash
# 스키마 생성
python src/utils/supabase_migration.py

# 데이터 마이그레이션
python src/utils/data_migration.py
```

### 2. 마이그레이션 검증
```bash
# 마이그레이션 결과 확인
python src/tests/test_connection.py

# 데이터 무결성 검사
python migrate_to_supabase.py
```

## 🔧 문제 해결

### 자주 발생하는 문제들

#### 1. "store_categories 테이블 누락" 오류
**해결책:**
```bash
docker exec -i refill_spot_db psql -U postgres -d refill_spot -c "
CREATE TABLE IF NOT EXISTS store_categories (
  store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
  category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (store_id, category_id)
);"
```

#### 2. Docker 컨테이너 연결 실패
**해결책:**
```bash
# 컨테이너 재시작
docker-compose down
docker-compose up -d

# 로그 확인
docker-compose logs postgres
```

#### 3. ChromeDriver 오류
**해결책:**
```bash
# Chrome 브라우저 업데이트
# 또는 수동 ChromeDriver 설치
```

#### 4. 메모리 부족 오류
**해결책:**
```python
# src/utils/main.py 에서 배치 크기 조정
BATCH_SIZE = 50  # 기본값에서 줄이기
```

#### 5. 크롤링 속도 저하
**해결책:**
```python
# 동시 실행 프로세스 수 조정
MAX_WORKERS = 3  # CPU 코어 수에 맞게 조정
```

### 성능 최적화

#### 1. 데이터베이스 인덱스 확인
```sql
-- 인덱스 목록 확인
SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public';
```

#### 2. 크롤링 병렬 처리 조정
```python
# src/utils/parallel_crawler.py
# CPU 성능에 맞게 워커 수 조정
workers = min(4, cpu_count())
```

## 📊 모니터링 및 유지보수

### 1. 시스템 상태 확인
```bash
# 전체 시스템 상태
python src/tests/stage6_test.py

# 데이터베이스 통계
python src/tests/check_db_tables.py
```

### 2. 자동화 스케줄링
```bash
# 정기 크롤링 스케줄 설정
python src/utils/seoul_scheduler.py
```

### 3. 로그 모니터링
```bash
# 크롤링 로그 확인
tail -f crawling.log

# 데이터베이스 로그 확인
docker logs refill_spot_db
```

## 🎯 추천 워크플로우

### 초기 설정 (한 번만):
1. 가상환경 설정 → Docker 실행 → 데이터베이스 확인
2. 테스트 크롤링 (stage1) 실행
3. 결과 확인 후 단계별 크롤링 진행

### 정기 업데이트:
1. stage4 실행 (서울 전체 업데이트)
2. 데이터 품질 검증
3. Supabase 마이그레이션
4. 결과 모니터링

### 문제 발생 시:
1. 로그 확인 → 원인 파악
2. 해당 구간 재크롤링
3. 데이터 검증 후 마이그레이션

이 가이드를 따라하면 크롤링부터 마이그레이션까지 전체 프로세스를 안정적으로 실행할 수 있습니다.