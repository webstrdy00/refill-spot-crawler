# 크롤링 데이터 마이그레이션 가이드

## 개요

크롤링한 데이터를 프로젝트 DB로 마이그레이션하는 방법을 설명합니다.

## 왜 데이터 가공이 필요한가?

### 1. 스키마 차이

- **크롤러 DB**: 더 많은 필드, PostGIS 지원, JSONB 타입 사용
- **프로젝트 DB**: Prisma ORM 기반, 더 단순한 구조

### 2. 데이터 품질

- 크롤링 데이터는 불완전하거나 중복될 수 있음
- 무한리필 여부 검증 필요
- 이미지 URL 유효성 확인 필요

### 3. 카테고리 매핑

- 크롤러의 상세 카테고리를 프로젝트의 일반 카테고리로 매핑 필요

## 마이그레이션 프로세스

### 1단계: 데이터 검증

```bash
cd refill-spot-crawler
python src/utils/data_validator.py
```

검증 항목:

- 필수 필드 누락 확인
- 위치 정보 유효성
- 중복 데이터 확인
- 무한리필 정보 확인

### 2단계: 환경변수 설정

```bash
# .env 파일 생성
touch .env
```

```env
# 크롤링 DB (기존 설정 유지)
DATABASE_URL=postgresql://postgres:12345@localhost:5432/refill_spot_crawler

# 메인 프로젝트 DB (Supabase 또는 PostgreSQL)
PROJECT_DATABASE_URL=postgresql://postgres:your_password@localhost:5432/refill_spot
# 또는 Supabase의 경우:
# PROJECT_DATABASE_URL=postgresql://postgres:your_supabase_password@db.your-project.supabase.co:5432/postgres
```

### 3단계: 데이터 마이그레이션

```bash
# 테스트 마이그레이션 (10개만)
python src/utils/data_migration.py --test

# 제한된 마이그레이션 (100개)
python src/utils/data_migration.py --limit 100

# 전체 마이그레이션
python src/utils/data_migration.py

# 커스텀 DB URL 사용 (선택사항)
python src/utils/data_migration.py \
  --crawler-db "postgresql://user:pass@host:port/db" \
  --project-db "postgresql://user:pass@host:port/db" \
  --test
```

## 데이터 가공 내용

### 1. 가격 정보

- 우선순위: `price` > `average_price` > `price_range`
- 숫자 형식으로 변환

### 2. 무한리필 아이템

- `refill_items` 필드 사용
- `refill_type`에서 추가 정보 추출
- 메뉴에서 무한리필 관련 아이템 검색

### 3. 이미지 URL

- 유효한 URL만 필터링
- 중복 제거
- 최대 5개까지 저장

### 4. 영업시간

- `open_hours` 우선 사용
- 브레이크타임, 라스트오더, 휴무일 정보 통합

### 5. 설명 생성

- 기본 설명 + 무한리필 정보 + 분위기 + 키워드 조합
- 최대 500자

### 6. 카테고리 매핑

```
크롤러 카테고리 → 프로젝트 카테고리
- 고기무한리필, 삼겹살무한리필 → 고기
- 초밥뷔페 → 일식
- 해산물무한리필 → 해산물
등...
```

## 주의사항

1. **중복 확인**: 이미 프로젝트 DB에 있는 데이터와 중복되지 않도록 확인
2. **트랜잭션**: 대량 데이터 처리 시 트랜잭션 관리 필요
3. **로깅**: 마이그레이션 과정 로깅으로 문제 추적
4. **백업**: 마이그레이션 전 프로젝트 DB 백업 권장

## 마이그레이션 후 확인

```sql
-- 프로젝트 DB에서 확인
SELECT COUNT(*) FROM stores;
SELECT * FROM stores LIMIT 10;

-- 카테고리 연결 확인
SELECT s.name, array_agg(c.name) as categories
FROM stores s
JOIN store_categories sc ON s.id = sc.store_id
JOIN categories c ON sc.category_id = c.id
GROUP BY s.id, s.name
LIMIT 10;
```

## 문제 해결

### 연결 오류

- DB 호스트, 포트, 사용자명, 비밀번호 확인
- PostgreSQL 서비스 실행 확인

### 데이터 타입 오류

- Prisma 스키마와 실제 DB 스키마 일치 확인
- 배열 타입 처리 확인

### 성능 문제

- 배치 크기 조정 (기본 100개)
- 인덱스 확인
- 트랜잭션 크기 조정
