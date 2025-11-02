"""Version information for RadioSynopsis."""

__version__ = "0.1.0-beta"
__version_info__ = (0, 1, 0, "beta")
__author__ = "RadioSynopsis Contributors"
__license__ = "MIT"
__description__ = "Open-source radio stream analysis with AI transcription and summarization"

# Release information
RELEASE_DATE = "2025-08-29"
RELEASE_NAME = "Initial Open Source Release"
GITHUB_URL = "https://github.com/FreeBandoLano/echobot"
DOCUMENTATION_URL = f"{GITHUB_URL}/blob/main/README.md"
ISSUES_URL = f"{GITHUB_URL}/issues"

def get_version_string():
    """Return formatted version string."""
    return f"RadioSynopsis v{__version__} ({RELEASE_DATE})"

def print_version_info():
    """Print detailed version information."""
    print(f"RadioSynopsis {__version__}")
    print(f"Release: {RELEASE_NAME}")
    print(f"Date: {RELEASE_DATE}")
    print(f"License: {__license__}")
    print(f"Project: {GITHUB_URL}")
