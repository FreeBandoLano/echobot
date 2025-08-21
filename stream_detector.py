"""Stream URL detector for VOB 92.9 FM from Starcom Network."""

import requests
import re
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)

def detect_vob_stream_url():
    """Detect the actual streaming URL for VOB 92.9 FM."""
    
    starcom_url = "https://starcomnetwork.net/radio-stations/stream-vob-92-9-fm/"
    
    try:
        # Get the webpage content
        response = requests.get(starcom_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        html_content = response.text
        
        # Common patterns for streaming URLs
        patterns = [
            r'["\']([^"\']*\.m3u8[^"\']*)["\']',  # HLS streams
            r'["\']([^"\']*stream[^"\']*\.mp3[^"\']*)["\']',  # MP3 streams
            r'["\']([^"\']*icecast[^"\']*)["\']',  # Icecast streams
            r'["\']([^"\']*shoutcast[^"\']*)["\']',  # Shoutcast streams
            r'src=["\']([^"\']*audio[^"\']*)["\']',  # Audio src attributes
            r'url:\s*["\']([^"\']*stream[^"\']*)["\']',  # JavaScript URL properties
        ]
        
        found_urls = []
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                # Convert relative URLs to absolute
                if match.startswith('//'):
                    match = 'https:' + match
                elif match.startswith('/'):
                    match = urljoin(starcom_url, match)
                elif not match.startswith('http'):
                    continue
                
                # Filter for likely audio streams
                if any(indicator in match.lower() for indicator in [
                    'stream', 'audio', 'radio', 'live', 'm3u8', 'mp3', 'aac'
                ]):
                    found_urls.append(match)
        
        # Remove duplicates and sort by likelihood
        unique_urls = list(set(found_urls))
        
        # Prioritize certain stream types
        priority_urls = []
        regular_urls = []
        
        for url in unique_urls:
            if any(high_priority in url.lower() for high_priority in ['.m3u8', 'vob', '929']):
                priority_urls.append(url)
            else:
                regular_urls.append(url)
        
        all_urls = priority_urls + regular_urls
        
        logger.info(f"Found {len(all_urls)} potential stream URLs")
        for i, url in enumerate(all_urls):
            logger.info(f"  {i+1}. {url}")
        
        return all_urls
        
    except Exception as e:
        logger.error(f"Error detecting stream URL: {e}")
        return []

def test_stream_url(url):
    """Test if a stream URL is accessible."""
    
    try:
        logger.info(f"Testing stream URL: {url}")
        
        response = requests.head(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Check if it's an audio stream
        if any(audio_type in content_type for audio_type in [
            'audio', 'application/vnd.apple.mpegurl', 'application/x-mpegurl'
        ]):
            logger.info(f"✓ Valid audio stream: {url} (Content-Type: {content_type})")
            return True
        else:
            logger.warning(f"⚠ Not an audio stream: {url} (Content-Type: {content_type})")
            return False
            
    except Exception as e:
        logger.warning(f"✗ Stream test failed: {url} - {e}")
        return False

def find_working_vob_stream():
    """Find a working stream URL for VOB 92.9 FM."""
    
    logger.info("Detecting VOB 92.9 FM stream URLs...")
    
    # First try to detect from the webpage
    detected_urls = detect_vob_stream_url()
    
    # Add some common Barbados radio stream URLs as fallbacks
    fallback_urls = [
        "https://stream.starcomnetwork.net/vob929",
        "https://stream.starcomnetwork.net/vob",
        "https://live.starcomnetwork.net/vob929.m3u8",
        "https://live.starcomnetwork.net/vob.m3u8",
        "http://stream.starcomnetwork.net:8000/vob929",
        "http://stream.starcomnetwork.net:8000/vob",
    ]
    
    all_test_urls = detected_urls + fallback_urls
    
    # Test each URL
    working_urls = []
    for url in all_test_urls:
        if test_stream_url(url):
            working_urls.append(url)
    
    if working_urls:
        logger.info(f"Found {len(working_urls)} working stream URLs")
        return working_urls[0]  # Return the first working URL
    else:
        logger.error("No working stream URLs found")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("VOB 92.9 FM Stream Detector")
    print("=" * 40)
    
    stream_url = find_working_vob_stream()
    
    if stream_url:
        print(f"\n✓ Working stream URL found: {stream_url}")
        print("\nYou can use this URL in your .env file:")
        print(f"RADIO_STREAM_URL={stream_url}")
    else:
        print("\n✗ No working stream URL found")
        print("\nYou may need to:")
        print("1. Check if the stream is currently live")
        print("2. Contact Starcom Network for the correct stream URL")
        print("3. Use local audio recording instead")
