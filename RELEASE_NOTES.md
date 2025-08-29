# Release Notes

## v0.1.0-beta - Initial Open Source Release
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

### 🔧 System Requirements
- **Memory**: 512MB+ available RAM
- **Storage**: 100MB+ free space (plus audio storage)
- **Network**: Stable internet for streaming and API calls
- **OS**: Linux, macOS, Windows (with FFmpeg)

### ⚙️ Configuration
The system is pre-configured for VOB 92.9 FM (Barbados) but can be adapted for any radio station by modifying the `.env` file.

Key configuration options:
- `RADIO_STREAM_URL`: Direct stream URL
- `STATION_NAME`: Your radio station
- `TARGET_AUDIENCE`: Summary audience (e.g., "government officials")
- `CONTENT_FOCUS`: Content areas to emphasize

### 📊 Cost Estimation
Using OpenAI APIs:
- **Whisper**: ~$0.006 per minute of audio
- **GPT-4**: Variable based on summary length
- **Estimated**: $5-15/day for continuous monitoring

### 🐛 Known Issues
- **FFmpeg Required**: Audio processing fails without FFmpeg installation
- **API Key Validation**: Some features require OpenAI API key configuration
- **Stream Detection**: Manual stream URL configuration may be needed for some stations

### ⚠️ Beta Limitations
- Limited error recovery for network issues
- Basic retry logic for API failures
- Single-threaded processing (may be slow for large files)
- No built-in authentication (suitable for internal use)

### 🔒 Security Notes
- Designed for internal/government monitoring use
- Debug endpoints disabled by default
- No authentication system (add reverse proxy if needed)
- Store API keys securely (never commit to version control)

### 📚 Documentation
- `README.md`: Installation and basic usage
- `.env.example`: Configuration template
- `test_install.py`: Installation verification
- `CONTRIBUTING.md`: Development guidelines

### 🤝 Contributing
We welcome contributions! Please see `CONTRIBUTING.md` for:
- Code style guidelines
- How to add support for new radio stations
- Reporting bugs and feature requests
- Development setup

### 📞 Support
- **Issues**: Use GitHub Issues for bug reports
- **Questions**: Start a GitHub Discussion
- **Security**: See `SECURITY.md` for reporting procedures

### 🔮 Roadmap
Future releases may include:
- Enhanced error handling and retry logic
- Support for local Whisper models (cost reduction)
- Multi-language support
- Real-time streaming analysis
- Advanced audio processing options
- Authentication and user management

### 📝 Legal
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

#### Python Dependencies
```bash
# If pip install fails
python -m pip install --upgrade pip
pip install -r requirements.txt

# For virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

#### OpenAI API Issues
- Get API key from: https://platform.openai.com/api-keys
- Set monthly usage limits to control costs
- Check API quota if requests fail

#### Stream Access Issues
- Test stream URL in browser first
- Check firewall/proxy settings
- Some streams require specific user agents
- Contact station for official stream URL

---

**Full Changelog**: Initial release
