-- ==========================================
-- Tabla de hoteles (metadata de hotels.json)
-- ==========================================
CREATE TABLE IF NOT EXISTS hotels (
    hotel_key   VARCHAR PRIMARY KEY,      -- "hotelkey" del JSON
    hotel_name  VARCHAR(255) NOT NULL,    -- "Name"
    country     VARCHAR(100),
    city        VARCHAR(100),
    zip_code    VARCHAR(20),
    address     TEXT
);

-- ==========================================
-- Tabla de habitaciones (Rooms de cada hotel)
-- ==========================================
CREATE TABLE IF NOT EXISTS rooms (
    hotel_key         VARCHAR REFERENCES hotels(hotel_key) ON DELETE CASCADE,
    room_id           VARCHAR(50),
    floor             VARCHAR(10),
    room_category     VARCHAR(100),   -- "Category" (Standard / Premium)
    room_type         VARCHAR(100),   -- "Type" (Single / Double / Triple)
    guests            INTEGER,
    price_off_season  DECIMAL(10, 2),
    price_peak_season DECIMAL(10, 2),
    CONSTRAINT rooms_pk PRIMARY KEY (hotel_key, room_id)
);

-- ==========================================
-- Tabla de bookings (como ya tenías)
-- ==========================================
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    hotel_name VARCHAR(255),
    room_id VARCHAR(50),
    room_type VARCHAR(100),
    room_category VARCHAR(100),
    check_in_date DATE,
    check_out_date DATE,
    total_nights INTEGER,
    guest_first_name VARCHAR(100),
    guest_last_name VARCHAR(100),
    guest_email VARCHAR(255),
    guest_phone VARCHAR(50),
    guest_country VARCHAR(100),
    guest_city VARCHAR(100),
    guest_address TEXT,
    guest_zip_code VARCHAR(20),
    meal_plan VARCHAR(50),
    total_price DECIMAL(10, 2)
);
