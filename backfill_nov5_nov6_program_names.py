#!/usr/bin/env python3
"""Backfill program_name for Nov 5 and Nov 6, 2025 blocks."""

from datetime import date
from database import db
from sqlalchemy import text

def backfill_program_names():
    """Set program_name based on block_code for Nov 5-6, 2025."""
    
    dates = [date(2025, 11, 5), date(2025, 11, 6)]
    
    for target_date in dates:
        print(f"\n📅 Processing {target_date}...")
        
        # Get blocks for this date
        blocks = db.get_blocks_by_date(target_date)
        print(f"Found {len(blocks)} blocks")
        
        if not blocks:
            print(f"  No blocks found for {target_date}")
            continue
        
        # Update program_name based on block_code
        with db.get_connection() as conn:
            for block in blocks:
                block_code = block['block_code']
                current_program = block.get('program_name')
                
                # Determine correct program name
                if block_code in ['A', 'B', 'C', 'D']:
                    correct_program = 'Down to Brass Tacks'
                elif block_code in ['E', 'F']:
                    correct_program = "Let's Talk About It"
                else:
                    print(f"  ⚠️ Unknown block code: {block_code}")
                    continue
                
                if current_program == correct_program:
                    print(f"  ✓ Block {block_code}: Already set to '{correct_program}'")
                else:
                    # Update the program_name
                    if db.use_azure_sql:
                        update_query = text("UPDATE blocks SET program_name = :program_name WHERE id = :block_id")
                        conn.execute(update_query, {"program_name": correct_program, "block_id": block['id']})
                    else:
                        conn.execute("UPDATE blocks SET program_name = ? WHERE id = ?", 
                                   (correct_program, block['id']))
                    print(f"  ✅ Block {block_code}: Updated from '{current_program}' to '{correct_program}'")
            
            conn.commit()
        
        # Verify
        blocks_after = db.get_blocks_by_date(target_date)
        vob_blocks = [b for b in blocks_after if b.get('program_name') == 'Down to Brass Tacks']
        cbc_blocks = [b for b in blocks_after if b.get('program_name') == "Let's Talk About It"]
        
        print(f"\n  Verification for {target_date}:")
        print(f"    VOB (Down to Brass Tacks): {len(vob_blocks)} blocks {[b['block_code'] for b in vob_blocks]}")
        print(f"    CBC (Let's Talk About It): {len(cbc_blocks)} blocks {[b['block_code'] for b in cbc_blocks]}")

if __name__ == '__main__':
    print("🔧 Backfilling program_name for Nov 5-6, 2025")
    backfill_program_names()
    print("\n✅ Backfill complete!")
