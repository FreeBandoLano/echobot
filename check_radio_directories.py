#!/usr/bin/env python3
"""
Check various radio directories for VOB 92.9 FM
"""

import requests
import json

def check_radio_garden():
    """Check Radio Garden for VOB 92.9"""
    print("🌍 Checking Radio Garden...")
    try:
        # Search for Barbados stations
        search_url = "http://radio.garden/api/ara/content/places"
        response = requests.get(search_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Radio Garden API accessible")
            # This would need more specific search implementation
            return None
        else:
            print(f"❌ Radio Garden API error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Radio Garden error: {e}")
        return None

def check_manual_sources():
    """Check known Caribbean radio stream sources"""
    print("🏝️ Checking Caribbean radio sources...")
    
    # Known Caribbean radio aggregators
    potential_sources = [
        "http://192.99.8.192:3134/stream",  # Example Caribbean stream
        "http://s2.voscast.com:8124/stream",  # Another example
        # These are examples - real URLs would need to be researched
    ]
    
    print("ℹ️  Manual research needed for Caribbean radio directories")
    return None

def suggest_professional_solutions():
    """Suggest professional radio monitoring solutions"""
    
    print("\n" + "="*60)
    print("🏢 PROFESSIONAL RADIO MONITORING SOLUTIONS")
    print("="*60)
    
    print("\n1. 📻 Hardware Solutions:")
    print("   • RTL-SDR USB dongle (~$25)")
    print("   • Can receive FM radio directly")
    print("   • Software: SDR# or GQRX")
    print("   • Perfect for government monitoring")
    
    print("\n2. 🎧 Virtual Audio Cable:")
    print("   • VB-Audio Virtual Cable (free)")
    print("   • More reliable than Stereo Mix")
    print("   • Routes browser audio to your app")
    
    print("\n3. 🌐 Streaming Aggregators:")
    print("   • Radio-Locator.com")
    print("   • Radio-Electronics.com")
    print("   • LiveOnlineRadio.net")
    
    print("\n4. 💼 Enterprise Solutions:")
    print("   • RadioLabs monitoring software")
    print("   • Critical Mention (broadcast monitoring)")
    print("   • TVEyes (broadcast transcription)")

def main():
    print("🎵 VOB 92.9 FM Alternative Source Checker")
    print("=" * 50)
    
    check_radio_garden()
    check_manual_sources()
    suggest_professional_solutions()
    
    print("\n📋 RECOMMENDED APPROACH:")
    print("1. ✅ Use browser dev tools FIRST (most likely to work)")
    print("2. 📞 Contact Starcom Network (official government request)")  
    print("3. 🎧 Set up Virtual Audio Cable (more reliable than Stereo Mix)")
    print("4. 📻 Consider RTL-SDR for direct FM reception (most robust)")

if __name__ == "__main__":
    main()

