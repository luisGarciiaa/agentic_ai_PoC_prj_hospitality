#!/usr/bin/env python3
"""Script to load booking data and hotel metadata into PostgreSQL database."""

import os
import json
import pandas as pd
import psycopg2
from psycopg2 import OperationalError, DatabaseError

HOTELS_JSON_PATH = "/app/data/hotels/hotels.json"  # ajusta si tu ruta es distinta


def check_table_exists(cursor, table_name):
    """Check if a table exists in the database."""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]


def execute_sql_file(cursor, file_path):
    """Execute SQL commands from a file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        sql_commands = file.read()
        cursor.execute(sql_commands)


# ==== NUEVO: helpers para cargar hotels.json ====

def load_hotels_json():
    """Load and parse hotels.json."""
    if not os.path.exists(HOTELS_JSON_PATH):
        raise FileNotFoundError(f"hotels.json not found at {HOTELS_JSON_PATH}")

    with open(HOTELS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    hotels = data.get("Hotels", [])
    return hotels


def upsert_hotels_and_rooms(cursor, hotels):
    """
    Insert or update hotels and rooms from JSON into PostgreSQL.
    Usa ON CONFLICT para que sea idempotente.
    """
    # Opcional: limpiar tablas antes (si quieres recargar siempre desde cero)
    # cursor.execute("TRUNCATE TABLE rooms RESTART IDENTITY CASCADE;")
    # cursor.execute("TRUNCATE TABLE hotels RESTART IDENTITY CASCADE;")

    for h in hotels:
        hotel_key = h.get("hotelkey")
        name = h.get("Name")
        address = h.get("Address", {}) or {}

        country = address.get("Country")
        city = address.get("City")
        zip_code = address.get("ZipCode")
        addr_text = address.get("Address")

        # Insertar hotel
        cursor.execute("""
            INSERT INTO hotels (hotel_key, hotel_name, country, city, zip_code, address)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (hotel_key) DO UPDATE
            SET hotel_name = EXCLUDED.hotel_name,
                country    = EXCLUDED.country,
                city       = EXCLUDED.city,
                zip_code   = EXCLUDED.zip_code,
                address    = EXCLUDED.address;
        """, (hotel_key, name, country, city, zip_code, addr_text))

        # Insertar habitaciones
        rooms = h.get("Rooms", []) or []
        for r in rooms:
            room_id = r.get("RoomId")
            floor = r.get("Floor")
            category = r.get("Category")   # Standard / Premium
            rtype = r.get("Type")          # Single / Double / Triple
            guests = r.get("Guests")
            price_off = r.get("PriceOffSeason")
            price_peak = r.get("PricePeakSeason")

            cursor.execute("""
                INSERT INTO rooms (
                    hotel_key, room_id, floor, room_category, room_type,
                    guests, price_off_season, price_peak_season
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (hotel_key, room_id) DO UPDATE
                SET floor             = EXCLUDED.floor,
                    room_category     = EXCLUDED.room_category,
                    room_type         = EXCLUDED.room_type,
                    guests            = EXCLUDED.guests,
                    price_off_season  = EXCLUDED.price_off_season,
                    price_peak_season = EXCLUDED.price_peak_season;
            """, (
                hotel_key, room_id, floor, category, rtype,
                guests, price_off, price_peak
            ))


# ==== FIN NUEVO ====


def load_excel_to_postgres():
    """Load booking data from Excel file into PostgreSQL database."""
    conn = None
    try:
        # Connect to PostgreSQL using environment variables
        conn = psycopg2.connect(
            host="bookings-db",
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )

        # Create a cursor
        cursor = conn.cursor()

        # 1) Crear tablas si no existen (bookings + hotels + rooms)
        if not check_table_exists(cursor, 'bookings'):
            print("Table 'bookings' does not exist. Creating it (and related tables)...")
            execute_sql_file(cursor, '/app/db/init.sql')
            conn.commit()

        # 2) Cargar hotels.json -> tablas hotels y rooms
        print("Loading hotels.json into 'hotels' and 'rooms' tables...")
        hotels = load_hotels_json()
        upsert_hotels_and_rooms(cursor, hotels)
        conn.commit()
        print("Hotel metadata loaded successfully.")

        # 3) Cargar all_bookings.xlsx -> tabla bookings (igual que antes)
        print("Loading all_bookings.xlsx into 'bookings' table...")
        excel_file = "/app/data/all_bookings.xlsx"
        df = pd.read_excel(excel_file)

        # Convert date columns to datetime
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'])
        df['Check-out Date'] = pd.to_datetime(df['Check-out Date'])
        
        # Calculate total nights
        df['Total Nights'] = (df['Check-out Date'] - df['Check-in Date']).dt.days

        # Opcional: limpiar bookings antes para evitar duplicados
        # cursor.execute("TRUNCATE TABLE bookings RESTART IDENTITY;")

        # Insert data into the database
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO bookings (
                    hotel_name, room_id, room_type, room_category,
                    check_in_date, check_out_date, total_nights, guest_first_name,
                    guest_last_name, guest_email, guest_phone,
                    guest_country, guest_city, guest_address,
                    guest_zip_code, meal_plan, total_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['Hotel Name'], row['Room ID'], row['Room Type'],
                row['Room Category'], row['Check-in Date'], row['Check-out Date'],
                row['Total Nights'], row['Guest First Name'], row['Guest Last Name'], row['Guest Email'],
                row['Guest Phone'], row['Guest Country'], row['Guest City'],
                row['Guest Address'], row['Guest Zip Code'], row['Meal Plan'],
                row['Total Price']
            ))

        # Commit the transaction
        conn.commit()
        print("Data loaded successfully into the database.")

    except (OperationalError, DatabaseError, FileNotFoundError, ValueError) as error:
        print(f"Error while connecting to PostgreSQL: {error}")
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("PostgreSQL connection is closed.")


if __name__ == "__main__":
    load_excel_to_postgres()
