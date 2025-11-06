#!/bin/bash
# Run this script in Azure SSH after deployment to fix Nov 5-6 data

cd /app

# Export env vars
export OPENAI_API_KEY=$(cat /proc/1/environ | tr '\0' '\n' | grep "^OPENAI_API_KEY=" | cut -d= -f2)
export AZURE_SQL_CONNECTION_STRING=$(cat /proc/1/environ | tr '\0' '\n' | grep "^SQLAZURECONNSTR_AZURE_SQL_CONNECTION_STRING=" | cut -d= -f2-)

echo "🔧 Step 1: Backfilling program_name for Nov 5-6 blocks..."
python3 << 'EOF'
from datetime import date
from database import db
from sqlalchemy import text

dates = [date(2025, 11, 5), date(2025, 11, 6)]

for target_date in dates:
    print(f"\n📅 Processing {target_date}...")
    blocks = db.get_blocks_by_date(target_date)
    print(f"Found {len(blocks)} blocks")
    
    if not blocks:
        continue
    
    with db.get_connection() as conn:
        for block in blocks:
            block_code = block['block_code']
            
            if block_code in ['A', 'B', 'C', 'D']:
                correct_program = 'Down to Brass Tacks'
            elif block_code in ['E', 'F']:
                correct_program = "Let's Talk About It"
            else:
                continue
            
            if db.use_azure_sql:
                conn.execute(text("UPDATE blocks SET program_name = :program_name WHERE id = :block_id"), 
                           {"program_name": correct_program, "block_id": block['id']})
            else:
                conn.execute("UPDATE blocks SET program_name = ? WHERE id = ?", 
                           (correct_program, block['id']))
            print(f"  ✅ Block {block_code}: Set to '{correct_program}'")
        
        conn.commit()
    
    # Verify
    blocks_after = db.get_blocks_by_date(target_date)
    vob = [b for b in blocks_after if b.get('program_name') == 'Down to Brass Tacks']
    cbc = [b for b in blocks_after if b.get('program_name') == "Let's Talk About It"]
    print(f"  Verification: VOB={len(vob)} blocks, CBC={len(cbc)} blocks")

print("\n✅ Backfill complete!")
EOF

echo ""
echo "📊 Step 2: Generating comprehensive 4000-word digests..."
python3 << 'EOF'
from datetime import date
from summarization import summarizer
from config import Config

dates = [date(2025, 11, 5), date(2025, 11, 6)]

for target_date in dates:
    print(f"\n📅 {target_date}:")
    
    for prog_key in Config.get_all_programs():
        prog_config = Config.get_program_config(prog_key)
        prog_name = prog_config['name']
        
        try:
            digest_text = summarizer.create_program_digest(target_date, prog_key)
            if digest_text:
                print(f"  ✅ {prog_name}: {len(digest_text)} chars")
            else:
                print(f"  ⚠️  {prog_name}: Not ready")
        except Exception as e:
            print(f"  ❌ {prog_name}: {e}")

print("\n✅ All digests generated!")
EOF

echo ""
echo "✅ Complete! Check the dashboard to see the digests."
