"""Test the database connection and verify all tables exist."""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
url = os.getenv("DATABASE_URL")
print("Connecting to DB...")
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
tables = [row[0] for row in cur.fetchall()]
print(f"Connected successfully!")
print(f"Tables found: {tables}")
cur.close()
conn.close()
