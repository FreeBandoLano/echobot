FROM python:3.11-slim

# Build arguments (must come after FROM)
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown

# Install system dependencies including FFmpeg and ODBC driver for Azure SQL
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    gnupg \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose build metadata inside container
ENV GIT_COMMIT_SHA=${GIT_COMMIT} \
	BUILD_TIME=${BUILD_TIME} \
	TZ=America/Barbados

LABEL org.opencontainers.image.revision=${GIT_COMMIT} \
	  org.opencontainers.image.created=${BUILD_TIME} \
	  org.opencontainers.image.source="https://example.com/echobot"

# Expose the port the application will run on
EXPOSE 8000

# Define the command to run the full system (automation + web dashboard)
CMD ["python", "main.py", "run"]