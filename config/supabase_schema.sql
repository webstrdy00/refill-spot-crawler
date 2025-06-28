-- Refill Spot Supabase Database Schema
-- 생성일: 2024년
-- 설명: 리필스팟 프로젝트의 전체 데이터베이스 스키마 정의

-- PostGIS 확장 활성화 (공간 데이터 처리용)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. 카테고리 테이블
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- 2. 사용자 프로필 테이블 (Supabase Auth와 연동)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    is_admin BOOLEAN DEFAULT false,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 매장 테이블 (메인 비즈니스 테이블)
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    description TEXT,
    position_lat DOUBLE PRECISION NOT NULL,
    position_lng DOUBLE PRECISION NOT NULL,
    position_x DOUBLE PRECISION NOT NULL,
    position_y DOUBLE PRECISION NOT NULL,
    naver_rating DOUBLE PRECISION,
    kakao_rating DOUBLE PRECISION,
    open_hours TEXT,
    price TEXT,
    refill_items TEXT[],
    image_urls TEXT[],
    geom GEOMETRY(POINT, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 매장-카테고리 연결 테이블 (다대다 관계)
CREATE TABLE IF NOT EXISTS store_categories (
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (store_id, category_id)
);

-- 5. 즐겨찾기 테이블
CREATE TABLE IF NOT EXISTS favorites (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, store_id)
);

-- 6. 리뷰 테이블
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    rating DOUBLE PRECISION NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. 고객 문의 테이블
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    store_name TEXT,
    store_address TEXT,
    message TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_stores_geom ON stores USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_stores_position ON stores (position_lat, position_lng);
CREATE INDEX IF NOT EXISTS idx_stores_name ON stores (name);
CREATE INDEX IF NOT EXISTS idx_reviews_store_id ON reviews (store_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites (user_id);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts (status);
CREATE INDEX IF NOT EXISTS idx_stores_created_at ON stores (created_at);

-- RLS (Row Level Security) 정책 설정
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

-- 프로필 정책
CREATE POLICY "Users can view own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

-- 즐겨찾기 정책
CREATE POLICY "Users can manage own favorites" ON favorites FOR ALL USING (auth.uid() = user_id);

-- 리뷰 정책
CREATE POLICY "Anyone can view reviews" ON reviews FOR SELECT USING (true);
CREATE POLICY "Users can create reviews" ON reviews FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own reviews" ON reviews FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own reviews" ON reviews FOR DELETE USING (auth.uid() = user_id);

-- 문의 정책
CREATE POLICY "Users can create contacts" ON contacts FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can view own contacts" ON contacts FOR SELECT USING (auth.uid()::text = email);

-- 매장 테이블은 공개 읽기
CREATE POLICY "Anyone can view stores" ON stores FOR SELECT USING (true);
CREATE POLICY "Anyone can view categories" ON categories FOR SELECT USING (true);
CREATE POLICY "Anyone can view store_categories" ON store_categories FOR SELECT USING (true);

-- 트리거 함수: updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 적용
CREATE TRIGGER update_stores_updated_at BEFORE UPDATE ON stores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reviews_updated_at BEFORE UPDATE ON reviews FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 함수: 매장 검색 (전문 검색)
CREATE OR REPLACE FUNCTION search_stores(search_term TEXT)
RETURNS TABLE (
    id INTEGER,
    name TEXT,
    address TEXT,
    description TEXT,
    position_lat DOUBLE PRECISION,
    position_lng DOUBLE PRECISION,
    naver_rating DOUBLE PRECISION,
    kakao_rating DOUBLE PRECISION,
    price TEXT,
    refill_items TEXT[],
    image_urls TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id, s.name, s.address, s.description,
        s.position_lat, s.position_lng,
        s.naver_rating, s.kakao_rating,
        s.price, s.refill_items, s.image_urls
    FROM stores s
    WHERE 
        s.name ILIKE '%' || search_term || '%' OR
        s.address ILIKE '%' || search_term || '%' OR
        s.description ILIKE '%' || search_term || '%'
    ORDER BY s.name;
END;
$$ LANGUAGE plpgsql;

-- 함수: 거리 기반 매장 검색
CREATE OR REPLACE FUNCTION search_stores_by_distance(
    user_lat DOUBLE PRECISION,
    user_lng DOUBLE PRECISION,
    radius_km DOUBLE PRECISION DEFAULT 5.0
)
RETURNS TABLE (
    id INTEGER,
    name TEXT,
    address TEXT,
    distance_km DOUBLE PRECISION,
    position_lat DOUBLE PRECISION,
    position_lng DOUBLE PRECISION,
    naver_rating DOUBLE PRECISION,
    kakao_rating DOUBLE PRECISION,
    price TEXT,
    refill_items TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id, s.name, s.address,
        ST_Distance(
            ST_GeogFromText('POINT(' || user_lng || ' ' || user_lat || ')'),
            ST_GeogFromText('POINT(' || s.position_lng || ' ' || s.position_lat || ')')
        ) / 1000 AS distance_km,
        s.position_lat, s.position_lng,
        s.naver_rating, s.kakao_rating,
        s.price, s.refill_items
    FROM stores s
    WHERE ST_DWithin(
        ST_GeogFromText('POINT(' || user_lng || ' ' || user_lat || ')'),
        ST_GeogFromText('POINT(' || s.position_lng || ' ' || s.position_lat || ')'),
        radius_km * 1000
    )
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql; 