# VOB 92.9 FM Radio Synopsis System

An automated system for capturing, transcribing, and summarizing "Down to Brass Tacks" radio program content for government/civil service use.

## 🎯 System Overview

This MVP system captures live radio audio from VOB 92.9 FM, transcribes it using OpenAI Whisper, and generates structured summaries using GPT-4 for policy makers and civil servants.

## ✅ Current Status: **FULLY FUNCTIONAL**

- ✅ Audio recording via Radio stream URl
- ✅ Real-time transcription with OpenAI Whisper 
- ✅ AI-powered summarization with GPT-4
- ✅ Web dashboard for manual control
- ✅ Structured output for government use

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.8+
- FFmpeg installed
- OpenAI API key

### 2. Installation
```bash
# Clone repository
git clone <your-repo-url>
cd govradio

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp config.env.example .env
```

### 3. Configuration
Edit `.env` file:
```bash
# Required: Your OpenAI API key
OPENAI_API_KEY=sk-proj-your-key-here

# Audio source (use Stereo Mix for browser audio) 
AUDIO_INPUT_DEVICE=Stereo Mix (Realtek(R) Audio)
# To use Audio from VOB92.9 FM live stream
RADIO_STREAM_URL=RADIO_STREAM_URL=https://ice66.securenetsystems.net/VOB929
# Make sure to only use one audio source at a time 


# Schedule (Barbados time)
BLOCK_A_START=10:00
BLOCK_A_END=12:00
# ... etc
```

### 4. Run System
```bash
# Start web dashboard
python main.py web

# Visit dashboard
http://localhost:8001
```

## 📋 Usage

### Manual Recording (Current)
0. Ensure VOB 92.9 FM is playing in browser ( If using Stereo Mix as audio input )
1. Click "Record [Block]" button at appropriate time
2. Wait for recording to complete  
3. Click "Process [Block]" for transcription & summary
4. View results in dashboard

### Block Schedule
- **Block A**: 10:00-12:00 (Morning Block)
- **Block B**: 12:05-12:30 (News Summary)  
- **Block C**: 12:40-13:30 (Major Newscast)
- **Block D**: 13:35-14:00 (History Block)

## 📊 Output Format

### Executive Summary
Structured summaries include:
- Key topics discussed
- Public concerns raised
- Policy implications
- Notable quotes
- Entities mentioned

### Civil Service Focus
Output formatted for:
- Policy makers
- Government officials
- Public service planning
- Community engagement insights

## 🔧 Technical Architecture

- **Audio Capture**: FFmpeg + DirectShow (Windows Stereo Mix)
- **Transcription**: OpenAI Whisper API
- **Summarization**: OpenAI GPT-4  
- **Web Interface**: FastAPI + Bootstrap
- **Database**: SQLite
- **Scheduling**: Python schedule library

## 🔒 Security Notes

- `.env` file contains sensitive API keys - **NEVER commit to git**
- Use `.gitignore` to exclude sensitive files
- Consider Azure OpenAI for enterprise deployment
- Rotate API keys regularly

## 📁 Project Structure

```
govradio/
├── main.py              # Application entry point
├── config.py            # Configuration management
├── audio_recorder.py    # Audio capture logic
├── transcription.py     # OpenAI Whisper integration
├── summarization.py     # GPT-4 summarization
├── web_app.py          # FastAPI web interface
├── scheduler.py        # Recording scheduler
├── database.py         # SQLite database
├── .env               # Environment variables (not in git)
├── requirements.txt   # Python dependencies
└── templates/         # HTML templates
```

## 🎮 Testing

For rapid testing, use shorter block durations:
```bash
# 1-minute test blocks
BLOCK_A_START=09:15
BLOCK_A_END=09:16
BLOCK_B_START=09:17  
BLOCK_B_END=09:18
# etc...
```

## 🚀 Deployment Considerations

### Production Deployment
- Use Azure OpenAI for enterprise-grade API access
- Implement proper logging and monitoring
- Set up automated scheduling
- Configure backup and recovery
- Use environment-specific configurations

### Scaling Options
- Add automatic recording triggers
- Implement real-time streaming
- Add multiple radio station support
- Integrate with government content management systems

## 📝 Recent Updates

**Latest Version** (Working MVP):
- ✅ Fixed Stereo Mix audio capture
- ✅ Resolved port conflicts (now uses 8001)
- ✅ Added 1-minute test blocks for rapid iteration
- ✅ Implemented full transcription + summarization pipeline
- ✅ Professional summary formatting for civil service use

## 🤝 Contributing

This system was developed for urgent government radio monitoring needs. 

For issues or enhancements:
1. Test thoroughly with radio content
2. Ensure security best practices
3. Maintain civil service output formatting
4. Document configuration changes

## 📞 Support

System captures content from VOB 92.9 FM "Down to Brass Tacks" program for government policy insights and community engagement analysis.

## 🚀 Deployment

This application is automatically deployed to Azure App Service via GitHub Actions.
