#!/usr/bin/env python3
"""
Quick test script to verify CBC Q100.7 FM stream accessibility.
"""

import requests
import time
from pathlib import Path

CBC_STREAM_URL = "http://108.178.16.190:8000/1007fm.mp3"
TEST_DURATION = 5  # seconds

def test_stream():
    """Test if the CBC stream is accessible and returning audio data."""
    
    print(f"Testing CBC Q100.7 FM stream...")
    print(f"URL: {CBC_STREAM_URL}")
    print(f"Duration: {TEST_DURATION} seconds")
    print("-" * 60)
    
    try:
        # Test stream connectivity
        print("1. Testing connectivity...")
        response = requests.get(CBC_STREAM_URL, stream=True, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Stream returned status code: {response.status_code}")
            return False
        
        print(f"✓ Stream accessible (status: {response.status_code})")
        
        # Check content type
        content_type = response.headers.get('content-type', 'unknown')
        print(f"✓ Content-Type: {content_type}")
        
        # Test downloading data
        print(f"\n2. Testing data download ({TEST_DURATION} seconds)...")
        start_time = time.time()
        bytes_received = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                bytes_received += len(chunk)
                elapsed = time.time() - start_time
                if elapsed >= TEST_DURATION:
                    break
        
        elapsed = time.time() - start_time
        kbps = (bytes_received * 8 / 1000) / elapsed if elapsed > 0 else 0
        
        print(f"✓ Received {bytes_received:,} bytes in {elapsed:.1f}s")
        print(f"✓ Average bitrate: {kbps:.1f} kbps")
        
        # Validate we got reasonable data
        if bytes_received < 1000:
            print(f"⚠ Warning: Very little data received ({bytes_received} bytes)")
            print("  Stream may not be active or may be experiencing issues")
            return False
        
        print(f"\n{'='*60}")
        print("✅ Stream test PASSED - CBC Q100.7 FM is accessible!")
        print(f"{'='*60}")
        return True
        
    except requests.exceptions.Timeout:
        print(f"❌ Timeout connecting to stream")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Run stream test."""
    success = test_stream()
    
    if success:
        print("\nStream is ready for integration!")
        print("You can proceed with recording blocks E and F.")
    else:
        print("\n⚠ Stream test failed!")
        print("Please verify:")
        print("  1. The stream URL is correct")
        print("  2. The stream is currently broadcasting")
        print("  3. Your network connection allows access to the stream")
        print("  4. Try accessing the stream in a web browser or media player")

if __name__ == "__main__":
    main()


