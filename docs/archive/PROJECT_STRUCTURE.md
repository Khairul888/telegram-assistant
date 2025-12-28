# 📁 Project Structure Template

This document outlines the complete project structure that will be created during development.

## 📂 Directory Structure

```
telegram-assistant/
├── 📄 README.md                      # Project overview and quick start
├── 📄 PROJECT_DOCUMENTATION.md       # Comprehensive project documentation
├── 📄 SETUP_INSTRUCTIONS.md          # Step-by-step setup guide
├── 📄 .env.example                   # Environment variables template
├── 📄 .env                           # Actual environment variables (gitignored)
├── 📄 .gitignore                     # Git ignore rules
├── 📄 requirements.txt               # Python dependencies
├── 📄 vercel.json                    # Vercel deployment configuration
├── 📄 runtime.txt                    # Python version specification
│
├── 📁 api/                           # Vercel serverless functions
│   ├── 📄 __init__.py
│   ├── 📄 telegram-webhook.py        # Handle Telegram messages
│   ├── 📄 drive-webhook.py           # Handle Google Drive file events
│   ├── 📄 process-file.py            # File processing endpoint
│   ├── 📄 health.py                  # Health check endpoint
│   └── 📄 chat.py                    # Chat interface endpoint
│
├── 📁 src/                           # Core application modules
│   ├── 📄 __init__.py
│   │
│   ├── 📁 core/                      # Core functionality
│   │   ├── 📄 __init__.py
│   │   ├── 📄 config.py              # Configuration and environment variables
│   │   ├── 📄 logger.py              # Logging configuration
│   │   ├── 📄 database.py            # Database connection and models
│   │   └── 📄 exceptions.py          # Custom exception classes
│   │
│   ├── 📁 services/                  # External service integrations
│   │   ├── 📄 __init__.py
│   │   ├── 📄 telegram_service.py    # Telegram Bot API integration
│   │   ├── 📄 google_drive_service.py# Google Drive API integration
│   │   ├── 📄 google_docs_service.py # Google Docs API integration
│   │   ├── 📄 gemini_service.py      # Google Gemini AI integration
│   │   ├── 📄 pinecone_service.py    # Pinecone vector database
│   │   ├── 📄 supabase_service.py    # Supabase integration (alternative)
│   │   └── 📄 cloudinary_service.py  # Image processing (optional)
│   │
│   ├── 📁 processors/                # File and data processing
│   │   ├── 📄 __init__.py
│   │   ├── 📄 text_processor.py      # Text document processing
│   │   ├── 📄 image_processor.py     # Image processing and OCR
│   │   ├── 📄 excel_processor.py     # Excel/CSV file processing
│   │   ├── 📄 pdf_processor.py       # PDF document processing
│   │   └── 📄 file_detector.py       # File type detection
│   │
│   ├── 📁 ai/                        # AI processing modules
│   │   ├── 📄 __init__.py
│   │   ├── 📄 metadata_extractor.py  # Extract structured metadata from content
│   │   ├── 📄 embeddings_generator.py# Generate vector embeddings
│   │   ├── 📄 chat_handler.py        # Handle conversational AI
│   │   ├── 📄 memory_manager.py      # Conversation memory management
│   │   └── 📄 prompt_templates.py    # AI prompt templates
│   │
│   ├── 📁 models/                    # Data models and schemas
│   │   ├── 📄 __init__.py
│   │   ├── 📄 document.py            # Document data model
│   │   ├── 📄 chat_message.py        # Chat message model
│   │   ├── 📄 file_metadata.py       # File metadata model
│   │   ├── 📄 user_profile.py        # User profile model
│   │   └── 📄 processing_job.py      # Processing job status model
│   │
│   ├── 📁 utils/                     # Utility functions
│   │   ├── 📄 __init__.py
│   │   ├── 📄 file_utils.py          # File handling utilities
│   │   ├── 📄 text_utils.py          # Text processing utilities
│   │   ├── 📄 async_utils.py         # Async/await helper functions
│   │   ├── 📄 validation_utils.py    # Data validation utilities
│   │   └── 📄 encryption_utils.py    # Security and encryption helpers
│   │
│   └── 📁 workflows/                 # Business logic workflows
│       ├── 📄 __init__.py
│       ├── 📄 document_ingestion.py  # Complete document processing workflow
│       ├── 📄 chat_workflow.py       # Chat interaction workflow
│       ├── 📄 approval_workflow.py   # User approval processes
│       └── 📄 batch_processing.py    # Batch file processing
│
├── 📁 tests/                         # Test suite
│   ├── 📄 __init__.py
│   ├── 📄 conftest.py               # Pytest configuration
│   ├── 📄 test_telegram_service.py  # Telegram service tests
│   ├── 📄 test_file_processing.py   # File processing tests
│   ├── 📄 test_ai_processing.py     # AI processing tests
│   └── 📄 test_workflows.py         # End-to-end workflow tests
│
├── 📁 scripts/                       # Utility scripts
│   ├── 📄 setup_database.py         # Database initialization
│   ├── 📄 migrate_data.py           # Data migration from n8n
│   ├── 📄 test_apis.py              # Test all API connections
│   └── 📄 cleanup_old_files.py      # Maintenance scripts
│
├── 📁 docs/                          # Additional documentation
│   ├── 📄 API_REFERENCE.md          # API endpoint documentation
│   ├── 📄 DEPLOYMENT_GUIDE.md       # Detailed deployment instructions
│   ├── 📄 TROUBLESHOOTING.md        # Common issues and solutions
│   └── 📄 CONTRIBUTING.md           # Development guidelines
│
└── 📁 config/                        # Configuration files
    ├── 📄 logging_config.yaml       # Logging configuration
    ├── 📄 ai_prompts.yaml           # AI prompt templates
    └── 📄 file_type_mappings.yaml   # File type processing rules
```

## 📋 Key Files Explanation

### 🚀 Deployment Files

- **`vercel.json`**: Configures Vercel serverless deployment
- **`requirements.txt`**: Python package dependencies
- **`runtime.txt`**: Specifies Python version for hosting platform

### 🔧 Configuration Files

- **`.env`**: Environment variables (API keys, database URLs)
- **`src/core/config.py`**: Application configuration management
- **`config/`**: YAML configuration files for various components

### 🌐 API Endpoints (`api/` directory)

- **`telegram-webhook.py`**: Receives messages from Telegram
- **`drive-webhook.py`**: Handles Google Drive file notifications
- **`process-file.py`**: On-demand file processing
- **`chat.py`**: Web-based chat interface (optional)

### 🧠 Core Services (`src/services/` directory)

- **`telegram_service.py`**: Telegram Bot API wrapper
- **`google_drive_service.py`**: Google Drive file operations
- **`gemini_service.py`**: Google Gemini AI integration
- **`pinecone_service.py`**: Vector database operations

### ⚙️ Processing Pipeline (`src/processors/` directory)

- **`text_processor.py`**: Extract text from documents
- **`image_processor.py`**: OCR and image analysis
- **`excel_processor.py`**: Spreadsheet data extraction
- **`file_detector.py`**: Automatic file type detection

### 🤖 AI Components (`src/ai/` directory)

- **`metadata_extractor.py`**: Structured data extraction using AI
- **`chat_handler.py`**: Conversational AI with memory
- **`embeddings_generator.py`**: Vector embeddings for search

### 📊 Data Models (`src/models/` directory)

- **`document.py`**: Document storage and metadata
- **`chat_message.py`**: Conversation history
- **`processing_job.py`**: Track file processing status

### 🔄 Workflows (`src/workflows/` directory)

- **`document_ingestion.py`**: Complete file → AI → storage pipeline
- **`chat_workflow.py`**: Message → search → AI → response pipeline
- **`approval_workflow.py`**: User confirmation processes

## 🏗️ Development Phases

### Phase 1: Core Infrastructure
1. Setup configuration and logging
2. Database models and connections
3. Basic Telegram bot functionality

### Phase 2: File Processing
1. Google Drive integration
2. File type detection and processing
3. Text extraction from various formats

### Phase 3: AI Processing
1. Gemini AI integration
2. Metadata extraction
3. Vector embeddings generation

### Phase 4: Vector Storage
1. Pinecone/Supabase integration
2. Document storage and retrieval
3. Semantic search functionality

### Phase 5: Chat Interface
1. Conversational AI with memory
2. Query processing and response generation
3. Context-aware responses

### Phase 6: Advanced Features
1. Image processing and OCR
2. Excel/spreadsheet analysis
3. Approval workflows

### Phase 7: Deployment & Testing
1. Vercel deployment configuration
2. Environment variable setup
3. End-to-end testing

## 🔍 File Naming Conventions

- **Snake_case**: For Python files and directories
- **Descriptive names**: Clear purpose from filename
- **Service pattern**: `*_service.py` for external API integrations
- **Processor pattern**: `*_processor.py` for data processing
- **Model pattern**: Singular nouns for data models

## 🧪 Testing Strategy

- **Unit tests**: Individual function testing
- **Integration tests**: Service-to-service testing
- **End-to-end tests**: Complete workflow testing
- **Mock services**: For testing without API calls

## 📦 Dependency Management

- **Core dependencies**: FastAPI, async libraries
- **AI dependencies**: Google AI SDK, embeddings
- **Service dependencies**: Telegram, Google APIs
- **Development dependencies**: Testing, linting tools

This structure provides a scalable, maintainable codebase that can grow with your project's needs while maintaining clear separation of concerns.