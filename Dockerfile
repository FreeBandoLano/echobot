FROM python:3.11-slim

# Build arguments (must come after FROM)
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown

# Install FFmpeg using the system package manager
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose build metadata inside container
ENV GIT_COMMIT_SHA=${GIT_COMMIT} \
	BUILD_TIME=${BUILD_TIME}

LABEL org.opencontainers.image.revision=${GIT_COMMIT} \
	  org.opencontainers.image.created=${BUILD_TIME} \
	  org.opencontainers.image.source="https://example.com/echobot"

# Expose the port Gunicorn will run on
EXPOSE 8000

# Define the command to run your app with increased timeout
CMD ["sh", "-c", "gunicorn -w 2 -k uvicorn.workers.UvicornWorker --timeout 600 --bind 0.0.0.0:${PORT:-8000} web_app:app"]