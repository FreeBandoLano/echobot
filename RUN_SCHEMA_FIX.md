# Fix Leaked Schema in Digests (Oct 26 & 28)

## Step 1: SSH into Azure Container

```bash
az webapp ssh --name echobot-docker-app --resource-group echobot-rg
```

## Step 2: Once connected, run these commands

```bash
cd /app

# Create the fix script
cat > fix_leaked_schema_digests.py << 'EOFSCRIPT'
#!/usr/bin/env python3
"""Fix leaked schema in digests for October 26 and October 28, 2025."""

import sys
import os
from datetime import date

sys.path.insert(0, '/app')

required_vars = ['OPENAI_API_KEY']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"\n❌ ERROR: Missing required environment variables: {missing_vars}")
    sys.exit(1)

from database import db
from summarization import summarizer

def fix_digest(target_date):
    print(f"\n{'='*70}")
    print(f"FIXING DIGEST FOR {target_date}")
    print(f"{'='*70}")
    
    print(f"\n📊 Database: {'Azure SQL' if db.use_azure_sql else 'SQLite'}")
    
    # Check for existing digest
    existing_digest = db.get_daily_digest(target_date)
    
    if existing_digest:
        digest_id = existing_digest.get('id')
        print(f"   Found digest ID: {digest_id}")
        print(f"   Length: {len(existing_digest.get('digest_text', ''))} chars")
        
        # Delete corrupted digest
        print(f"\n🗑️  Deleting corrupted digest...")
        conn = db.get_connection()
        conn.execute("DELETE FROM daily_digests WHERE id = ?", (digest_id,))
        conn.commit()
        conn.close()
        print(f"   ✅ Deleted")
    else:
        print(f"   No existing digest found")
    
    # Check blocks
    blocks = db.get_blocks_by_date(target_date)
    completed_blocks = [b for b in blocks if b.get('status') == 'completed']
    
    print(f"\n📋 Blocks: {len(completed_blocks)} completed")
    
    if not completed_blocks:
        print(f"❌ No completed blocks")
        return False
    
    # Generate new digest
    print(f"\n🔄 Generating clean digest...")
    digest_text = summarizer.create_daily_digest(target_date)
    
    if digest_text:
        print(f"✅ Digest created: {len(digest_text)} characters")
        
        # Check for schema leakage
        if '"metadata"' in digest_text[:500]:
            print(f"⚠️  WARNING: Schema still detected!")
            return False
        else:
            print(f"✅ No schema leakage detected")
        return True
    else:
        print(f"❌ Failed to create digest")
        return False

def main():
    print("\n" + "="*70)
    print("FIX LEAKED SCHEMA IN DIGESTS")
    print("="*70)
    
    dates_to_fix = [
        date(2025, 10, 26),
        date(2025, 10, 28),
    ]
    
    results = {}
    for target_date in dates_to_fix:
        results[target_date] = fix_digest(target_date)
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    
    for target_date, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"   {target_date}: {status}")
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
EOFSCRIPT

# Make it executable
chmod +x fix_leaked_schema_digests.py

# Run the fix
python3 fix_leaked_schema_digests.py

# Exit SSH
exit
```

## What this does:

1. **Deletes** the corrupted digests for Oct 26 & Oct 28 from Azure SQL
2. **Regenerates** clean digests for both dates
3. **Verifies** no schema leakage in the new digests

## Expected Output:

You should see:
- ✅ Database: Azure SQL
- ✅ Digest deleted for each date
- ✅ Clean digest generated
- ✅ No schema leakage detected
- ✅ SUCCESS for both dates
