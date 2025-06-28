-- 간단한 크롤러 데이터베이스 초기화

-- PostGIS 확장 활성화
CREATE EXTENSION IF NOT EXISTS postgis;

-- 카테고리 테이블
CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 가게 테이블 (단순화)
CREATE TABLE IF NOT EXISTS stores (
  id SERIAL PRIMARY KEY,
  diningcode_place_id VARCHAR(50) UNIQUE,
  name VARCHAR(200) NOT NULL,
  address TEXT,
  description TEXT,
  
  -- 위치 정보
  position_lat DECIMAL(10, 8),
  position_lng DECIMAL(11, 8),
  position_x DECIMAL(15, 6),
  position_y DECIMAL(15, 6),
  
  -- 평점 정보
  naver_rating DECIMAL(3, 2),
  kakao_rating DECIMAL(3, 2),
  diningcode_rating DECIMAL(3, 2),
  
  -- 영업시간 정보
  open_hours TEXT,
  open_hours_raw TEXT,
  break_time TEXT,
  holiday TEXT,
  
  -- 가격 정보
  price TEXT,
  price_range TEXT,
  average_price TEXT,
  price_details TEXT[],
  
  -- 무한리필 정보
  refill_items TEXT[],
  refill_type TEXT,
  refill_conditions TEXT,
  
  -- 이미지 정보
  image_urls TEXT[],
  main_image TEXT,
  menu_images TEXT[],
  interior_images TEXT[],
  
  -- 메뉴 정보
  menu_items JSONB,
  keywords TEXT[],
  atmosphere TEXT,
  
  -- 연락처 정보
  phone_number VARCHAR(20),
  website TEXT,
  
  -- 기타
  raw_categories_diningcode TEXT[],
  status VARCHAR(20) DEFAULT '운영중',
  
  -- 타임스탬프
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 가게-카테고리 연결 테이블
CREATE TABLE IF NOT EXISTS store_categories (
  store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
  category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (store_id, category_id)
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_stores_name ON stores(name);
CREATE INDEX IF NOT EXISTS idx_stores_status ON stores(status);
CREATE INDEX IF NOT EXISTS idx_stores_position ON stores(position_lat, position_lng);

-- 기본 카테고리 데이터 삽입
INSERT INTO categories (name) VALUES 
('무한리필'), ('고기'), ('뷔페'), ('일식'), ('중식'), ('양식'), 
('피자'), ('치킨'), ('한식'), ('해산물')
ON CONFLICT (name) DO NOTHING; 