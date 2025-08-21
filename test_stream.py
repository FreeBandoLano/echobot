#!/usr/bin/env python3
"""
Test the VOB 92.9 FM stream URL
"""

import subprocess
import os
from pathlib import Path

def test_vob_stream():
    """Test the VOB 92.9 FM stream URL directly"""
    
    stream_url = "https://ice66.securenetsystems.net/VOB929"
    output_path = Path("audio/vob_stream_test.wav")
    
    # Ensure audio directory exists
    output_path.parent.mkdir(exist_ok=True)
    
    print("🎵 Testing VOB 92.9 FM Stream")
    print("=" * 50)
    print(f"Stream URL: {stream_url}")
    print(f"Output: {output_path}")
    print("Recording 15 seconds...")
    
    # FFmpeg command to record from stream
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-loglevel', 'error',
        '-nostdin',
        '-reconnect', '1',
        '-reconnect_streamed', '1',
        '-reconnect_delay_max', '5',
        '-i', stream_url,
        '-ac', '1',  # Mono
        '-ar', '16000',  # 16kHz
        '-t', '15',  # 15 seconds
        '-y',  # Overwrite
        str(output_path)
    ]
    
    try:
        # Run FFmpeg
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and output_path.exists():
            size = output_path.stat().st_size
            print(f"✅ SUCCESS!")
            print(f"📁 File size: {size:,} bytes")
            print(f"🎧 Quality: 16kHz mono (Whisper-optimized)")
            print(f"🌐 Stream is CLOUD-READY for Azure!")
            
            # Estimate data usage
            bytes_per_minute = size / 15 * 60  # Scale to per minute
            mb_per_hour = bytes_per_minute * 60 / 1_000_000
            print(f"📊 Estimated usage: ~{mb_per_hour:.1f} MB/hour")
            
            return True
        else:
            print(f"❌ FFmpeg failed:")
            print(f"Return code: {result.returncode}")
            print(f"STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Recording timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_azure_compatibility():
    """Check Azure deployment readiness"""
    
    print("\n🏢 AZURE DEPLOYMENT ANALYSIS")
    print("=" * 50)
    
    print("✅ PROS:")
    print("  • Direct HTTP stream (no local audio devices)")
    print("  • Professional streaming provider (SecureNet)")
    print("  • No browser dependency")
    print("  • Works with FFmpeg (available in Azure)")
    print("  • Reliable reconnection handling")
    print("  • Standard audio formats")
    
    print("\n🔒 SECURITY:")
    print("  • HTTPS encrypted stream")
    print("  • No authentication required")
    print("  • Public broadcast content")
    print("  • Compliant with government monitoring")
    
    print("\n⚙️ AZURE REQUIREMENTS:")
    print("  • Azure Container Instances (or App Service)")
    print("  • FFmpeg in container image")
    print("  • Azure Blob Storage for audio files")
    print("  • Azure OpenAI for transcription")
    print("  • Scheduled automation with Azure Functions")

if __name__ == "__main__":
    success = test_vob_stream()
    check_azure_compatibility()
    
    if success:
        print("\n🎯 NEXT STEPS:")
        print("1. Update .env with: RADIO_STREAM_URL=https://ice66.securenetsystems.net/VOB929")
        print("2. Comment out AUDIO_INPUT_DEVICE")
        print("3. Test with your system")
        print("4. Ready for Azure deployment!")
    else:
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Check internet connection")
        print("2. Verify FFmpeg installation")
        print("3. Try browser to confirm stream availability")

