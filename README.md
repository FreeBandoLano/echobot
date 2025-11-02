# RadioSynopsis - Open Source Radio Stream Analysis

**Automated radio stream recording, transcription, and AI-powered summarization.**

> **Status:** Beta v0.1.0 - Core functionality working, actively improving

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/AI-OpenAI%20Whisper%20%26%20GPT-green.svg)](https://openai.com/)

## ⚠️ Legal Notice
This software is for educational and research purposes. Users are responsible for:
- Complying with local broadcasting laws
- Obtaining necessary permissions for recording streams
- Respecting content licensing and copyright
- Following OpenAI's usage policies

## Features
- 🎙️ Automated radio stream recording
- 📝 Speech-to-text transcription via OpenAI Whisper
- 🤖 AI-powered content summarization
- 📊 Web dashboard for monitoring and analysis
- 🔍 Flexible configuration for any radio station

## Quick Start

### 1. Installation
```bash
git clone <repository-url>
cd echobot
pip install -r requirements.txt

# Install FFmpeg (required for audio processing)
# Ubuntu/Debian:
sudo apt update && sudo apt install ffmpeg
# macOS:
brew install ffmpeg
# Windows: Download from https://ffmpeg.org/download.html

cp .env.example .env
```

### 2. Configuration
Edit `.env` with your settings:
- Add your OpenAI API key
- Configure your radio station details
- Set your target audience and content focus

### 3. Verification & Run
```bash
# First time setup and verification
python main.py setup
python test_install.py  # Verify installation

# Start both recording and web interface
python main.py run

# Or run components separately:
python main.py web        # Web interface only
python main.py schedule   # Scheduler only
```

Visit `http://localhost:8001` for the dashboard.

## Quick Test (No API Key Required)
```bash
# Test without OpenAI API key
python main.py web  # Should start web interface
# Visit http://localhost:8001 to see the dashboard
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `STATION_NAME` | Your radio station name | "Radio Station" |
| `PROGRAM_NAME` | Program being analyzed | "Radio Program" |
| `TARGET_AUDIENCE` | Summary target audience | "general public" |
| `CONTENT_FOCUS` | Content areas to emphasize | "general topics and public interest" |
| `TIMEZONE_NAME` | Station timezone | "UTC" |
| `ENABLE_DEBUG_ENDPOINTS` | Enable debug APIs | "false" |

## Extending to Other Stations

1. **Find Stream URL**: Use the stream finder utilities
2. **Configure**: Update `.env` with station-specific settings
3. **Test**: Use debug endpoints (if enabled) to verify stream access
4. **Customize**: Adjust prompts and content focus for your audience

## API Costs
This project uses OpenAI APIs:
- **Whisper**: ~$0.006 per minute of audio
- **GPT-4**: Variable based on summary length
- Estimate: $5-15/day for continuous monitoring

## Architecture
```
Radio Stream → Audio Chunks → Transcription → AI Summary → Web Dashboard
```

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security
See [SECURITY.md](SECURITY.md) for security policies and reporting procedures.

## License
MIT License - see [LICENSE](LICENSE) for details.
