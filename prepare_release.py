#!/usr/bin/env python3
"""
GitHub Release Preparation Script
Helps prepare files and commands for creating a GitHub release
"""

import subprocess
import sys
from pathlib import Path
from version import __version__, RELEASE_NAME, RELEASE_DATE

def check_git_status():
    """Check if git repository is clean and ready for release."""
    print("📋 Checking Git Status...")
    
    try:
        # Check if we're in a git repository
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            print("⚠️ Working directory has uncommitted changes:")
            print(result.stdout)
            print("Please commit or stash changes before creating a release.")
            return False
        
        print("✅ Git working directory is clean")
        
        # Check current branch
        result = subprocess.run(['git', 'branch', '--show-current'], 
                              capture_output=True, text=True, check=True)
        current_branch = result.stdout.strip()
        print(f"📍 Current branch: {current_branch}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {e}")
        return False
    except FileNotFoundError:
        print("❌ Git not found. Please install git.")
        return False

def check_release_files():
    """Check that all release files are present."""
    print("\n📁 Checking Release Files...")
    
    required_files = [
        'README.md',
        'LICENSE',
        'requirements.txt',
        '.env.example',
        'RELEASE_NOTES.md',
        'version.py',
        'main.py',
        'test_install.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️ Missing files: {', '.join(missing_files)}")
        return False
    
    print("✅ All required files present")
    return True

def generate_release_commands():
    """Generate the commands needed to create the GitHub release."""
    print(f"\n🚀 Release Preparation for v{__version__}")
    print("=" * 50)
    
    tag_name = f"v{__version__}"
    
    print("\n1️⃣ Create and push git tag:")
    print(f"git tag -a {tag_name} -m \"{RELEASE_NAME}\"")
    print(f"git push origin {tag_name}")
    
    print("\n2️⃣ GitHub CLI release command:")
    print(f"gh release create {tag_name} \\")
    print(f"  --title \"RadioSynopsis {tag_name} - {RELEASE_NAME}\" \\")
    print(f"  --notes-file RELEASE_NOTES.md \\")
    print("  --prerelease \\")
    print("  --generate-notes")
    
    print("\n3️⃣ Or create release manually on GitHub:")
    print("- Go to: https://github.com/FreeBandoLano/echobot/releases/new")
    print(f"- Tag version: {tag_name}")
    print(f"- Release title: RadioSynopsis {tag_name} - {RELEASE_NAME}")
    print("- Check 'This is a pre-release' (since it's beta)")
    print("- Copy content from RELEASE_NOTES.md")

def generate_docker_commands():
    """Generate Docker build commands for the release."""
    print("\n🐳 Docker Release Commands:")
    print("=" * 30)
    
    tag_name = f"v{__version__}"
    
    print("# Build Docker image")
    print(f"docker build -t radiosynopsis:{tag_name} .")
    print(f"docker build -t radiosynopsis:latest .")
    
    print("\n# Test Docker image")
    print(f"docker run --rm radiosynopsis:{tag_name} python main.py --version")
    
    print("\n# Push to registry (if using Docker Hub)")
    print(f"docker tag radiosynopsis:{tag_name} yourusername/radiosynopsis:{tag_name}")
    print(f"docker push yourusername/radiosynopsis:{tag_name}")

def generate_announcement_text():
    """Generate text for release announcement."""
    print("\n📢 Release Announcement Template:")
    print("=" * 40)
    
    announcement = f"""
🎉 RadioSynopsis v{__version__} Released!

We're excited to announce the first beta release of RadioSynopsis - an open-source radio stream analysis system.

🚀 What it does:
• Automatically records radio streams
• Transcribes audio using OpenAI Whisper
• Generates AI-powered summaries with GPT-4
• Provides a web dashboard for monitoring

📋 Perfect for:
• Government monitoring of public radio
• Research institutions studying media content
• Community organizations tracking local news
• Anyone needing automated radio analysis

⚡ Quick start:
```bash
git clone https://github.com/FreeBandoLano/echobot.git
cd echobot
pip install -r requirements.txt
cp .env.example .env
python main.py setup
```

💡 Pre-configured for VOB 92.9 FM (Barbados) but easily adaptable to any radio station.

🔗 Try it out: https://github.com/FreeBandoLano/echobot/releases/tag/v{__version__}

#OpenSource #RadioAnalysis #AI #Python #Transcription
"""
    
    print(announcement.strip())

def main():
    print("🎯 RadioSynopsis Release Preparation")
    print("=" * 40)
    
    # Check git status
    if not check_git_status():
        print("\n❌ Git checks failed. Please resolve issues before proceeding.")
        sys.exit(1)
    
    # Check release files
    if not check_release_files():
        print("\n❌ Missing required files. Please ensure all files are present.")
        sys.exit(1)
    
    print("\n✅ All checks passed!")
    
    # Generate commands and templates
    generate_release_commands()
    generate_docker_commands()
    generate_announcement_text()
    
    print("\n" + "=" * 50)
    print("🎉 Ready for Release!")
    print("=" * 50)
    print("1. Review the commands above")
    print("2. Execute git tag and push commands")
    print("3. Create GitHub release")
    print("4. Share announcement on social media")
    print("5. Monitor issues and feedback")

if __name__ == "__main__":
    main()
