# ✈️ Travel Buddy - AI Travel Companion & Expense Tracker

A Telegram bot that acts as your personal travel assistant and group expense tracker. Upload photos of tickets, receipts, and itineraries - I'll remember everything and help track your spending.

## ✨ Features

- ✈️ **Travel Context Memory** - Upload flight tickets, hotel bookings, itineraries
- 🧾 **Expense Tracking** - Photo receipts → itemized lists and group expense tracking
- 🤖 **Casual Chat Interface** - Ask "when's our flight?" or "what did we spend on food?"
- 📸 **Image OCR** - Extract text from photos automatically
- 💰 **Group Expense Management** - Track who paid what and split costs
- ⚡ **Instant Responses** - Fast webhook-based processing
- 📊 **Google Drive Storage** - All photos backed up to your Drive

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Telegram Bot   │───▶│   FastAPI App   │───▶│  Google Gemini  │
│  (Chat Interface)   │    (Core Logic)     │    (AI Processing) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Google Drive   │◀──▶│   Vector Store  │    │   PostgreSQL    │
│  (File Storage) │    │ (Pinecone/Supabase) │    (Metadata)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

1. **Complete the setup checklist** in `PRE_DEVELOPMENT_CHECKLIST.md`
2. **Follow setup instructions** in `SETUP_INSTRUCTIONS.md`
3. **Configure environment variables** by copying `.env.example` to `.env`

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd telegram-assistant

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Test the setup
python test_setup.py

# Run development server
python main.py
```

### Quick Test

```bash
# Verify everything is working
python test_setup.py

# Start the application
python main.py

# Visit http://localhost:8000 for API docs
```

## 📋 Environment Variables

Required environment variables (see `.env.example` for complete list):

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Google Services
GOOGLE_GEMINI_API_KEY=your_gemini_api_key
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=path/to/service-account.json
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id

# Vector Database (choose one)
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment
# OR
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## 🏗️ Project Structure

```
telegram-assistant/
├── 📁 api/                    # Vercel serverless functions
├── 📁 src/
│   ├── 📁 core/               # Core functionality
│   ├── 📁 models/             # Database models
│   ├── 📁 services/           # External service integrations
│   ├── 📁 processors/         # File processing
│   ├── 📁 ai/                 # AI processing modules
│   ├── 📁 utils/              # Utility functions
│   └── 📁 workflows/          # Business logic workflows
├── 📁 tests/                  # Test suite
├── 📄 main.py                 # FastAPI application
├── 📄 requirements.txt        # Python dependencies
├── 📄 vercel.json            # Vercel deployment config
└── 📄 test_setup.py          # Setup validation script
```

## 💡 How It Works

### 1. Document Processing Pipeline

1. **File Detection** - Monitor Google Drive for new files
2. **Download & Extract** - Retrieve files and extract text/data
3. **AI Analysis** - Use Google Gemini to extract metadata and insights
4. **Vector Storage** - Generate embeddings and store in Pinecone/Supabase
5. **Indexing** - Make content searchable via semantic queries

### 2. Chat Interface

1. **Message Received** - Telegram sends user message to webhook
2. **Context Retrieval** - Search vector database for relevant documents
3. **AI Processing** - Generate response using retrieved context
4. **Memory Management** - Maintain conversation history
5. **Response Delivery** - Send reply back through Telegram

### 3. Supported File Types

- **Documents**: PDF, DOCX, TXT, RTF
- **Spreadsheets**: XLSX, XLS, CSV
- **Images**: JPG, PNG, GIF, WEBP (with OCR)
- **Presentations**: PPTX, PPT

## 🚀 Deployment Options

### Option 1: Vercel (Recommended - $0/month)

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy to Vercel
vercel --prod

# Configure environment variables in Vercel dashboard
```

### Option 2: Railway ($0/month with credits)

```bash
# Connect to Railway
railway login
railway init

# Deploy
railway up
```

### Option 3: Self-Hosted

```bash
# Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000

# Or with gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 📊 Monitoring & Health Checks

### Health Endpoints

- `GET /health` - Basic health check
- `GET /status` - Detailed system status
- `GET /debug/config` - Configuration status (dev only)

### Logging

Logs are structured using Loguru with different levels:

```python
from src.core.logger import get_logger

logger = get_logger(__name__)
logger.info("Processing started")
logger.error("Processing failed", extra={"file_id": "123"})
```

## 🔧 Development

### Running Tests

```bash
# Test setup and configuration
python test_setup.py

# Run unit tests
pytest tests/

# Test specific components
pytest tests/test_telegram_service.py -v
```

### Adding New Features

1. **Create models** in `src/models/`
2. **Add services** in `src/services/`
3. **Implement processors** in `src/processors/`
4. **Create API endpoints** in `api/`
5. **Add tests** in `tests/`

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migration
alembic upgrade head
```

## 🛠️ Troubleshooting

### Common Issues

**Configuration Errors**
```bash
python test_setup.py  # Validates all configuration
```

**Database Issues**
```bash
# Check database health
curl http://localhost:8000/health
```

**Telegram Bot Not Responding**
- Verify bot token in `.env`
- Check webhook URL is accessible
- Ensure chat ID is correct

**Google Drive Access Denied**
- Verify service account JSON file
- Check folder sharing permissions
- Ensure APIs are enabled

### Getting Help

1. **Check logs** - Look for error messages in console/log files
2. **Validate config** - Run `python test_setup.py`
3. **Check documentation** - Review setup instructions
4. **Test endpoints** - Use `/health` and `/status` endpoints

## 📈 Performance & Scaling

### Optimization Tips

- **Use chunking** for large files (configured via `CHUNK_SIZE`)
- **Enable caching** for frequently accessed documents
- **Monitor API limits** for Google Gemini and Pinecone
- **Batch process** multiple files when possible

### Scaling Considerations

- **Serverless**: Automatic scaling with Vercel/Railway
- **Database**: Upgrade to paid tier when needed
- **Vector Storage**: Monitor Pinecone usage and costs
- **API Limits**: Consider rate limiting for heavy usage

## 🔒 Security

### Best Practices

- **Environment Variables** - Never commit API keys
- **Service Accounts** - Use least-privilege permissions
- **Input Validation** - All user inputs are validated
- **Error Handling** - Sensitive data not exposed in errors
- **HTTPS Only** - All webhook endpoints use HTTPS

## 📚 Documentation

- **Setup Guide**: `SETUP_INSTRUCTIONS.md`
- **Pre-Development Checklist**: `PRE_DEVELOPMENT_CHECKLIST.md`
- **Project Structure**: `PROJECT_STRUCTURE.md`
- **API Documentation**: Available at `/docs` when running

## 🎯 Roadmap

- [ ] **Web Interface** - Browser-based chat interface
- [ ] **Multi-user Support** - Support multiple Telegram users
- [ ] **Advanced Analytics** - Document processing insights
- [ ] **Plugin System** - Extensible processing modules
- [ ] **Real-time Sync** - Live Google Drive synchronization

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit changes** (`git commit -m 'Add amazing feature'`)
4. **Push to branch** (`git push origin feature/amazing-feature`)
5. **Open Pull Request**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **n8n** - Original workflow inspiration
- **FastAPI** - Modern Python web framework
- **Google Gemini** - AI language model
- **Pinecone** - Vector database
- **Vercel** - Serverless hosting platform

---

**🎉 Ready to build your AI assistant? Follow the setup guide and start processing documents with AI power!**