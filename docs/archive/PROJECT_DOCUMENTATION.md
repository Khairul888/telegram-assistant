# Nostr User Profile Assistant - Custom FastAPI Implementation

## Project Overview

This project is a **custom FastAPI application** that replicates and enhances the functionality of an n8n workflow for analyzing and querying Nostr user profiles. By building a custom implementation instead of deploying n8n, we achieve **zero hosting costs** through serverless deployment while maintaining all the original functionality.

### Why Custom Implementation Over n8n?

**Cost Benefits:**
- **n8n Deployment**: $120-400/month (requires persistent server)
- **Custom FastAPI**: $0/month (serverless functions only)
- **Savings**: 100% cost reduction

**Performance Benefits:**
- Direct API integrations (no n8n overhead)
- Faster cold starts and response times
- Custom error handling and logging
- Full control over processing logic

### Core Architecture: Dual System Design

**System 1: Document Processing & Vector Storage Pipeline**
- Batch processes files from Google Drive (documents, images, Excel files)
- Extracts insights using AI and stores them as searchable vectors
- Includes safety approval workflows via Telegram

**System 2: Intelligent Chat Interface**
- Provides conversational access to processed documents
- Uses semantic search to retrieve relevant information
- Maintains conversation context and history

### Primary Functions

1. **Automated Document Processing**: Processes files from Google Drive with support for text documents, images (OCR/Vision), and Excel files
2. **AI-Powered Content Analysis**: Extracts structured metadata including themes, pain points, insights, and keywords using Google Gemini
3. **Vector Database Management**: Stores and manages document embeddings in Pinecone for semantic search capabilities
4. **Conversational AI Interface**: Telegram-based chat bot with 40-message memory window for natural language queries
5. **Safety & Approval Systems**: Telegram-based confirmation workflows for data operations
6. **Real-time Processing**: Supports both manual triggers and webhook-based automation

## Core Technologies Used

### Backend Framework
- **FastAPI**: Modern, fast Python web framework for building APIs
- **Python 3.9+**: Core programming language
- **Async/Await**: Non-blocking operations for better performance

### AI/ML Services
- **Google Gemini 2.0 Flash (Experimental)**: Primary language model for text analysis and chat interactions
  - Model: `models/gemini-2.0-flash-exp`
  - Temperature: 0.4 for analysis, max 8192 output tokens for chat
- **Google Gemini Embeddings**: Vector embeddings for semantic search and document similarity

### Vector Database
- **Pinecone**: Cloud-native vector database for storing and querying document embeddings
  - Index: "wheeey"
  - Used for semantic similarity search and retrieval

### Cloud Storage & Document Management
- **Google Drive API**: File storage and management
- **Google Docs API**: Chat history logging and documentation
- **File Processing**: Supports various document formats with automatic text extraction

### Communication Platform
- **Telegram Bot API**: Real-time chat interface and notification system
- **Webhook Integration**: Supports both webhook triggers and manual testing

### Data Processing
- **LangChain Framework**: Document processing, text splitting, and AI agent orchestration
- **Token Splitter**: Chunks documents into 3000-token segments for processing
- **Information Extractor**: Structured data extraction from unstructured text
- **Multi-format Support**: Handles text documents, images (with OCR/Vision), and Excel files
- **Spreadsheet Processing**: Extracts and structures data from Excel/CSV files

## Required APIs and Keys

### Essential API Credentials

1. **Google Gemini (PaLM) API**
   - **Purpose**: Language model for text analysis and chat functionality
   - **Credential ID**: `TleJsX0UscivoXop`
   - **Configuration**: Access to Gemini 2.0 Flash experimental model
   - **Obtain From**: [Google AI Studio](https://makersuite.google.com/app/apikey)

2. **Google Drive OAuth2 API**
   - **Purpose**: File access, download, and document management
   - **Credential ID**: `84MeXEXZiQnCE6Xy`
   - **Scopes**: Drive file access, folder enumeration
   - **Setup**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

3. **Telegram Bot API**
   - **Purpose**: Chat interface and notification system
   - **Credential ID**: `8k97Iy99lPSuch8Z`
   - **Setup**: Create bot via [@BotFather](https://t.me/botfather) on Telegram

4. **Pinecone API**
   - **Purpose**: Vector database for semantic search
   - **Credential ID**: `RtZwEVtSQhcnYFNw`
   - **Index**: "wheeey"
   - **Setup**: [Pinecone Console](https://app.pinecone.io/)

### Environment Variables Required

```bash
# Core Configuration
TELEGRAM_CHAT_ID=<your_telegram_chat_id>

# Optional Enhancements (for automatic trigger modifications)
GOOGLE_DRIVE_WEBHOOK_URL=<your_n8n_webhook_url>
PROCESSING_NOTIFICATION_ENABLED=true
```

### Configuration Parameters

- **Google Drive Folder ID**: `[Your-Google-Folder-ID]` - Must be configured for document source
- **Qdrant Collection Name**: `nostr-damus-user-profiles` - Vector store collection identifier
- **Google Docs Document ID**: `1ej_qLolUFp1h4eZkrb99T3DWQ3JOwXVEMS3VUjWyVf0` - For chat history logging

## Hosting and Deployment Guide

### Prerequisites

1. **n8n Installation**
   ```bash
   # Via npm (recommended)
   npm install -g n8n

   # Via Docker
   docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n
   ```

2. **Required Node Packages**
   - `@n8n/n8n-nodes-langchain` - LangChain integration nodes
   - Standard n8n base nodes (included by default)

### Deployment Options

#### 1. Vercel Serverless (Recommended - $0/month)

**System Requirements**:
- Python 3.9+
- Git for version control
- Internet connection for API calls
- No persistent server needed

**Benefits**:
- Zero cost hosting
- Automatic HTTPS and SSL
- Global CDN distribution
- Automatic scaling
- No server maintenance

#### 2. Railway (Alternative - $0/month with credits)

**Configuration**:
```python
# Single FastAPI application
# Covered by $5 monthly credit
# Always-on availability
# Built-in PostgreSQL option
```

#### 3. Alternative Free Hosting

- **Fly.io**: 160 hours/month free
- **Render**: 750 hours/month free
- **Netlify Functions**: 125k requests/month free
- **Railway**: $5 monthly credit (effectively free)

### Post-Deployment Configuration

1. **Environment Variables**:
   - Configure all API keys in hosting platform
   - Set up webhook URLs for Telegram and Google Drive
   - Configure database connections

2. **API Key Verification**:
   - Test all external service connections
   - Verify Telegram bot is responding
   - Confirm Google Drive access permissions

3. **Webhook Setup**:
   - Register Telegram webhook URL
   - Configure Google Drive push notifications
   - Test end-to-end functionality

## Detailed Workflow Architecture

### System 1: Document Processing Pipeline

#### Entry Points & Triggers
- **Manual Testing Trigger**: `When clicking 'Test workflow'` - Used for development and testing
- **Webhook Trigger**: HTTP endpoint at `/upsert` path (currently disabled)
- **Future Enhancement**: Google Drive webhook trigger for automatic file detection

#### Document Processing Flow

**Step 1: Configuration & File Discovery**
```
Google Folder ID → Find File Ids in Google Drive Folder
```
- Sets Google Drive folder ID: `[Your-Google-Folder-ID]`
- Scans specified folder for all files
- Returns list of file IDs and metadata

**Step 2: File Processing Loop**
```
File List → Loop Over Items → Download File → Extract Content
```
- **Loop Over Items**: Processes files one by one in batches
- **Download File From Google Drive**: Downloads each file using Google Drive API
- **Get File Contents**: Extracts text content from downloaded files

**Step 3: AI Analysis & Metadata Extraction**
```
File Content → Extract Meta Data → Merge with File Info
```
- **Extract Meta Data**: Uses Google Gemini 2.0 Flash to analyze content
- Extracts structured data:
  - `overarching_theme`: Main topics discussed
  - `recurring_topics`: Common threads as array
  - `pain_points`: User frustrations/challenges
  - `analytical_insights`: Key observations and behavior shifts
  - `conclusion`: Summary of findings
  - `keywords`: 10 relevant keywords

**Step 4: Document Preparation & Vector Storage**
```
Merged Data → Token Splitter → Data Loader → Pinecone Vector Storage
```
- **Token Splitter**: Chunks text into 3000-token segments
- **Data Loader**: Prepares documents with metadata for embedding
- **Pinecone Vector Store**: Stores embeddings in "wheeey" index

#### Safety & Approval System
```
Qdrant Collection Name → File Id List → Merge → Telegram Approval → Conditional Processing
```
- **File Id List**: Aggregates all file IDs to be processed
- **Confirm Qdrant Delete Points**: Sends Telegram message asking for approval
- **If Statement**: Checks if user approved the operation
- **Send Declined/Completed Message**: Notifies user of operation status

### System 2: AI Chat Interface

#### Chat Trigger & Memory Management
```
When chat message received → AI Agent (with Memory & Tools)
```
- **Chat Trigger**: Webhook endpoint for receiving chat messages
- **Window Buffer Memory**: Maintains conversation context (40 message window)
- **Google Gemini Chat Model**: Powers conversational AI (max 8192 output tokens)

#### AI Agent Capabilities

**Vector Search Tool**:
- **Pinecone Vector Store**: Searches through stored documents using semantic similarity
- **Embeddings Google Gemini**: Converts queries to vector embeddings
- Tool description: "Find the most appropriate content to use as context"

**AI Agent System Prompt**:
```
You are an intelligent assistant specialized in answering user questions using Nostr user profiles.
Use the "nostr_damus_user_profiles" tool to perform semantic similarity searches
and retrieve information from Nostr user profiles relevant to the user's query.
```

#### Response & Logging System
```
AI Agent → Update Chat History + Respond to User
```
- **Update Chat History**: Logs conversation to Google Docs (ID: `1ej_qLolUFp1h4eZkrb99T3DWQ3JOwXVEMS3VUjWyVf0`)
- **Respond to User**: Sends response back through chat interface
- **Optional File Storage**: Can save responses to Google Drive (currently disabled)

### Key Data Flow Patterns

1. **Document Processing Pattern**:
   ```
   Manual Trigger → Google Drive Files → AI Analysis → Vector Storage → Telegram Notification
   ```

2. **Chat Interaction Pattern**:
   ```
   Chat Message → Vector Search → AI Response → History Logging → User Response
   ```

3. **Approval Pattern**:
   ```
   File Operations → Telegram Approval Request → User Decision → Execute/Cancel → Notification
   ```

### Technical Storage Architecture

- **Pinecone "wheeey" Index**: Vector embeddings and semantic search
- **Google Drive**: File storage and management
- **Google Docs**: Chat history persistence
- **Qdrant Collection**: `nostr-damus-user-profiles` (referenced but not actively used)

### AI Models Configuration

- **Google Gemini 2.0 Flash Experimental**: Primary language model
  - Analysis tasks: Temperature 0.4
  - Chat tasks: Max 8192 output tokens
- **Google Gemini Embeddings**: Vector generation for semantic search
- **Alternative Model**: OpenAI GPT-4o-mini (currently disabled)

### Security Considerations

- All API keys stored securely in n8n credentials manager
- Webhook endpoints should use HTTPS in production
- Telegram bot token provides access control
- Google OAuth provides secure file access
- Regular backup of workflow configuration recommended

### Monitoring and Maintenance

- Monitor API rate limits (especially Google Gemini)
- Regular cleanup of vector store if needed
- Backup chat history and workflow configurations
- Monitor Pinecone usage and costs
- Update model versions when available

## Planned Enhancements

### Automatic Google Drive Trigger (Proposed)

To enable real-time processing of new files, the following modifications are planned:

#### New Google Drive Webhook Trigger
```json
{
  "name": "Google Drive File Added Trigger",
  "type": "n8n-nodes-base.googleDriveTrigger",
  "parameters": {
    "event": "fileCreated",
    "folderId": "[Your-Google-Folder-ID]",
    "options": {
      "fileTypes": ["image/png", "image/jpeg", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
    }
  }
}
```

#### Enhanced File Type Processing

**Image Processing Branch**:
- **Gemini Vision API**: OCR and visual content analysis
- **Text Extraction**: Convert images to searchable text
- **Visual Element Description**: AI-generated descriptions of visual content

**Excel Processing Branch**:
- **Data Extraction**: Structured data extraction from spreadsheets
- **Format Conversion**: Convert tabular data to searchable text format
- **Schema Analysis**: Identify column structures and data types

#### Universal Metadata Extraction
```json
{
  "attributes": [
    {"name": "file_type", "description": "Type of file processed (image, excel, document)"},
    {"name": "content_summary", "description": "Brief summary of the file content"},
    {"name": "key_data_points", "description": "Important data, numbers, or information extracted"},
    {"name": "visual_elements", "description": "For images: description of visual content"},
    {"name": "data_structure", "description": "For Excel: description of data organization"}
  ]
}
```

### Additional API Requirements for Enhancements

1. **Google Drive Push Notifications**
   - Webhook endpoint configuration
   - Domain verification for real-time triggers

2. **Enhanced Gemini Vision API**
   - Image analysis and OCR capabilities
   - May require API tier upgrade

## Use Cases and Applications

### Current Capabilities
- **Nostr Community Analysis**: Understanding user behaviors and trends from text documents
- **Content Research**: Semantic search across processed user profiles
- **Community Management**: Identifying pain points and insights through AI analysis
- **Research Assistant**: Automated analysis of social media profiles and documents
- **Conversational Knowledge Base**: Natural language queries against stored information

### Enhanced Capabilities (with proposed modifications)
- **Visual Content Analysis**: Process screenshots, charts, and images from Nostr
- **Data Analytics**: Analyze Excel reports and spreadsheets about user metrics
- **Real-time Processing**: Automatic ingestion of new files as they're added
- **Multi-format Intelligence**: Unified search across text, visual, and tabular data
- **Comprehensive Profiling**: Combine multiple data sources for complete user analysis

## Project Summary

This project represents a sophisticated "knowledge ingestion and retrieval system" that combines:

1. **Automated Document Processing**: Batch or real-time processing of multiple file formats
2. **AI-Powered Analysis**: Advanced content extraction and insight generation
3. **Semantic Search**: Vector-based similarity search for relevant information retrieval
4. **Conversational Interface**: Natural language interaction with processed knowledge
5. **Safety Controls**: Approval workflows and notification systems
6. **Extensible Architecture**: Designed for easy enhancement with new file types and AI capabilities

The dual-system architecture ensures continuous knowledge accumulation while providing immediate access through conversational AI, making it ideal for research, community management, and analytical applications in the Nostr ecosystem.