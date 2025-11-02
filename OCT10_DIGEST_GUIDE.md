# Manual Digest Generation for October 10, 2025

## Quick Start

The automated digest system fix was deployed today, so October 10's digest needs to be generated manually.

### Option 1: Run the Helper Script (Easiest)

```bash
./generate_today_digest.sh
```

This will:
1. Connect you to Azure via SSH
2. Show you the commands to run
3. Generate and email today's digest

### Option 2: Manual SSH Commands

```bash
# Connect to Azure
az webapp ssh --name echobot-docker-app --resource-group echobot-rg

# Once connected, run:
cd /app
python generate_today_digest.py
```

## What It Does

The script will:
1. ✅ Check if blocks for Oct 10 are completed in Azure SQL
2. ✅ Generate the daily digest (4000-word structured summary)
3. ✅ Save to database and file system
4. ✅ Email to stakeholders:
   - delano@futurebarbados.bb
   - anya@futurebarbados.bb
   - Roy.morris@barbados.gov.bb

## Expected Output

```
╔════════════════════════════════════════════════════════════════╗
║  MANUAL DIGEST GENERATION FOR OCTOBER 10, 2025               ║
╚════════════════════════════════════════════════════════════════╝

📊 Database: Azure SQL

📋 Blocks Status:
   Total blocks: 4
   Completed blocks: 4

✅ Found 4 completed blocks:
   Block A: completed
   Block B: completed
   Block C: completed
   Block D: completed

🔄 Generating digest for 2025-10-10...
✅ Digest created successfully!
   Length: 23547 characters
   Preview: Executive Summary - October 10, 2025...

📧 Sending digest email...
✅ Email sent successfully!

📬 Recipients:
   - delano@futurebarbados.bb
   - anya@futurebarbados.bb
   - Roy.morris@barbados.gov.bb

╔════════════════════════════════════════════════════════════════╗
║  ✅ DIGEST GENERATION COMPLETE                                 ║
╚════════════════════════════════════════════════════════════════╝
```

## Troubleshooting

### "No blocks found"
- You're running locally - must run in Azure where production database is
- Use SSH to connect to Azure container

### "No completed blocks yet"
- Recording/processing still in progress
- Wait for all blocks to complete before generating digest
- Check block status in Azure logs

### "Digest already exists"
- Script will ask if you want to regenerate
- Safe to regenerate if needed

## After Oct 10

Starting October 11, the automated system will handle digest creation:
1. Recording completes → transcription task added
2. Transcription completes → summarization task added
3. All blocks complete → digest creation task added
4. Digest created → email task added
5. Email sent to stakeholders

No manual intervention needed! 🎉
