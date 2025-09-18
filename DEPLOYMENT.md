# 🚀 Telegram Assistant - Vercel Deployment Guide

Deploy your Telegram Assistant to Vercel for **$0/month hosting** and replace your n8n workflow.

## 📋 Pre-deployment Checklist

- ✅ Local application tested and working
- ✅ `vercel.json` configuration created
- ✅ `requirements.txt` dependencies ready
- ⬜ Vercel account created
- ⬜ Environment variables configured

## 🔧 Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

## 🌐 Step 2: Deploy to Vercel

1. **Login to Vercel**
   ```bash
   vercel login
   ```

2. **Deploy the Application**
   ```bash
   cd C:\Users\khair\Personal_Projects\Telegram_Assistant
   vercel
   ```

3. **Follow the prompts:**
   - Project name: `telegram-assistant` (or your preferred name)
   - Framework: `Other`
   - Source code location: `./` (current directory)

## 🔐 Step 3: Configure Environment Variables

### In Vercel Dashboard:

1. Go to your project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add the following variables:

#### **Required Variables:**

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=8437973822:AAHhR1UEXTLEGqWsMfYI6AUl9oiO9ovrSs0
TELEGRAM_CHAT_ID=1316304260

# Google AI Configuration
GOOGLE_GEMINI_API_KEY=AIzaSyCc2EN8eVF_jXboSyC_bLc2JoH1xD3EMpA

# Vector Database
PINECONE_API_KEY=pcsk_3h2WXW_66qtNp8FhiciVUCaeJM4dUX4MASXPRuyq722TS21eA7CtYBtwQk4b6BKyX5LDke
PINECONE_ENVIRONMENT=us-east1-aws
PINECONE_INDEX_NAME=wheeey

# Application Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
DATABASE_URL=sqlite+aiosqlite:///./telegram_assistant.db

# File Processing
MAX_FILE_SIZE_MB=50
SUPPORTED_FILE_TYPES=["pdf","docx","txt","jpg","jpeg","png","xlsx","csv"]
CHUNK_SIZE=3000
CHUNK_OVERLAP=200
MAX_TOKENS_PER_REQUEST=8192
AI_TEMPERATURE=0.4

# Memory Settings
MEMORY_WINDOW_SIZE=40
MEMORY_CLEANUP_DAYS=30
```

#### **Production URLs (Update after deployment):**

```bash
# Update these with your actual Vercel deployment URL
APP_BASE_URL=https://your-app-name.vercel.app
TELEGRAM_WEBHOOK_URL=https://your-app-name.vercel.app/api/telegram-webhook
GOOGLE_DRIVE_WEBHOOK_URL=https://your-app-name.vercel.app/api/drive-webhook
```

#### **Optional Variables:**

```bash
# Google Drive Integration (Optional)
GOOGLE_DRIVE_FOLDER_ID=https://drive.google.com/drive/folders/1mkSfXU2li9KPTp0eENhSgmPbb-EinFJI
GOOGLE_DOCS_HISTORY_ID=your_google_docs_document_id_here
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=Users\khair\Personal_Projects\telegram-assistant-472511-434f4b2f266f

# Development Settings
DEBUG=False
SKIP_WEBHOOK_VERIFICATION=False
USE_MOCK_RESPONSES=False
```

## 🔗 Step 4: Configure Telegram Webhook

After deployment, set up your Telegram webhook:

### Option A: Using curl

```bash
curl -X POST "https://api.telegram.org/bot8437973822:AAHhR1UEXTLEGqWsMfYI6AUl9oiO9ovrSs0/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://your-app-name.vercel.app/api/telegram-webhook",
       "allowed_updates": ["message", "callback_query"]
     }'
```

### Option B: Using your deployed endpoint

Visit: `https://your-app-name.vercel.app/api/telegram-webhook/setup`

## 🧪 Step 5: Test Your Deployment

1. **Check application health:**
   ```
   https://your-app-name.vercel.app/health
   ```

2. **Test Telegram bot:**
   - Send `/start` to your bot
   - Send `/help` for available commands
   - Upload a test document

3. **Monitor logs:**
   ```bash
   vercel logs
   ```

## 🔄 Step 6: Update Deployment

For future updates:

```bash
vercel --prod
```

## 🚨 Troubleshooting

### Common Issues:

1. **Environment Variables Not Working:**
   - Ensure variables are set in Vercel dashboard
   - Redeploy after adding variables

2. **Telegram Webhook Fails:**
   - Check webhook URL is correct
   - Verify bot token is valid
   - Check Vercel function logs

3. **Database Issues:**
   - SQLite works for development
   - Consider upgrading to PostgreSQL for production

4. **File Upload Limits:**
   - Vercel has 50MB limit for serverless functions
   - Large files may need external storage

### Debug Endpoints:

- **Health Check:** `/health`
- **Status:** `/status`
- **API Docs:** `/docs`
- **Webhook Info:** `/api/telegram-webhook`

## 🎯 Success Metrics

Your deployment is successful when:

- ✅ Health check returns `200 OK`
- ✅ Telegram webhook responds to messages
- ✅ File uploads are processed
- ✅ AI responses are generated
- ✅ No errors in Vercel logs

## 💰 Cost Optimization

**Vercel Free Tier Limits:**
- 100GB bandwidth/month
- 100 serverless function invocations/day
- 10 second function timeout

**Tips:**
- Monitor usage in Vercel dashboard
- Optimize function cold start times
- Use caching for repeated requests

---

🎉 **Congratulations!** Your Telegram Assistant is now deployed and replaces your n8n workflow at $0/month cost!