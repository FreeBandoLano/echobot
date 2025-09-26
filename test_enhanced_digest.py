#!/usr/bin/env python3
"""Test script for enhanced digest generation with new structured format."""

from summarization import summarizer
from database import db
from datetime import date
import json

def test_enhanced_digest_generation():
    """Test the enhanced digest with simulated data."""
    print("🧪 Testing Enhanced Digest Generation")
    print("=" * 50)
    
    # Create test date
    test_date = date(2025, 9, 24)
    
    # Create mock block summaries for testing
    mock_blocks = [
        {
            'block_code': 'A',
            'block_name': 'Morning Block',
            'summary': 'Economic sovereignty concerns dominated with caller Mr. Alexander highlighting Sagicor share buyout issues. Strong sentiment against predatory financial practices.',
            'key_points': [
                'Barbados Stock Trading Company LLC offering 29% discount on Sagicor shares',
                'Fears of eroding Barbadian ownership in key sectors',
                'Calls for stronger minority shareholder protections'
            ],
            'entities': ['Sagicor Financial Corporation', 'Barbados Stock Trading Company LLC', 'Mr. Alexander'],
            'caller_count': 12
        },
        {
            'block_code': 'B', 
            'block_name': 'News Summary Block',
            'summary': 'Sports governance and disaster preparedness discussions. Debate over Sports Council restructuring and Hurricane Janet anniversary reflections.',
            'key_points': [
                'Sports Council potential dismantling causing staff anxiety',
                'Dr. Dalmarie Armstrong\'s claims vs official clarifications',
                'Hurricane Janet anniversary calls for better disaster prep'
            ],
            'entities': ['Sports Council', 'Dr. Dalmarie Armstrong', 'Hurricane Janet'],
            'caller_count': 8
        }
    ]
    
    # Test the internal digest generation function
    try:
        digest = summarizer._generate_enhanced_daily_digest(
            test_date, 
            mock_blocks, 
            20,  # total callers
            ['Sagicor', 'Sports Council', 'Hurricane Janet']
        )
        
        if digest:
            print("✅ Enhanced digest generated successfully!")
            print(f"📏 Length: {len(digest)} characters")
            
            # Check for new structured format markers
            structure_checks = [
                ("Preamble section", "## PREAMBLE" in digest),
                ("Topics Overview section", "## TOPICS OVERVIEW" in digest),
                ("Structured themes", "### 1." in digest),
                ("Policy Implications subsection", "**Policy Implications**" in digest),
                ("Notable Exchanges subsection", "**Notable Exchanges**" in digest),
                ("Key Quotes subsection", "**Key Quotes**" in digest),
            ]
            
            print("\n🔍 Structure Analysis:")
            for check_name, result in structure_checks:
                status = "✅" if result else "❌"
                print(f"   {status} {check_name}")
            
            # Show preview of topics section
            if "## TOPICS OVERVIEW" in digest:
                topics_start = digest.find("## TOPICS OVERVIEW")
                topics_section = digest[topics_start:topics_start+800] + "..."
                print(f"\n📋 Topics Overview Preview:\n{topics_section}")
            
            # Save sample output
            with open('web_output/enhanced_digest_test_sample.txt', 'w', encoding='utf-8') as f:
                f.write(digest)
            print(f"\n💾 Sample saved to: web_output/enhanced_digest_test_sample.txt")
            
        else:
            print("❌ No digest generated")
            
    except Exception as e:
        print(f"❌ Error testing enhanced digest: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_enhanced_digest_generation()