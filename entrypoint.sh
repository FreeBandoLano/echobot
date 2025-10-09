#!/bin/sh
set -e

# Start SSH service
service ssh start

# Start the application using uvicorn (since you're using FastAPI)
exec uvicorn main:app --host 0.0.0.0 --port 8000
