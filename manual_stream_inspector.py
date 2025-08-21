#!/usr/bin/env python3
"""
Manual stream inspection for VOB 92.9 FM
Opens browser tools to help find the stream URL
"""

import requests
from bs4 import BeautifulSoup
import re
import json

def inspect_page_source():
    """Inspect the webpage source for any streaming clues"""
    
    print("🔍 Deep inspection of VOB 92.9 page source...")
    
    try:
        # Get the page
        url = "https://starcomnetwork.net/radio-stations/stream-vob-92-9-fm/"
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        print(f"✅ Page loaded successfully (Status: {response.status_code})")
        
        # Save full HTML for analysis
        with open('vob_page_source.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("💾 Page source saved to 'vob_page_source.html'")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for any audio/embed elements
        print("\n🎵 Searching for audio elements...")
        audio_elements = soup.find_all(['audio', 'source', 'embed', 'iframe'])
        for elem in audio_elements:
            print(f"Found {elem.name}: {elem.attrs}")
        
        # Look for script tags that might contain player config
        print("\n📜 Searching for player scripts...")
        scripts = soup.find_all('script')
        
        player_keywords = ['player', 'stream', 'audio', 'radio', 'mp3', 'm3u', 'shoutcast', 'icecast']
        
        for i, script in enumerate(scripts):
            if script.string:
                script_content = script.string.lower()
                if any(keyword in script_content for keyword in player_keywords):
                    print(f"\n📄 Script {i+1} (contains player keywords):")
                    print("=" * 50)
                    print(script.string[:500] + "..." if len(script.string) > 500 else script.string)
                    print("=" * 50)
        
        # Look for URLs in the page
        print("\n🔗 All URLs found in page:")
        url_pattern = r'https?://[^\s"\'\)>]+'
        urls = re.findall(url_pattern, response.text)
        
        # Filter for potentially relevant URLs
        relevant_urls = []
        for url in set(urls):  # Remove duplicates
            url_lower = url.lower()
            if any(keyword in url_lower for keyword in ['stream', 'radio', 'audio', 'mp3', 'm3u', 'play']):
                relevant_urls.append(url)
        
        if relevant_urls:
            for url in relevant_urls:
                print(f"📻 {url}")
        else:
            print("❌ No obvious streaming URLs found")
        
        # Look for data attributes
        print("\n📊 Elements with data attributes:")
        elements_with_data = soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys()))
        for elem in elements_with_data[:10]:  # Limit to first 10
            data_attrs = {k: v for k, v in elem.attrs.items() if k.startswith('data-')}
            if data_attrs:
                print(f"{elem.name}: {data_attrs}")
        
    except Exception as e:
        print(f"❌ Error inspecting page: {e}")

def suggest_manual_steps():
    """Provide instructions for manual stream discovery"""
    
    print("\n" + "="*60)
    print("🔧 MANUAL STREAM DISCOVERY GUIDE")
    print("="*60)
    
    print("\n1. 🌐 Browser Developer Tools Method:")
    print("   • Open https://starcomnetwork.net/radio-stations/stream-vob-92-9-fm/")
    print("   • Press F12 to open Developer Tools")
    print("   • Go to Network tab")
    print("   • Filter by 'Media' or 'All'")
    print("   • Click the play button on the radio player")
    print("   • Look for audio streams (usually .mp3, .m3u8, or streaming URLs)")
    
    print("\n2. 📞 Direct Contact Method:")
    print("   • Contact Starcom Network technical team")
    print("   • Ask for the direct streaming URL for VOB 92.9 FM")
    print("   • Explain it's for government monitoring purposes")
    
    print("\n3. 🔍 Alternative Stream Sources:")
    print("   • Check TuneIn Radio for VOB 92.9 FM")
    print("   • Look for other radio directory services")
    print("   • Search for 'VOB 92.9 FM stream URL' online")
    
    print("\n4. 🎧 Temporary Solutions:")
    print("   • Continue using Stereo Mix (current working method)")
    print("   • Set up virtual audio cable for more reliable routing")
    print("   • Use hardware audio capture device")
    
    print("\n5. 🚀 Professional Solutions:")
    print("   • Radio monitoring software (like RadioLabs)")
    print("   • Broadcast monitoring services")
    print("   • Hardware SDR (Software Defined Radio) receivers")

def main():
    print("🎵 VOB 92.9 FM Manual Stream Inspector")
    print("=" * 50)
    
    inspect_page_source()
    suggest_manual_steps()
    
    print("\n📋 NEXT STEPS:")
    print("1. Check 'vob_page_source.html' for any clues")
    print("2. Use browser developer tools as described above")
    print("3. Consider contacting Starcom Network directly")
    print("4. For now, Stereo Mix remains your most reliable option")

if __name__ == "__main__":
    main()

