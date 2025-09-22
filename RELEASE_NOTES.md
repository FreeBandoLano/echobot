# Release Notes

## Version 1.4.0 - Enhanced Summarization System (January 15, 2025)

### 🚀 Major Features

#### Enhanced Daily Digests
- **4000-word structured daily intelligence briefings** designed for government analysis
- **Comprehensive sections**: Preamble, Executive Summary, Topics Overview, Conversation Evolution, Moderator Analysis, Public Sentiment, Policy Implications, Notable Quotes
- **Government classification** labels and professional formatting
- **JSON-structured output** with automatic parsing and display
- **Election monitoring focus** for tracking public sentiment ahead of political events

#### Advanced Conversation Analysis
- **Conversation evolution tracking** shows how topics and sentiment shift throughout the program
- **Moderator influence analysis** tracks how hosts shape public discourse
- **Cross-block topic correlation** identifies themes that persist across program segments
- **Public sentiment deep-dive** with mood and confidence level analysis

### 🎨 UI/UX Improvements

#### Cleaner Production Interface
- **Removed Raw JSON toggle buttons** from block detail view for cleaner production interface
- **Removed Hide Filler buttons** - filler content always visible for transparency
- **Enhanced digest display** with structured sections and government styling
- **Professional classification labels** for executive briefings
- **Improved metadata display** showing generation details and statistics

#### Enhanced Block Detail View
- **Enhanced summary sections** with structured key themes and entity tags
- **Professional styling** consistent with government document standards
- **Better entity visualization** with tagged display format

### ⚙️ Configuration System

#### New Environment Variables
```env
ENABLE_DAILY_DIGEST=true
DAILY_DIGEST_TARGET_WORDS=4000
ENABLE_STRUCTURED_OUTPUT=true
ENABLE_CONVERSATION_EVOLUTION=true
ENABLE_TOPIC_DEEP_DIVE=true
```

#### Backward Compatibility
- **Automatic detection** of enhanced vs standard mode
- **Graceful fallback** to original digest format when enhanced features disabled
- **Existing digests** continue to work unchanged

### 🔧 Technical Improvements

#### Database Hardening (Phase 1A)
- **Enhanced result object handling** for improved Azure SQL compatibility
- **Dual database support** with automatic detection and conversion
- **Analytics function updates** with proper _mapping attribute usage
- **Emergency constraint handling** for production data migration

#### Model Integration
- **Adaptive model fallback** chain: GPT-5-nano → GPT-4.1-mini → GPT-4o-mini
- **Enhanced token management** with separate limits for enhanced vs standard digests
- **Robust error handling** with detailed logging and recovery mechanisms

#### API Enhancements
- **New endpoint**: `/api/generate-enhanced-digest` for manual digest generation
- **Comprehensive responses** with generation metadata and preview content
- **Date validation** and error handling for invalid requests

### 📊 Analytics Preparation (Phase 3 Ready)

#### Foundation for Advanced Features
- **Structured data storage** ready for topic drilling capabilities
- **Sentiment analysis framework** prepared for trend tracking
- **Cross-date comparison** infrastructure in place
- **Topic clustering** data structures optimized

### 🔒 Security and Classification

#### Government-Grade Features
- **Classification labels**: INTERNAL GOVERNMENT USE
- **Secure export** functionality with print and download controls
- **Audience targeting**: Prime Minister's Office, Senior Civil Servants
- **Data sensitivity** controls for policy decision-making content

### 🐛 Bug Fixes

#### Database Compatibility
- **Fixed parameter binding** issues in Azure SQL environment
- **Resolved NULL constraint** violations in topics table
- **Corrected GROUP BY clauses** for analytics queries
- **Enhanced result object** conversion for dual database support

#### Error Handling
- **Improved LLM fallback** logic with better error recovery
- **Enhanced logging** for debugging and monitoring
- **Graceful degradation** when enhanced features unavailable

### 📈 Performance Improvements

#### Optimized Processing
- **Efficient token usage** with adaptive model selection
- **Reduced API calls** through intelligent fallback mechanisms
- **Streamlined database** operations with proper result handling
- **Enhanced caching** for improved response times

### 🔄 Migration and Deployment

#### Seamless Upgrade Path
- **No breaking changes** to existing functionality
- **Environment variable** based feature activation
- **Automatic schema** compatibility handling
- **Gradual rollout** capability through configuration

#### Production Readiness
- **Comprehensive testing** on both SQLite and Azure SQL
- **Error recovery** mechanisms for production stability
- **Monitoring hooks** for operational visibility
- **Documentation** complete with troubleshooting guides

### 📚 Documentation

#### New Documentation
- **Enhanced Summarization Guide** with complete feature overview
- **Configuration reference** with all environment variables
- **API documentation** for new endpoints
- **Troubleshooting guide** with common issues and solutions

#### Updated Guides
- **Azure Setup Guide** updated for enhanced features
- **Deployment Analysis** includes new configuration requirements
- **README** updated with enhanced capabilities overview

### 🔮 Future Roadmap Preparation

#### Phase 3 Analytics Enhancement (Planned)
- **Topic drilling** with detailed caller quote analysis
- **Sentiment trend** visualization across multiple days
- **Predictive analytics** for emerging issue identification
- **Integration APIs** for other government monitoring systems

#### Advanced Features (Future)
- **Multi-day analysis** with conversation arc tracking
- **Automated alerting** for threshold-based notifications
- **Demographic analysis** when caller patterns identifiable
- **Cross-platform integration** with other intelligence sources

---

## Version 1.3.x - Database Compatibility & Analytics (December 2024)

### Database Improvements
- **Azure SQL compatibility** with dual database support
- **Analytics page** with comprehensive statistics
- **Emergency data migration** tools for production deployment
- **Enhanced error handling** for constraint violations

### Bug Fixes
- **Parameter binding** fixes for Azure SQL environment
- **Result object** conversion improvements
- **GROUP BY clause** corrections for analytics queries
- **Topics table** NULL constraint resolution

---

*For technical support and feature requests, please contact the development team.*
*Classification: INTERNAL GOVERNMENT USE*