#!/usr/bin/env python3
"""
Advanced stream URL detection for VOB 92.9 FM
Tries multiple methods to find the actual streaming URL
"""

import requests
import re
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, urlparse
import subprocess
import time

class RadioStreamFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def find_vob_stream(self):
        """Try multiple methods to find VOB 92.9 FM stream URL"""
        
        print("🔍 Searching for VOB 92.9 FM stream URL...")
        
        # Method 1: Parse the main page
        stream_url = self.parse_starcom_page()
        if stream_url:
            return stream_url
            
        # Method 2: Try common stream URL patterns
        stream_url = self.try_common_patterns()
        if stream_url:
            return stream_url
            
        # Method 3: Network inspection approach
        stream_url = self.inspect_network_requests()
        if stream_url:
            return stream_url
            
        print("❌ Could not find direct stream URL")
        return None
        
    def parse_starcom_page(self):
        """Parse the VOB 92.9 page for stream URLs"""
        try:
            print("📄 Parsing Starcom Network webpage...")
            url = "https://starcomnetwork.net/radio-stations/stream-vob-92-9-fm/"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for audio/stream URLs in various places
            patterns = [
                r'https?://[^"\s]+\.(?:mp3|m3u8|aac|ogg)',
                r'https?://[^"\s]*stream[^"\s]*',
                r'https?://[^"\s]*radio[^"\s]*',
                r'https?://[^"\s]*vob[^"\s]*'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                for match in matches:
                    if self.test_stream_url(match):
                        print(f"✅ Found working stream: {match}")
                        return match
                        
            # Look in script tags for player configurations
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    for pattern in patterns:
                        matches = re.findall(pattern, script.string, re.IGNORECASE)
                        for match in matches:
                            if self.test_stream_url(match):
                                print(f"✅ Found working stream in script: {match}")
                                return match
                                
        except Exception as e:
            print(f"❌ Error parsing webpage: {e}")
            
        return None
        
    def try_common_patterns(self):
        """Try common radio streaming URL patterns"""
        print("🎯 Trying common streaming patterns...")
        
        base_patterns = [
            "https://stream.starcomnetwork.net/vob929",
            "https://live.starcomnetwork.net/vob929",
            "https://radio.starcomnetwork.net/vob929",
            "http://stream.starcomnetwork.net:8000/vob929",
            "http://live.starcomnetwork.net:8000/vob929",
            "https://stream.starcomnetwork.net/vob929.mp3",
            "https://stream.starcomnetwork.net/vob929.m3u8",
            "https://live.starcomnetwork.net/vob929.mp3",
            "https://icecast.starcomnetwork.net/vob929",
            "https://shoutcast.starcomnetwork.net/vob929"
        ]
        
        for url in base_patterns:
            print(f"🔍 Testing: {url}")
            if self.test_stream_url(url):
                print(f"✅ Found working stream: {url}")
                return url
                
        return None
        
    def test_stream_url(self, url):
        """Test if a URL is a valid audio stream"""
        try:
            # Quick HEAD request to check headers
            response = self.session.head(url, timeout=10, allow_redirects=True)
            
            content_type = response.headers.get('content-type', '').lower()
            
            # Check for audio content types
            audio_types = ['audio/', 'application/ogg', 'video/mp2t']
            if any(audio_type in content_type for audio_type in audio_types):
                return True
                
            # Check for streaming indicators
            streaming_indicators = ['icy-', 'shoutcast', 'icecast']
            for header, value in response.headers.items():
                if any(indicator in header.lower() or indicator in str(value).lower() 
                       for indicator in streaming_indicators):
                    return True
                    
        except Exception as e:
            print(f"❌ Failed to test {url}: {e}")
            
        return False
        
    def inspect_network_requests(self):
        """Use browser automation to inspect network requests"""
        print("🌐 Attempting network inspection...")
        
        # This would require selenium/playwright for full browser automation
        # For now, return None - we can implement this if needed
        print("ℹ️  Network inspection requires browser automation (not implemented)")
        return None
        
    def get_stream_info(self, url):
        """Get detailed information about a stream"""
        try:
            print(f"\n📊 Analyzing stream: {url}")
            
            # Test with FFmpeg
            cmd = [
                'ffmpeg', '-i', url, '-t', '5', '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                print("✅ FFmpeg can process this stream")
                return True
            else:
                print(f"❌ FFmpeg error: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Stream analysis failed: {e}")
            return False

def main():
    finder = RadioStreamFinder()
    
    print("🎵 VOB 92.9 FM Stream Finder")
    print("=" * 40)
    
    stream_url = finder.find_vob_stream()
    
    if stream_url:
        print(f"\n🎉 SUCCESS! Found stream URL:")
        print(f"📻 {stream_url}")
        
        # Test with FFmpeg
        print(f"\n🔧 Testing with FFmpeg...")
        if finder.get_stream_info(stream_url):
            print(f"\n✅ Stream is ready for use!")
            print(f"\nTo use in your .env file:")
            print(f"RADIO_STREAM_URL={stream_url}")
            print(f"# Comment out AUDIO_INPUT_DEVICE to use stream")
        else:
            print(f"\n⚠️  Stream found but may have compatibility issues")
    else:
        print(f"\n❌ Could not find a working stream URL")
        print(f"\nAlternatives:")
        print(f"1. Contact Starcom Network for direct stream URL")
        print(f"2. Use browser developer tools to inspect network requests")
        print(f"3. Continue with Stereo Mix as fallback")

if __name__ == "__main__":
    main()

