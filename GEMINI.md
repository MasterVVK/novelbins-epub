**Project Overview**

This project, "Novelbins EPUB," is a comprehensive Python-based system designed for parsing, translating, editing, and generating EPUB files of web novels. It features a Flask web application for managing the workflow through a user interface, complemented by standalone scripts for core functionalities like parsing, translation, and EPUB generation.

**Key Technologies:**

*   **Web Framework:** Flask
*   **Database (Web App):** SQLAlchemy with Flask-SQLAlchemy and Flask-Migrate for migrations.
*   **Database (Standalone Scripts):** SQLite (managed directly via `sqlite3` module).
*   **Asynchronous Tasks:** Celery with Redis as a broker.
*   **Web Scraping:** Selenium and BeautifulSoup4.
*   **AI/Translation:** Google Generative AI, OpenAI APIs, Anthropic Claude, and **Ollama with dynamic context calculation**.
*   **EPUB Generation:** `ebooklib`.
*   **Frontend:** Jinja2 templates, likely with custom CSS/JS.
*   **Utilities:** `python-dotenv`, `httpx`, `httpx-socks`.

**Architecture:**

The project employs a hybrid architecture:

1.  **Web Application (`web_app/`):** A Flask application providing a user interface for managing novels, chapters, tasks, system settings, and prompt templates. It exposes both traditional web views and RESTful API endpoints. It uses Flask-SQLAlchemy for its primary data persistence.
2.  **Standalone Scripts:** A set of Python scripts (`1_parser_selenium.py`, `2_translator_improved_filtered.py`, `3_editor.py`, `4_epub_generator.py`, etc.) that perform specific tasks. These scripts interact with a separate SQLite database (managed by `database.py`) for their operational data. This suggests they can be run independently for batch processing or specific tasks outside the web UI.

**Core Functionalities:**

*   **Novel Management:** Add, edit, delete, and restore novel entries.
*   **Chapter Parsing:** Scrape novel chapters from various web sources using Selenium, with support for EPUB uploads.
*   **Translation:** Translate chapters using configured AI models (Gemini, OpenAI), with intelligent glossary filtering and prompt templating.
*   **Editing:** Manual and potentially AI-assisted editing of translated chapters.
*   **EPUB Generation:** Create EPUB files from translated and edited chapters, including glossaries and summaries.
*   **Task Management:** Track the progress of parsing, translation, and editing tasks.
*   **Glossary Management:** Comprehensive management of terms specific to each novel, including adding, editing, deleting, searching, and import/export.
*   **System Settings:** Configure API keys, default models, temperatures, and other system-wide parameters.
*   **Prompt Templates:** Manage and customize AI prompt templates for translation and editing.

**Building and Running:**

1.  **Setup Virtual Environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Initialize Database (for Web App):**
    ```bash
    flask --app web_app.run init-db
    ```
    *Note: This initializes the Flask-SQLAlchemy database. The standalone scripts use a separate SQLite database.*
4.  **Run the Web Application:**
    ```bash
    python web_app/run.py
    ```
    The web application will typically run on `http://0.0.0.0:5001` (or `localhost:5001`).

**Development Conventions:**

*   **Language:** Python 3.
*   **Code Formatting:** `black` (indicated by `black==23.11.0` in `requirements.txt`).
*   **Linting:** `flake8` (indicated by `flake8==6.1.0` in `requirements.txt`).
*   **Testing:** `pytest` (indicated by `pytest==7.4.3` in `requirements.txt`), with specific tests found in `test_*.py` files.
*   **Database Migrations:** `alembic` is used for managing database schema changes for the Flask application.
*   **Logging:** Configured via `setup_logging` in `web_app/app/__init__.py`.
*   **Modularity:** The project is structured into `web_app/app/api`, `web_app/app/models`, `web_app/app/services`, and `parsers` directories, promoting separation of concerns.

**Standalone Script Usage Examples:**

*   **Parsing:**
    ```bash
    python 1_parser_selenium.py --chapters 10
    ```
*   **Translation:**
    ```bash
    python 2_translator_improved_filtered.py
    ```
*   **EPUB Generation:**
    ```bash
    python 4_epub_generator.py --title "My Novel" --author "Me"
    ```
    *Note: These scripts interact with the `translations.db` SQLite database.*