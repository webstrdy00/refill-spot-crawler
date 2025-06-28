-- Simple crawler database initialization

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stores table (simplified)
CREATE TABLE IF NOT EXISTS stores (
  id SERIAL PRIMARY KEY,
  diningcode_place_id VARCHAR(50) UNIQUE,
  name VARCHAR(200) NOT NULL,
  address TEXT,
  description TEXT,
  
  -- Position info
  position_lat DECIMAL(10, 8),
  position_lng DECIMAL(11, 8),
  position_x DECIMAL(15, 6),
  position_y DECIMAL(15, 6),
  
  -- Rating info
  naver_rating DECIMAL(3, 2),
  kakao_rating DECIMAL(3, 2),
  diningcode_rating DECIMAL(3, 2),
  
  -- Hours info
  open_hours TEXT,
  open_hours_raw TEXT,
  break_time TEXT,
  holiday TEXT,
  
  -- Price info
  price TEXT,
  price_range TEXT,
  average_price TEXT,
  price_details TEXT[],
  
  -- Refill info
  refill_items TEXT[],
  refill_type TEXT,
  refill_conditions TEXT,
  
  -- Image info
  image_urls TEXT[],
  main_image TEXT,
  menu_images TEXT[],
  interior_images TEXT[],
  
  -- Menu info
  menu_items JSONB,
  keywords TEXT[],
  atmosphere TEXT,
  
  -- Contact info
  phone_number VARCHAR(20),
  website TEXT,
  
  -- Other
  raw_categories_diningcode TEXT[],
  status VARCHAR(20) DEFAULT 'open',
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store-categories junction table
CREATE TABLE IF NOT EXISTS store_categories (
  store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
  category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (store_id, category_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_stores_name ON stores(name);
CREATE INDEX IF NOT EXISTS idx_stores_status ON stores(status);
CREATE INDEX IF NOT EXISTS idx_stores_position ON stores(position_lat, position_lng);

-- Insert basic categories
INSERT INTO categories (name) VALUES 
('refill'), ('meat'), ('buffet'), ('japanese'), ('chinese'), ('western'), 
('pizza'), ('chicken'), ('korean'), ('seafood')
ON CONFLICT (name) DO NOTHING; 