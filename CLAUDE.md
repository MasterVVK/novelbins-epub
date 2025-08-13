# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chinese web novel translation system that processes "Shrouding the Heavens" (遮天) from novelbins.com through a multi-stage pipeline: parsing, AI translation, literary editing, and EPUB generation.

## Common Development Commands

### Running the Pipeline
```bash
# Stage 1: Parse chapters from novelbins.com
python 1_parser_selenium.py

# Stage 2: Translate chapters using Gemini AI
python 2_translator_improved.py

# Stage 3: Edit and improve translations
python 3_editor.py

# Stage 4: Generate EPUB
python 4_epub_generator.py
```

### Code Quality
```bash
# Run tests
pytest

# Lint code
flake8

# Format code
black .
```

### Database Management
```bash
# Initialize database (if using Flask app)
flask init-db

# View database
sqlite3 translations.db
```

### Web Interface
```bash
# Start Flask web app (port 5001)
python run_web.py

# Alternative web interface (port 8080)
./start_web.sh
```

## Architecture Overview

### Processing Pipeline
1. **Parser** (`1_parser_selenium.py`): Selenium-based scraper for novelbins.com
   - Uses headless Chrome for JavaScript rendering
   - Extracts chapter content, titles, and metadata
   - Stores raw data in SQLite database

2. **Translator** (`2_translator_improved.py`): Gemini AI translation
   - Specialized prompts for xianxia genre
   - Context-aware translation with glossary
   - Batch processing with rate limiting
   - Uses multiple API keys for load balancing

3. **Editor** (`3_editor.py`): Post-translation refinement
   - Multi-stage editing (analysis → style → dialogue)
   - Quality scoring system
   - Preserves original meaning while improving readability

4. **EPUB Generator** (`4_epub_generator.py`): Final output creation
   - Generates publication-ready EPUB files
   - Customizable metadata and formatting

### Data Storage
- **SQLite Database** (`translations.db`):
  - `chapters`: Original and translated content
  - `glossary`: Term consistency tracking
  - `edited_chapters`: Post-editing improvements
  - `translation_context`: Narrative continuity
  
- **File Storage** (`edited_translations/`):
  - Each chapter has `.txt` (content) and `.json` (metadata)
  - ~1,800+ processed chapters

### Key Technologies
- **Web Scraping**: Selenium + BeautifulSoup4
- **AI Translation**: Google Gemini AI (gemini-2.5-flash-preview-05-20)
- **Task Queue**: Celery + Redis
- **Web Framework**: Flask + SocketIO
- **EPUB Generation**: ebooklib

### Environment Configuration
Key settings in `.env`:
- Multiple `GEMINI_API_KEY_*` for API rotation
- `PROXY_URL` for SOCKS5 proxy support
- Translation parameters (temperature, batch size, token limits)
- Flask/Redis/Celery configuration

### Important Considerations
- The system uses proxy for accessing novelbins.com
- Translation quality improves from ~6 to ~8+ after editing
- Each API key has rate limits; system rotates through multiple keys
- Database contains extensive translation context and glossary data