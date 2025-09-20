# Use Python 3.11 slim image
FROM python:3.11-slim

# Build arguments (must come after FROM)
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown

# Install system dependencies including ODBC drivers
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unixodbc \
    unixodbc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 17 using direct download (bypasses repository issues)
RUN curl -fsSL https://packages.microsoft.com/debian/12/prod/pool/main/m/msodbcsql17/msodbcsql17_17.10.6.1-1_amd64.deb -o msodbcsql17.deb \
    && ACCEPT_EULA=Y dpkg -i msodbcsql17.deb || true \
    && apt-get install -f -y \
    && rm -f msodbcsql17.deb

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