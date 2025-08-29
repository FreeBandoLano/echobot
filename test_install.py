#!/usr/bin/env python3
"""
Installation test script for RadioSynopsis
Run this after setup to verify everything works
"""

import sys
import subprocess
import importlib
from pathlib import Path

def test_python_dependencies():
    """Test that all Python dependencies can be imported."""
    required_modules = [
        'fastapi', 'uvicorn', 'openai', 'requests', 'schedule', 
        'pydub', 'pytz', 'jinja2', 'python_multipart'
    ]
    
    print("🐍 Testing Python dependencies...")
    missing = []
    
    for module in required_modules:
        try:
            # Handle modules with different import names
            import_name = module.replace('-', '_').replace('python_multipart', 'multipart')
            importlib.import_module(import_name)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module}")
            missing.append(module)
    
    return len(missing) == 0, missing

def test_ffmpeg():
    """Test FFmpeg availability."""
    print("\n🎵 Testing FFmpeg...")
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"  ✅ {version}")
            return True
        else:
            print(f"  ❌ FFmpeg failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ❌ FFmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"  ❌ FFmpeg test error: {e}")
        return False

def test_configuration():
    """Test configuration setup."""
    print("\n⚙️ Testing configuration...")
    
    # Check if .env.example exists
    if not Path('.env.example').exists():
        print("  ❌ .env.example not found")
        return False
    print("  ✅ .env.example found")
    
    # Check if .env exists
    if Path('.env').exists():
        print("  ✅ .env found")
        
        # Try to load config
        try:
            from config import Config
            print("  ✅ Configuration loads successfully")
            
            # Check for API key
            if Config.OPENAI_API_KEY and Config.OPENAI_API_KEY != 'your_openai_api_key_here':
                print("  ✅ OpenAI API key configured")
            else:
                print("  ⚠️ OpenAI API key not configured")
            
            return True
        except Exception as e:
            print(f"  ❌ Configuration error: {e}")
            return False
    else:
        print("  ⚠️ .env not found (copy from .env.example)")
        return False

def test_database():
    """Test database setup."""
    print("\n💾 Testing database...")
    try:
        from database import db
        with db.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        print("  ✅ Database connection successful")
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False

def test_web_server():
    """Test if web server can start."""
    print("\n🌐 Testing web server startup...")
    try:
        import web_app
        print("  ✅ Web app imports successfully")
        return True
    except Exception as e:
        print(f"  ❌ Web app import error: {e}")
        return False

def main():
    print("🧪 RadioSynopsis Installation Test")
    print("=" * 40)
    
    tests = [
        ("Python Dependencies", test_python_dependencies),
        ("FFmpeg", test_ffmpeg),
        ("Configuration", test_configuration),
        ("Database", test_database),
        ("Web Server", test_web_server),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if test_name == "Python Dependencies":
                success, missing = test_func()
                results.append((test_name, success, missing if not success else None))
            else:
                success = test_func()
                results.append((test_name, success, None))
        except Exception as e:
            print(f"  💥 Test crashed: {e}")
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 Test Summary")
    print("=" * 40)
    
    passed = 0
    for test_name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if not success and error:
            if isinstance(error, list):  # Missing dependencies
                print(f"     Missing: {', '.join(error)}")
            else:
                print(f"     Error: {error}")
        if success:
            passed += 1
    
    print(f"\nResult: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! RadioSynopsis is ready to use.")
        print("\nNext steps:")
        print("1. Configure your .env file with OpenAI API key")
        print("2. Run: python main.py web")
        print("3. Visit: http://localhost:8001")
    else:
        print("\n⚠️ Some tests failed. Please fix the issues above.")
        
        if not any(name == "FFmpeg" and success for name, success, _ in results):
            print("\n💡 To install FFmpeg:")
            print("  Ubuntu/Debian: sudo apt install ffmpeg")
            print("  macOS: brew install ffmpeg") 
            print("  Windows: Download from https://ffmpeg.org/")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
