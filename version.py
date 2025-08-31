"""Build/version metadata injected at build time (lightweight)."""

# These defaults can be overridden at build time by passing --build-arg GIT_COMMIT
# and setting an environment variable, but we also hard-code the current short
# commit for traceability when running outside Docker.

COMMIT = "5758c7b"  # updated manually; Docker image will expose GIT_COMMIT env
BUILD_TIME = "2025-08-31T00:00:00Z"  # update if needed; optional
