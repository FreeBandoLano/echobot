"""Build/version metadata fallback (used only when Docker env vars unavailable).

The application prioritizes environment variables GIT_COMMIT_SHA and BUILD_TIME
that are set during Docker build via --build-arg. These values are only used
as fallbacks for local development when not running in a Docker container.

In production (Docker), version info comes from build args automatically.
"""

# Fallback values for local development (Docker will override with build args)
COMMIT = "dev-local"  # Will be overridden by GIT_COMMIT_SHA env var in Docker
BUILD_TIME = "dev-build"  # Will be overridden by BUILD_TIME env var in Docker
