# 🚀 Setup Instructions - Telegram Assistant

## Prerequisites Setup Guide

Complete these steps **BEFORE** starting development. This guide will walk you through creating all necessary accounts and obtaining API keys.

---

## 📋 Checklist Overview

Before you begin, you'll need accounts and API keys from these services:

- [ ] **Telegram Bot** - For chat interface
- [ ] **Google AI Studio** - For Gemini AI processing
- [ ] **Google Cloud Console** - For Drive/Docs API access
- [ ] **Pinecone** - For vector storage (Option A)
- [ ] **Supabase** - For database (and optional vector storage)
- [ ] **Vercel** - For free hosting
- [ ] **Cloudinary** - For image processing (optional)

**Estimated Setup Time: 30-45 minutes**

---

## 🤖 Step 1: Create Telegram Bot

### 1.1 Create Bot with BotFather
1. Open Telegram and search for `@BotFather`
2. Start a conversation and send `/newbot`
3. Choose a name for your bot (e.g., "My Nostr Assistant")
4. Choose a username ending in 'bot' (e.g., "my_nostr_assistant_bot")
5. **Copy the bot token** - you'll need this for `TELEGRAM_BOT_TOKEN`

### 1.2 Get Your Chat ID
1. Send a message to your newly created bot
2. Visit this URL in your browser (replace `<BOT_TOKEN>` with your actual token):
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id":NUMBERS}` in the response
4. **Copy the chat ID number** - you'll need this for `TELEGRAM_CHAT_ID`

### 1.3 Configure Bot Settings (Optional)
```
/setdescription - Set a description for your bot
/setabouttext - Set about text
/setuserpic - Set profile picture
```

---

## 🧠 Step 2: Google AI Studio (Gemini)

### 2.1 Get Gemini API Key
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. **Copy the API key** - you'll need this for `GOOGLE_GEMINI_API_KEY`

### 2.2 Test API Access
You can test your key with this curl command:
```bash
curl -H 'Content-Type: application/json' \
     -d '{"contents":[{"parts":[{"text":"Hello"}]}]}' \
     -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=YOUR_API_KEY"
```

---

## ☁️ Step 3: Google Cloud Console Setup

### 3.1 Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "New Project"
3. Name your project (e.g., "telegram-assistant")
4. Click "Create"

### 3.2 Enable Required APIs
1. In the console, go to "APIs & Services" > "Library"
2. Search and enable these APIs:
   - **Google Drive API**
   - **Google Docs API**
   - **Google Sheets API** (for Excel processing)

### 3.3 Create Service Account
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Enter details:
   - **Service account name**: `telegram-assistant-service`
   - **Description**: `Service account for Telegram Assistant app`
4. Click "Create and Continue"
5. Skip role assignment for now, click "Continue"
6. Click "Done"

### 3.4 Generate Service Account Key
1. Click on your newly created service account
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose "JSON" format
5. **Download the JSON file** - you'll need this file path for `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`
6. **Keep this file secure!** Never commit it to git.

### 3.5 Setup Google Drive Access
1. Create a folder in Google Drive for file processing
2. Right-click the folder > "Share"
3. Add your service account email (found in the JSON file) with "Editor" permissions
4. **Copy the folder ID** from the URL - you'll need this for `GOOGLE_DRIVE_FOLDER_ID`
   ```
   https://drive.google.com/drive/folders/FOLDER_ID_HERE
   ```

### 3.6 Setup Google Docs (Optional)
1. Create a Google Doc for chat history logging
2. Share it with your service account email (Editor permissions)
3. **Copy the document ID** from the URL - you'll need this for `GOOGLE_DOCS_HISTORY_ID`
   ```
   https://docs.google.com/document/d/DOCUMENT_ID_HERE/edit
   ```

---

## 🗂️ Step 4: Vector Database Setup

### Option A: Pinecone (Matches Original Workflow)

#### 4.1 Create Pinecone Account
1. Go to [Pinecone](https://app.pinecone.io/)
2. Sign up for free account
3. Verify your email

#### 4.2 Create Index
1. Click "Create Index"
2. **Index name**: `wheeey` (to match original workflow)
3. **Dimensions**: `768` (for Google Gemini embeddings)
4. **Metric**: `cosine`
5. **Environment**: Note this down for `PINECONE_ENVIRONMENT`
6. Click "Create Index"

#### 4.3 Get API Key
1. Go to "API Keys" in Pinecone dashboard
2. **Copy your API key** - you'll need this for `PINECONE_API_KEY`

### Option B: Supabase (All-in-One Alternative)

#### 4.1 Create Supabase Account
1. Go to [Supabase](https://supabase.com/)
2. Sign up with GitHub (recommended)
3. Create new project:
   - **Name**: `telegram-assistant`
   - **Password**: Generate strong password
   - **Region**: Choose closest to you

#### 4.2 Enable Vector Extension
1. Go to SQL Editor in your Supabase dashboard
2. Run this command to enable vector extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

#### 4.3 Get Connection Details
1. Go to Settings > Database
2. **Copy the connection string** - you'll need this for `DATABASE_URL`
3. Go to Settings > API
4. **Copy the URL** - you'll need this for `SUPABASE_URL`
5. **Copy the anon key** - you'll need this for `SUPABASE_KEY`

---

## 🚀 Step 5: Hosting Setup (Vercel)

### 5.1 Create Vercel Account
1. Go to [Vercel](https://vercel.com/)
2. Sign up with GitHub
3. Install Vercel CLI (optional):
   ```bash
   npm i -g vercel
   ```

### 5.2 Connect GitHub Repository
1. Create a GitHub repository for your project
2. In Vercel dashboard, click "New Project"
3. Import your GitHub repository
4. **Don't deploy yet** - we'll do this after coding

---

## 🖼️ Step 6: Optional Services

### Cloudinary (for advanced image processing)
1. Go to [Cloudinary](https://cloudinary.com/)
2. Sign up for free account
3. Go to Dashboard
4. **Copy these values**:
   - Cloud name → `CLOUDINARY_CLOUD_NAME`
   - API Key → `CLOUDINARY_API_KEY`
   - API Secret → `CLOUDINARY_API_SECRET`

---

## 🔧 Step 7: Configure Environment Variables

### 7.1 Copy Environment Template
```bash
cp .env.example .env
```

### 7.2 Fill in Your Values
Open `.env` and replace all placeholder values with the actual keys and IDs you collected:

```env
# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIjKlMnOpQrStUvWxYz
TELEGRAM_CHAT_ID=123456789

# Google Services
GOOGLE_GEMINI_API_KEY=AIzaSyA...
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=./path/to/service-account-key.json
GOOGLE_DRIVE_FOLDER_ID=1BxiMVs0XRA5nFMdKvBdBZjgm...

# Vector Database (choose one)
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=us-east1-aws
PINECONE_INDEX_NAME=wheeey

# OR Supabase
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 7.3 Secure Your Credentials
```bash
# Add .env to gitignore (if not already there)
echo ".env" >> .gitignore
echo "*.json" >> .gitignore  # For service account files
```

---

## ✅ Verification Checklist

Before proceeding to development, verify you have:

### Required Credentials
- [ ] `TELEGRAM_BOT_TOKEN` - Bot responds to messages
- [ ] `TELEGRAM_CHAT_ID` - You can receive messages
- [ ] `GOOGLE_GEMINI_API_KEY` - AI API is accessible
- [ ] `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` - File exists and readable
- [ ] `GOOGLE_DRIVE_FOLDER_ID` - Service account can access folder
- [ ] Vector database credentials (Pinecone OR Supabase)

### Permissions Test
- [ ] Send message to your bot (should receive it)
- [ ] Upload file to Google Drive folder
- [ ] Service account can read/write to Google Drive folder
- [ ] Service account can edit Google Doc (if using)

### Optional Verifications
- [ ] Cloudinary dashboard accessible (if using)
- [ ] Vercel account connected to GitHub
- [ ] All environment variables set in `.env`

---

## 🎯 Next Steps

Once you've completed all steps:

1. **Verify all API keys work** by testing them individually
2. **Commit your project structure** to GitHub (without `.env` file!)
3. **Ready for development** - you can now proceed with coding

---

## ⚠️ Security Notes

- **Never commit `.env` files** to version control
- **Keep service account JSON files secure** - they provide full access to your Google services
- **Use strong passwords** for all accounts
- **Enable 2FA** where available
- **Regular key rotation** for production use

---

## 🆘 Troubleshooting

### Common Issues

**Telegram bot not responding:**
- Check bot token is correct
- Ensure bot is not blocked
- Verify chat ID is correct

**Google API access denied:**
- Ensure APIs are enabled in Google Cloud Console
- Check service account permissions
- Verify JSON file path is correct

**Pinecone connection failed:**
- Check API key and environment
- Ensure index exists and dimensions match

**Supabase connection failed:**
- Verify URL and key are correct
- Check database is not paused (free tier auto-pauses)

### Getting Help

If you encounter issues:
1. Check the error messages carefully
2. Verify all credentials are correct
3. Test each service individually
4. Check service status pages for outages
5. Consult the official documentation for each service

---

## 📚 Useful Links

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Google AI Studio](https://makersuite.google.com/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [Supabase Documentation](https://supabase.com/docs)
- [Vercel Documentation](https://vercel.com/docs)

---

**🎉 You're all set! Once you complete these steps, we can start building the application.**