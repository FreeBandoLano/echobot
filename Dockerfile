# filepath: /workspaces/echobot/Dockerfile
# Start from the official Python base image
FROM mcr.microsoft.com/appsvc/python:3.11-slim

# Install FFmpeg using the system package manager
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 8000

# Define the command to run your app
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:${PORT:-8000}", "web_app:app"]