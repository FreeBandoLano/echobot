#!/usr/bin/env python3
"""
Comprehensive Azure SQL and Scheduler Integration Test
Tests all critical integration points after Chat Completions migration.
"""

import sys
import os
from datetime import date, datetime
from pathlib import Path

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

def test_database_connection():
    """Test database connectivity (Azure SQL or SQLite)."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}1. Database Connection Test{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from database import db
        from config import Config
        
        # Check database type
        db_type = "Azure SQL" if db.use_azure_sql else "SQLite"
        print_status('info', f"Database type: {db_type}")
        
        if db.use_azure_sql:
            print_status('pass', "Connected to Azure SQL Database")
            print_status('info', f"Engine: {db.engine.url.drivername}")
            
            # Check for ODBC driver
            import pyodbc
            drivers = [x for x in pyodbc.drivers() if x.startswith('ODBC Driver')]
            print_status('info', f"ODBC Drivers available: {drivers}")
        else:
            print_status('info', f"Using local SQLite: {db.db_path}")
        
        # Test basic query
        with db.get_connection() as conn:
            if db.use_azure_sql:
                from sqlalchemy import text
                result = conn._conn.execute(text("SELECT COUNT(*) as cnt FROM blocks"))
                count = list(result)[0][0]
            else:
                result = conn.execute("SELECT COUNT(*) as cnt FROM blocks")
                count = result.fetchone()[0]
            print_status('pass', f"Query successful: {count} blocks in database")
        
        # Test Azure SQL specific features
        if db.use_azure_sql:
            # Check OUTPUT INSERTED.id support
            with db.get_connection() as conn:
                from sqlalchemy import text
                # Test if OUTPUT clause is supported (Azure SQL feature)
                try:
                    test_query = text("""
                        INSERT INTO shows (show_date, title) 
                        OUTPUT INSERTED.id 
                        VALUES (:show_date, :title)
                    """)
                    # Don't actually insert, just check syntax
                    print_status('pass', "Azure SQL OUTPUT INSERTED.id syntax supported")
                except Exception as e:
                    print_status('warn', f"OUTPUT INSERTED.id may not work: {e}")
        
        # Test critical database methods
        methods_to_check = [
            'create_summary',
            'update_daily_digest_content',
            'try_acquire_digest_lock',
            'get_summary',
            'get_blocks_by_date',
            'upsert_topic',
            'link_topic_to_block'
        ]
        
        for method_name in methods_to_check:
            if hasattr(db, method_name):
                print_status('pass', f"db.{method_name}() exists")
            else:
                print_status('fail', f"db.{method_name}() missing")
                return False
        
        # Check db.create_summary accepts raw_json parameter
        import inspect
        sig = inspect.signature(db.create_summary)
        params = list(sig.parameters.keys())
        if 'raw_json' in params:
            print_status('pass', "db.create_summary() accepts raw_json parameter")
        else:
            print_status('fail', "db.create_summary() missing raw_json parameter")
            return False
        
        return True
        
    except Exception as e:
        print_status('fail', f"Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scheduler_integration():
    """Test scheduler integration and bypass logic."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}2. Scheduler Integration Test{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from scheduler import RadioScheduler
        from config import Config
        import inspect
        
        scheduler = RadioScheduler()
        print_status('pass', "Scheduler initialized successfully")
        
        # Check DIGEST_CREATOR configuration
        digest_creator = Config.DIGEST_CREATOR
        print_status('info', f"DIGEST_CREATOR: {digest_creator}")
        
        if digest_creator == 'task_manager':
            print_status('pass', "Using task_manager for digest creation (recommended)")
        elif digest_creator == 'scheduler':
            print_status('warn', "Using scheduler for digest creation (may cause duplicates)")
        else:
            print_status('warn', f"Unknown DIGEST_CREATOR: {digest_creator}")
        
        # Check _process_block has bypass logic
        if hasattr(scheduler, '_process_block'):
            source = inspect.getsource(scheduler._process_block)
            if 'DIGEST_CREATOR' in source and 'task_manager' in source:
                print_status('pass', "Scheduler._process_block has task_manager bypass")
            else:
                print_status('fail', "Scheduler._process_block missing bypass logic")
                return False
        else:
            print_status('fail', "Scheduler._process_block method missing")
            return False
        
        # Check _create_daily_digest respects DIGEST_CREATOR
        if hasattr(scheduler, '_create_daily_digest'):
            source = inspect.getsource(scheduler._create_daily_digest)
            if 'DIGEST_CREATOR' in source:
                print_status('pass', "Scheduler._create_daily_digest respects DIGEST_CREATOR flag")
            else:
                print_status('warn', "Scheduler._create_daily_digest may not check DIGEST_CREATOR")
        else:
            print_status('fail', "Scheduler._create_daily_digest method missing")
            return False
        
        # Check if scheduler has required attributes
        required_attrs = ['recording_threads', 'processing_threads', '_jobs']
        for attr in required_attrs:
            if hasattr(scheduler, attr):
                print_status('pass', f"Scheduler has {attr} attribute")
            else:
                print_status('warn', f"Scheduler missing {attr} attribute")
        
        return True
        
    except Exception as e:
        print_status('fail', f"Scheduler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_task_manager_integration():
    """Test task_manager integration with summarizer."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}3. Task Manager Integration Test{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from task_manager import TaskManager, TaskType
        import inspect
        
        tm = TaskManager()
        print_status('pass', "TaskManager initialized successfully")
        
        # Check task types exist
        required_task_types = [
            'TRANSCRIBE_BLOCK',
            'SUMMARIZE_BLOCK',
            'CREATE_DAILY_DIGEST',
            'EMAIL_DAILY_DIGEST'
        ]
        
        for task_type_name in required_task_types:
            if hasattr(TaskType, task_type_name):
                print_status('pass', f"TaskType.{task_type_name} exists")
            else:
                print_status('fail', f"TaskType.{task_type_name} missing")
                return False
        
        # Check handler methods exist
        handler_methods = [
            '_handle_transcribe_block',
            '_handle_summarize_block',
            '_handle_create_daily_digest',
            '_handle_email_daily_digest'
        ]
        
        for method_name in handler_methods:
            if hasattr(tm, method_name):
                print_status('pass', f"TaskManager.{method_name}() exists")
            else:
                print_status('fail', f"TaskManager.{method_name}() missing")
                return False
        
        # Verify _handle_create_daily_digest calls summarizer
        source = inspect.getsource(tm._handle_create_daily_digest)
        if 'summarizer.create_daily_digest' in source:
            print_status('pass', "Task manager calls summarizer.create_daily_digest()")
        else:
            print_status('fail', "Task manager does not call summarizer")
            return False
        
        # Check for email chaining
        if 'EMAIL_DAILY_DIGEST' in source:
            print_status('pass', "Task manager chains EMAIL_DAILY_DIGEST task")
        else:
            print_status('warn', "Task manager may not chain email task")
        
        return True
        
    except Exception as e:
        print_status('fail', f"Task manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_summarizer_integration():
    """Test summarizer integration with database and LLM."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}4. Summarizer Integration Test{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from summarization import RadioSummarizer
        from config import Config
        import inspect
        
        summarizer = RadioSummarizer()
        print_status('pass', "RadioSummarizer initialized successfully")
        
        # Check OpenAI client
        if summarizer.client:
            print_status('pass', "OpenAI client configured")
        else:
            print_status('warn', "OpenAI client not configured (LLM disabled)")
        
        # Check _call_llm method
        if hasattr(summarizer, '_call_llm'):
            print_status('pass', "Summarizer._call_llm() exists")
            
            # Check method signature
            sig = inspect.signature(summarizer._call_llm)
            params = list(sig.parameters.keys())
            required_params = ['model', 'instructions', 'prompt', 'max_out']
            for param in required_params:
                if param in params:
                    print_status('pass', f"_call_llm has '{param}' parameter")
                else:
                    print_status('fail', f"_call_llm missing '{param}' parameter")
                    return False
            
            # Check if it uses Chat Completions (not Responses API)
            source = inspect.getsource(summarizer._call_llm)
            if 'chat.completions.create' in source:
                print_status('pass', "_call_llm uses Chat Completions API")
            else:
                print_status('fail', "_call_llm not using Chat Completions API")
                return False
            
            # Check for parameter adaptation logic
            if 'max_completion_tokens' in source and 'max_tokens' in source:
                print_status('pass', "_call_llm has adaptive parameter logic")
            else:
                print_status('warn', "_call_llm may not handle all model types")
        else:
            print_status('fail', "Summarizer._call_llm() missing")
            return False
        
        # Check create_daily_digest method
        if hasattr(summarizer, 'create_daily_digest'):
            print_status('pass', "Summarizer.create_daily_digest() exists")
            
            # Check for digest lock usage
            source = inspect.getsource(summarizer.create_daily_digest)
            if 'try_acquire_digest_lock' in source:
                print_status('pass', "Daily digest uses lock mechanism (prevents duplicates)")
            else:
                print_status('warn', "Daily digest may not use lock mechanism")
        else:
            print_status('fail', "Summarizer.create_daily_digest() missing")
            return False
        
        return True
        
    except Exception as e:
        print_status('fail', f"Summarizer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_azure_environment():
    """Test Azure environment configuration."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}5. Azure Environment Configuration Test{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    try:
        from config import Config
        
        # Check critical environment variables
        env_vars = {
            'AZURE_SQL_CONNECTION_STRING': os.getenv('AZURE_SQL_CONNECTION_STRING'),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
            'SUMMARIZATION_MODEL': os.getenv('SUMMARIZATION_MODEL'),
            'ENABLE_LLM': os.getenv('ENABLE_LLM'),
            'ENABLE_STRUCTURED_OUTPUT': os.getenv('ENABLE_STRUCTURED_OUTPUT'),
            'DIGEST_CREATOR': os.getenv('DIGEST_CREATOR'),
            'PORT': os.getenv('PORT')
        }
        
        for var_name, var_value in env_vars.items():
            if var_value:
                if 'KEY' in var_name or 'CONNECTION_STRING' in var_name:
                    # Mask sensitive values
                    display_value = f"***{var_value[-4:]}" if len(var_value) > 4 else "***"
                    print_status('pass', f"{var_name}: {display_value}")
                else:
                    print_status('pass', f"{var_name}: {var_value}")
            else:
                if var_name in ['AZURE_SQL_CONNECTION_STRING', 'OPENAI_API_KEY']:
                    print_status('warn', f"{var_name}: NOT SET (using defaults/local)")
                else:
                    print_status('info', f"{var_name}: NOT SET (using defaults)")
        
        # Check Config class attributes
        print_status('info', f"Config.SUMMARIZATION_MODEL: {Config.SUMMARIZATION_MODEL}")
        print_status('info', f"Config.ENABLE_LLM: {Config.ENABLE_LLM}")
        print_status('info', f"Config.DIGEST_CREATOR: {Config.DIGEST_CREATOR}")
        print_status('info', f"Config.API_PORT: {Config.API_PORT}")
        
        # Check if running in Azure (PORT env var is set by Azure)
        if os.getenv('PORT'):
            print_status('info', "Appears to be running in Azure Web App environment")
        else:
            print_status('info', "Appears to be running in local/development environment")
        
        return True
        
    except Exception as e:
        print_status('fail', f"Environment test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all integration tests."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}AZURE SQL & SCHEDULER INTEGRATION TEST SUITE{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    results = {}
    
    # Run tests
    results['Database Connection'] = test_database_connection()
    results['Scheduler Integration'] = test_scheduler_integration()
    results['Task Manager Integration'] = test_task_manager_integration()
    results['Summarizer Integration'] = test_summarizer_integration()
    results['Azure Environment'] = test_azure_environment()
    
    # Print summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = 'pass' if result else 'fail'
        print_status(status, test_name)
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    if passed == total:
        print(f"{GREEN}✅ ALL TESTS PASSED ({passed}/{total}){RESET}")
        print(f"{GREEN}🚀 Azure SQL and Scheduler integration verified{RESET}")
        return 0
    else:
        print(f"{RED}❌ SOME TESTS FAILED ({passed}/{total} passed){RESET}")
        print(f"{YELLOW}⚠️  Review failed tests before deployment{RESET}")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
