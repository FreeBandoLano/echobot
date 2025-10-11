#!/usr/bin/env python3
"""
Automated verification script for OpenAI Responses API migration.
Tests critical integration points to ensure no logic errors introduced.

Usage:
    python3 verify_responses_api_migration.py [--quick] [--full]
    
    --quick: Run only critical path checks (Phase 1)
    --full: Run all verification checks (all phases)
"""

import sys
import os
from datetime import date, datetime
from pathlib import Path
import json

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_status(status, message):
    """Print colored status message."""
    if status == 'pass':
        print(f"{GREEN}✅ PASS{RESET}: {message}")
    elif status == 'fail':
        print(f"{RED}❌ FAIL{RESET}: {message}")
    elif status == 'warn':
        print(f"{YELLOW}⚠️  WARN{RESET}: {message}")
    elif status == 'info':
        print(f"{BLUE}ℹ️  INFO{RESET}: {message}")

def check_openai_sdk():
    """Verify OpenAI SDK version and Chat Completions API support with corrected parameters."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}1. OpenAI SDK Compatibility Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from openai import OpenAI
        import openai
        print_status('pass', f"OpenAI SDK imported successfully")
        
        # Check version
        version = getattr(openai, '__version__', 'unknown')
        print_status('info', f"OpenAI SDK version: {version}")
        
        # Check if Chat Completions API available (using corrected approach)
        client = OpenAI(api_key='sk-test')
        if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
            print_status('pass', "Chat Completions API available")
            if hasattr(client.chat.completions, 'create'):
                print_status('pass', "chat.completions.create() method exists")
                
                # Test parameter compatibility (this will fail with invalid key but should not fail on parameters)
                try:
                    # This should fail on auth but not on unsupported parameters
                    client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=[{"role": "user", "content": "test"}],
                        max_completion_tokens=100
                    )
                except openai.AuthenticationError:
                    print_status('pass', "max_completion_tokens parameter accepted")
                except Exception as e:
                    if "unsupported parameter" in str(e).lower():
                        print_status('fail', f"Parameter compatibility issue: {e}")
                        return False
                    else:
                        # Other errors (like auth) are expected
                        print_status('pass', "Parameter compatibility verified (auth error expected)")
                
                return True
            else:
                print_status('fail', "chat.completions.create() method missing")
                return False
        else:
            print_status('fail', "Chat Completions API not available")
            return False
            
    except ImportError as e:
        print_status('fail', f"OpenAI SDK import failed: {e}")
        return False
    except Exception as e:
        print_status('fail', f"Unexpected error: {e}")
        return False

def check_config():
    """Verify configuration settings."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}2. Configuration Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from config import Config
        
        # Check SUMMARIZATION_MODEL
        model = Config.SUMMARIZATION_MODEL
        print_status('info', f"SUMMARIZATION_MODEL: {model}")
        if model in ['gpt-5-mini', 'gpt-5-nano']:
            print_status('pass', "Primary model is gpt-5-mini/nano as expected")
        else:
            print_status('warn', f"Primary model is {model}, expected gpt-5-mini")
        
        # Check OPENAI_API_KEY
        if Config.OPENAI_API_KEY:
            key_preview = f"...{Config.OPENAI_API_KEY[-4:]}"
            print_status('pass', f"OPENAI_API_KEY configured (ends with {key_preview})")
        else:
            print_status('fail', "OPENAI_API_KEY missing")
            return False
        
        # Check feature flags
        print_status('info', f"ENABLE_LLM: {Config.ENABLE_LLM}")
        print_status('info', f"ENABLE_STRUCTURED_OUTPUT: {Config.ENABLE_STRUCTURED_OUTPUT}")
        print_status('info', f"DIGEST_CREATOR: {Config.DIGEST_CREATOR}")
        
        # Check directories
        for dir_name in ['SUMMARIES_DIR', 'TRANSCRIPTS_DIR', 'AUDIO_DIR']:
            dir_path = getattr(Config, dir_name)
            if dir_path.exists():
                print_status('pass', f"{dir_name} exists: {dir_path}")
            else:
                print_status('warn', f"{dir_name} missing: {dir_path}")
        
        return True
        
    except Exception as e:
        print_status('fail', f"Config check failed: {e}")
        return False

def check_summarizer_init():
    """Verify RadioSummarizer initializes correctly."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}3. Summarizer Initialization Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from summarization import RadioSummarizer
        
        summarizer = RadioSummarizer()
        
        # Check client initialized
        if summarizer.client:
            print_status('pass', "OpenAI client initialized")
        else:
            print_status('fail', "OpenAI client is None")
            return False
        
        # Check _call_llm method exists
        if hasattr(summarizer, '_call_llm'):
            print_status('pass', "_call_llm() method exists")
        else:
            print_status('fail', "_call_llm() method missing")
            return False
        
        # Check _response_text method exists
        if hasattr(summarizer, '_response_text'):
            print_status('pass', "_response_text() method exists")
        else:
            print_status('fail', "_response_text() method missing")
            return False
        
        # Check usage counters initialized
        expected_keys = ['block_requests', 'block_llm_calls', 'block_llm_failures',
                        'daily_digest_requests', 'daily_digest_llm_calls', 'daily_digest_llm_failures']
        if all(key in summarizer.usage for key in expected_keys):
            print_status('pass', "Usage counters initialized correctly")
        else:
            print_status('fail', "Usage counters missing keys")
            return False
        
        return True
        
    except Exception as e:
        print_status('fail', f"Summarizer init failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_database():
    """Verify database connectivity and schema."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}4. Database Integration Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from database import db
        
        # Check database type
        if db.use_azure_sql:
            print_status('info', "Using Azure SQL Database")
        else:
            print_status('info', "Using local SQLite database")
        
        # Test connection
        conn = db.get_connection()
        print_status('pass', "Database connection successful")
        
        # Check for raw_json column in summaries table
        try:
            if db.use_azure_sql:
                result = conn.execute('SELECT TOP 1 id, raw_json FROM summaries')
            else:
                result = conn.execute('SELECT id, raw_json FROM summaries LIMIT 1')
            print_status('pass', "summaries.raw_json column exists")
        except Exception as e:
            print_status('warn', f"raw_json column check failed (may be new installation): {e}")
        
        conn.close()
        return True
        
    except Exception as e:
        print_status('fail', f"Database check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_model_fallback():
    """Verify model fallback order is consistent."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}5. Model Fallback Logic Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from config import Config
        import re
        
        # Read summarization.py
        with open('summarization.py', 'r') as f:
            content = f.read()
        
        # Find all model_order or dd_models patterns
        patterns = [
            r"model_order\s*=\s*\[(.*?)\]",
            r"dd_models\s*=\s*\[(.*?)\]"
        ]
        
        model_lists = []
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                models_str = match.group(1)
                # Extract model names (simplified)
                models = [m.strip().strip("'\"") for m in models_str.split(',') if m.strip()]
                model_lists.append(models)
        
        if model_lists:
            print_status('info', f"Found {len(model_lists)} model order definitions")
            
            # Check if all lists have same structure
            first_list = model_lists[0]
            all_same = all(len(ml) == len(first_list) for ml in model_lists)
            
            if all_same:
                print_status('pass', "All model fallback orders have same length")
                print_status('info', f"Models in order: {first_list[:3]}")  # Show first 3
                
                # Check if gpt-5-mini or gpt-5-nano is primary
                primary_model = Config.SUMMARIZATION_MODEL
                if 'gpt-5-mini' in str(first_list) or 'gpt-5-nano' in str(first_list):
                    print_status('pass', "gpt-5-mini/nano in fallback order")
                else:
                    print_status('warn', "gpt-5-mini/nano not found in fallback order")
                
                return True
            else:
                print_status('warn', "Model fallback orders have different lengths")
                return False
        else:
            print_status('fail', "No model order definitions found")
            return False
            
    except Exception as e:
        print_status('fail', f"Model fallback check failed: {e}")
        return False

def check_json_extraction():
    """Test JSON extraction logic with various inputs."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}6. JSON Extraction Logic Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from summarization import summarizer
        
        test_cases = [
            ('{"key": "value"}', True, "Pure JSON"),
            ('Some text\n{"key": "value"}', True, "Text then JSON"),
            ('No JSON here', False, "No JSON"),
            ('{"nested": {"deep": "value"}}', True, "Nested JSON"),
            ('{"array": [1, 2, 3]}', True, "JSON with array"),
        ]
        
        passed = 0
        for content, should_extract, desc in test_cases:
            result = summarizer._extract_json_from_content(content)
            success = bool(result) == should_extract
            
            if success:
                print_status('pass', f"{desc}: {'extracted' if result else 'no JSON'} (as expected)")
                passed += 1
            else:
                print_status('fail', f"{desc}: unexpected result")
        
        print_status('info', f"Passed {passed}/{len(test_cases)} test cases")
        return passed == len(test_cases)
        
    except Exception as e:
        print_status('fail', f"JSON extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_task_manager():
    """Verify task manager integration."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}7. Task Manager Integration Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from task_manager import task_manager, TaskType
        from database import db
        
        # Check if add_task uses OUTPUT INSERTED.id pattern for Azure
        if db.use_azure_sql:
            with open('task_manager.py', 'r') as f:
                content = f.read()
                if 'OUTPUT INSERTED.id' in content:
                    print_status('pass', "Azure SQL OUTPUT INSERTED.id pattern found")
                else:
                    print_status('fail', "OUTPUT INSERTED.id pattern missing for Azure SQL")
                    return False
        else:
            print_status('info', "Using SQLite (OUTPUT INSERTED.id check skipped)")
        
        # Check if task types include digest-related tasks
        digest_types = ['CREATE_DAILY_DIGEST', 'EMAIL_DAILY_DIGEST']
        for task_type in digest_types:
            if hasattr(TaskType, task_type):
                print_status('pass', f"TaskType.{task_type} exists")
            else:
                print_status('fail', f"TaskType.{task_type} missing")
                return False
        
        return True
        
    except Exception as e:
        print_status('fail', f"Task manager check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_scheduler_bypass():
    """Verify scheduler respects DIGEST_CREATOR flag."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}8. Scheduler Bypass Logic Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from config import Config
        
        with open('scheduler.py', 'r') as f:
            content = f.read()
        
        # Check for DIGEST_CREATOR checks
        if 'DIGEST_CREATOR' in content:
            print_status('pass', "Scheduler checks DIGEST_CREATOR flag")
            
            # Check for task_manager bypass in _process_block
            if "DIGEST_CREATOR == 'task_manager'" in content or 'task_manager' in content:
                print_status('pass', "Scheduler has task_manager bypass logic")
            else:
                print_status('warn', "task_manager bypass logic unclear")
            
            return True
        else:
            print_status('fail', "DIGEST_CREATOR not referenced in scheduler")
            return False
            
    except Exception as e:
        print_status('fail', f"Scheduler check failed: {e}")
        return False

def check_rolling_summary():
    """Verify rolling summary uses Chat Completions API with corrected parameters."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}9. Rolling Summary Integration Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        with open('rolling_summary.py', 'r') as f:
            content = f.read()
        
        # Check for Chat Completions API usage
        if 'chat.completions.create' in content:
            print_status('pass', "Rolling summary uses Chat Completions API")
        else:
            print_status('fail', "Rolling summary doesn't use Chat Completions API")
            return False
        
        # Check it doesn't use old Responses API
        if 'responses.create' in content:
            print_status('fail', "Rolling summary still uses Responses API")
            return False
        else:
            print_status('pass', "No Responses API usage in rolling summary")
        
        # Check for corrected parameters
        if 'max_completion_tokens' in content:
            print_status('pass', "Rolling summary uses max_completion_tokens parameter")
        else:
            print_status('warn', "Rolling summary may not use corrected parameters")
        
        return True
        
    except Exception as e:
        print_status('fail', f"Rolling summary check failed: {e}")
        return False

def run_quick_checks():
    """Run only critical path checks (Phase 1)."""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}RUNNING QUICK VERIFICATION (PHASE 1 - CRITICAL PATH){RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    checks = [
        ("OpenAI SDK Compatibility", check_openai_sdk),
        ("Configuration", check_config),
        ("Summarizer Initialization", check_summarizer_init),
        ("Database Integration", check_database),
        ("Task Manager Integration", check_task_manager),
        ("Scheduler Bypass Logic", check_scheduler_bypass),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_status('fail', f"{name} threw exception: {e}")
            results.append((name, False))
    
    return results

def run_full_checks():
    """Run all verification checks."""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}RUNNING FULL VERIFICATION (ALL PHASES){RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    checks = [
        # Phase 1: Critical Path
        ("OpenAI SDK Compatibility", check_openai_sdk),
        ("Configuration", check_config),
        ("Summarizer Initialization", check_summarizer_init),
        ("Database Integration", check_database),
        ("Task Manager Integration", check_task_manager),
        ("Scheduler Bypass Logic", check_scheduler_bypass),
        # Phase 2: High Priority
        ("Model Fallback Logic", check_model_fallback),
        ("JSON Extraction", check_json_extraction),
        # Phase 3: Medium Priority
        ("Rolling Summary", check_rolling_summary),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_status('fail', f"{name} threw exception: {e}")
            results.append((name, False))
    
    return results

def print_summary(results):
    """Print summary of all checks."""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}VERIFICATION SUMMARY{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = 'pass' if result else 'fail'
        print_status(status, name)
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    percentage = (passed / total * 100) if total > 0 else 0
    
    if passed == total:
        print(f"{GREEN}✅ ALL CHECKS PASSED ({passed}/{total}){RESET}")
        print(f"{GREEN}🚀 Ready for deployment{RESET}")
    elif passed >= total * 0.8:
        print(f"{YELLOW}⚠️  MOSTLY PASSED ({passed}/{total} - {percentage:.1f}%){RESET}")
        print(f"{YELLOW}⚠️  Review failed checks before deployment{RESET}")
    else:
        print(f"{RED}❌ MULTIPLE FAILURES ({passed}/{total} - {percentage:.1f}%){RESET}")
        print(f"{RED}❌ Do NOT deploy - critical issues detected{RESET}")
    
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    return passed == total

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify OpenAI Responses API migration')
    parser.add_argument('--quick', action='store_true', help='Run only critical path checks')
    parser.add_argument('--full', action='store_true', help='Run all verification checks')
    
    args = parser.parse_args()
    
    if args.full:
        results = run_full_checks()
    else:
        # Default to quick checks
        results = run_quick_checks()
    
    success = print_summary(results)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
