# Contributing to RadioSynopsis

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. **Fork and Clone**
   ```bash
   git clone <your-fork-url>
   cd radiosynopsis
   ```

2. **Environment Setup**
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run Tests**
   ```bash
   python -m pytest tests/ -v
   ```

## Development Guidelines

### Code Style
- Follow PEP 8 conventions
- Add type hints where practical
- Write clear, descriptive docstrings
- Keep functions focused and single-purpose

### Commit Messages
- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove)
- Reference issues when applicable

### Pull Requests
1. Create a feature branch (`git checkout -b feature/your-feature`)
2. Make your changes with tests
3. Ensure all tests pass
4. Update documentation if needed
5. Submit PR with clear description

### Testing
- Add unit tests for new functionality
- Ensure existing tests continue to pass
- Test with different radio stations/streams when possible

## Areas for Contribution

- **New Radio Station Support**: Add configurations for additional stations
- **Alternative Backends**: Implement non-OpenAI transcription/summarization
- **UI Improvements**: Enhance the web dashboard
- **Performance**: Optimize audio processing and storage
- **Documentation**: Improve guides and examples
- **Testing**: Expand test coverage

## Questions?
Open an issue for discussion before starting major changes.
