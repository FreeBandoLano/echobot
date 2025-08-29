# GitHub Release Instructions

## How to Create the Release on GitHub

1. **Go to**: https://github.com/FreeBandoLano/echobot/releases/new

2. **Fill in the form**:
   - **Tag version**: `v0.1.0-beta` (should auto-populate since we pushed the tag)
   - **Release title**: `RadioSynopsis v0.1.0-beta - Initial Open Source Release`
   - **Check**: ✅ "This is a pre-release" (since it's beta)

3. **Release description** (copy the content below):

---

## RadioSynopsis v0.1.0-beta - Initial Open Source Release
*Released: August 29, 2025*

### 🎉 What's New
This is the first public beta release of RadioSynopsis - an open-source radio stream analysis system that automatically records, transcribes, and summarizes radio content using AI.

### ✨ Features
- **Automated Radio Recording**: Stream capture from online radio sources
- **AI Transcription**: Speech-to-text using OpenAI Whisper
- **Intelligent Summarization**: Content analysis using GPT-4
- **Web Dashboard**: Real-time monitoring and results viewing
- **Flexible Scheduling**: Configurable recording blocks
- **Multi-Station Support**: Easily adaptable to different radio stations

### 🚀 Quick Start
```bash
git clone https://github.com/FreeBandoLano/echobot.git
cd echobot
pip install -r requirements.txt

# Install FFmpeg (REQUIRED)
sudo apt install ffmpeg  # Ubuntu/Debian
# brew install ffmpeg    # macOS

cp .env.example .env
# Edit .env with your OpenAI API key

python main.py setup
python test_install.py  # Verify installation
python main.py web      # Start dashboard
```

### 📋 Requirements
- **Python 3.8+**
- **FFmpeg** (for audio processing)
- **OpenAI API Key** (for transcription/summarization)
- **Internet connection** (for stream access and AI services)

### 📊 Cost Estimation
Using OpenAI APIs:
- **Whisper**: ~$0.006 per minute of audio
- **GPT-4**: Variable based on summary length
- **Estimated**: $5-15/day for continuous monitoring

### 🐛 Known Issues & Limitations
- **FFmpeg Required**: Audio processing fails without FFmpeg installation
- **API Key Validation**: Some features require OpenAI API key configuration
- **Stream Detection**: Manual stream URL configuration may be needed for some stations
- Limited error recovery for network issues
- Basic retry logic for API failures
- No built-in authentication (suitable for internal use)

### 🤝 Contributing
We welcome contributions! Please see:
- 🐛 **Bug reports**: Use GitHub Issues
- 💡 **Feature requests**: Use GitHub Issues with enhancement label
- 📻 **New radio stations**: Use the station support issue template
- 📖 **Documentation**: Submit PRs for improvements

### 🔮 What's Next
Future releases may include:
- Enhanced error handling and retry logic
- Support for local Whisper models (cost reduction)
- Multi-language support
- Real-time streaming analysis
- Authentication and user management

### 📝 Legal & Usage
- **License**: MIT (see LICENSE file)
- **Usage**: Educational and research purposes
- **Compliance**: Users responsible for broadcasting law compliance
- **Content**: Respect copyright and licensing agreements

---

### Installation Troubleshooting

#### FFmpeg Issues
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
# Add to PATH environment variable
```

#### OpenAI API Issues
- Get API key from: https://platform.openai.com/api-keys
- Set monthly usage limits to control costs
- Check API quota if requests fail

**Full Documentation**: See README.md for complete setup instructions

---

4. **Click**: "Publish release"

## After Publishing

1. **Test the release**:
   ```bash
   # Test installation from the release
   git clone https://github.com/FreeBandoLano/echobot.git
   cd echobot
   git checkout v0.1.0-beta
   python test_install.py
   ```

2. **Share the release**:
   - Social media announcement (template in prepare_release.py output)
   - Relevant communities (Reddit, Discord, etc.)
   - Professional networks (LinkedIn, etc.)

3. **Monitor feedback**:
   - Watch GitHub Issues
   - Respond to installation problems
   - Collect feature requests
   - Track usage patterns

4. **Plan next iteration**:
   - Address common issues found
   - Implement high-value feature requests
   - Improve documentation based on questions
