#!/usr/bin/env python3
"""
Quick script to fix the program_key values in program_digests table for 2025-11-17
"""
from sqlalchemy import create_engine, text
import os

# Azure SQL connection string (using SQLAlchemy format)
server = 'echobot-sql-server-v3.database.windows.net'
database = 'echobot-db'
username = 'echobotadmin'
password = 'EchoBot2025!'

# SQLAlchemy connection string format
connection_string = f'mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no'

print("Connecting to Azure SQL Database...")
engine = create_engine(connection_string)
conn = engine.connect()

# Show current state
print("\n=== BEFORE FIX ===")
result = conn.execute(text("SELECT id, show_date, program_key, program_name FROM program_digests WHERE show_date = '2025-11-17'"))
rows = result.fetchall()
for row in rows:
    print(f"ID: {row[0]}, Date: {row[1]}, Key: '{row[2]}', Name: {row[3]}")

# Fix VOB Brass Tacks
print("\n=== FIXING VOB BRASS TACKS ===")
result = conn.execute(text("""
    UPDATE program_digests 
    SET program_key = 'VOB_BRASS_TACKS' 
    WHERE program_key = 'down_to_brass_tacks' AND show_date = '2025-11-17'
"""))
affected = result.rowcount
print(f"Updated {affected} row(s) for VOB Brass Tacks")

# Fix CBC Let's Talk
print("\n=== FIXING CBC LET'S TALK ===")
result = conn.execute(text("""
    UPDATE program_digests 
    SET program_key = 'CBC_LETS_TALK' 
    WHERE program_key = 'let''s_talk_about_it' AND show_date = '2025-11-17'
"""))
affected = result.rowcount
print(f"Updated {affected} row(s) for CBC Let's Talk")

# Commit changes
conn.commit()

# Show final state
print("\n=== AFTER FIX ===")
result = conn.execute(text("SELECT id, show_date, program_key, program_name FROM program_digests WHERE show_date = '2025-11-17'"))
rows = result.fetchall()
for row in rows:
    print(f"ID: {row[0]}, Date: {row[1]}, Key: '{row[2]}', Name: {row[3]}")

conn.close()
print("\n✅ Database keys fixed successfully!")
print("\nNow you can trigger the email send with:")
print('curl -X POST "https://echobot-docker-app.azurewebsites.net/api/send-digest-email" -H "Content-Type: application/x-www-form-urlencoded" -d "date=2025-11-17"')
