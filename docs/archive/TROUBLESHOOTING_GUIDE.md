# Telegram Bot Deployment Troubleshooting Guide

## Overview

This document chronicles the complete troubleshooting process for deploying a Telegram bot on Vercel serverless functions. The bot was initially configured but completely unresponsive to messages, requiring systematic debugging to identify and resolve the root cause.

## Initial Problem

**Symptom**: Telegram bot deployed on Vercel but completely unresponsive to user messages
- No responses to any messages
- No visible errors to end users
- Bot appeared "online" but silent

## Systematic Troubleshooting Approach

### 1. Configuration Verification (✅ PASSED)

**What we checked:**
- Environment variables configuration
- API keys and tokens
- Basic project setup

**Method:**
```bash
python src/core/config.py
```

**Result:** All required services were properly configured:
- Telegram Bot Token: ✅
- Google Gemini API: ✅
- Pinecone Vector DB: ✅
- Google Drive: ✅

**Key Learning:** Always verify configuration first, but don't assume this is the issue if validation passes.

### 2. Webhook Status Investigation (🔍 REVEALED ISSUE)

**What we discovered:**
```bash
python simple_webhook_check.py
```

**Critical findings:**
- Webhook URL: Not set initially (empty)
- Pending Updates: 8 messages waiting
- Last Error: "Wrong response from the webhook: 500 Internal Server Error"

**Key Learning:** Telegram's webhook status provides crucial diagnostic information:
- `pending_update_count` shows messages waiting to be delivered
- `last_error_message` reveals specific webhook failures
- Empty URL means webhook was never properly configured

### 3. Deployment Testing (❌ FAILED)

**What we tested:**
```bash
curl -X GET "https://telegram-assistant-three.vercel.app/api/telegram-webhook"
```

**Result:** `FUNCTION_INVOCATION_FAILED` error

**Multiple endpoint attempts:**
- `api/telegram-webhook.py` (FastAPI + complex imports)
- `api/telegram-webhook-simple.py` (simplified with httpx)
- `api/telegram-webhook-minimal.py` (only stdlib)
- All returned identical `FUNCTION_INVOCATION_FAILED`

**Key Learning:** When all variations of code fail identically, the issue is likely infrastructure/configuration, not code logic.

### 4. Requirements Debugging (❌ NOT THE ISSUE)

**Hypothesis:** Complex dependencies causing import failures

**Actions taken:**
- Simplified `requirements.txt` from 15+ packages to just 3
- Removed requirements.txt entirely
- Still got `FUNCTION_INVOCATION_FAILED`

**Key Learning:** Don't assume dependency issues when the error is consistent across all code variations.

### 5. Handler Format Discovery (🎯 ROOT CAUSE FOUND)

**Critical test:** Created ultra-simple handler
```python
# api/hello.py
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write('Hello, World!'.encode('utf-8'))
```

**Result:** ✅ **SUCCESS!** This worked perfectly.

**Root Cause Identified:** Vercel's Python runtime requires `BaseHTTPRequestHandler` class format, not:
- Function-based handlers
- FastAPI + Mangum combinations
- Standard serverless function patterns

### 6. Environment Variable Verification (✅ CONFIRMED)

**Diagnostic endpoint created:**
```python
# api/debug.py - Check production environment
debug_info = {
    "TELEGRAM_BOT_TOKEN": "SET" if bot_token else "MISSING",
    "TELEGRAM_BOT_TOKEN_LENGTH": len(bot_token) if bot_token else 0,
    # ... other checks
}
```

**Result:** All environment variables properly available in production:
- `TELEGRAM_BOT_TOKEN`: SET (46 characters)
- `TELEGRAM_CHAT_ID`: SET
- `GOOGLE_GEMINI_API_KEY`: SET

### 7. Webhook Data Capture (🔍 CONFIRMED RECEIPT)

**Method:** Set webhook to debug endpoint and monitored logs
```bash
vercel logs https://telegram-assistant-three.vercel.app
```

**Findings:**
- Telegram successfully sending POST requests
- Webhook receiving messages correctly
- Issue was lack of response functionality, not reception

## Final Solution

### Working Bot Implementation

**Correct Vercel handler format:**
```python
from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # Parse JSON and extract message
        update = json.loads(post_data.decode('utf-8'))
        message_info = self.extract_message_info(update)

        # Send response to user
        if message_info:
            self.send_telegram_response(message_info)

        # Acknowledge to Telegram
        self.send_response(200)
        # ... rest of implementation
```

**Key components:**
1. **BaseHTTPRequestHandler class** (mandatory for Vercel)
2. **POST method handling** (Telegram sends POST requests)
3. **JSON parsing** (extract message data)
4. **Telegram API response** (send messages back)
5. **Error handling** (always return 200 to Telegram)

## Critical Lessons Learned

### 1. Vercel-Specific Requirements

**Vercel Python Runtime Constraints:**
- Must use `BaseHTTPRequestHandler` class format
- Function-based handlers don't work
- FastAPI + Mangum combinations fail
- Standard library approach is most reliable

**Deployment Protection:**
- Non-production URLs require authentication
- Only production domain (`telegram-assistant-three.vercel.app`) is publicly accessible
- Testing must use production domain

### 2. Telegram Webhook Behavior

**Webhook Status Diagnostics:**
- `pending_update_count`: Shows queued messages
- `last_error_date` + `last_error_message`: Specific failure details
- Empty URL means webhook never configured

**Message Flow:**
- Telegram sends POST requests with JSON payload
- Webhook must return 200 status code
- Failed webhooks result in message queuing
- Telegram stops delivering after persistent failures

### 3. Debugging Methodology

**Effective Troubleshooting Order:**
1. Configuration verification (but don't stop here)
2. Webhook status investigation
3. Infrastructure testing (handler format)
4. Environment variable verification
5. Message flow confirmation
6. Response functionality implementation

**Common Pitfalls:**
- Assuming dependency issues when error is consistent
- Testing with wrong request methods (GET vs POST)
- Not checking actual production environment variables
- Overlooking platform-specific handler requirements

### 4. Environment Variable Management

**Vercel Environment Variables:**
- Set in Vercel dashboard under project settings
- Available in production runtime via `os.getenv()`
- Can be verified with diagnostic endpoints
- Different from local `.env` files

### 5. Error Interpretation

**`FUNCTION_INVOCATION_FAILED` means:**
- Handler function not found or not callable
- Wrong handler format for the platform
- Import failures preventing function loading
- NOT necessarily dependency or code logic issues

**Webhook "500 Internal Server Error" means:**
- Function started but crashed during execution
- Different from `FUNCTION_INVOCATION_FAILED`
- Check logs for specific error details

## Best Practices for Future Deployments

### 1. Platform-Specific Testing

**Always test handler format first:**
```python
# Minimal test to verify platform requirements
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write('Test successful'.encode('utf-8'))
```

### 2. Progressive Enhancement

**Build complexity gradually:**
1. Basic handler (verify platform compatibility)
2. Add JSON parsing (verify request handling)
3. Add environment variable access (verify configuration)
4. Add external API calls (verify connectivity)
5. Add full business logic (verify functionality)

### 3. Diagnostic Infrastructure

**Always include debug endpoints:**
```python
# Environment variable checker
# Webhook data inspector
# Health status reporter
```

### 4. Webhook Configuration Management

**Webhook URL management:**
- Use production domains for webhooks
- Test endpoint availability before setting webhook
- Monitor webhook status regularly
- Have rollback plan for webhook failures

### 5. Error Handling Strategy

**For Telegram webhooks:**
- Always return 200 status to Telegram (prevent retries)
- Log errors internally for debugging
- Implement graceful degradation
- Handle malformed requests safely

## Tools and Commands Reference

### Webhook Management
```bash
# Check webhook status
python simple_webhook_check.py

# Set webhook URL
python simple_webhook_check.py set "https://domain.com/api/webhook"

# Delete webhook (switch to polling)
python simple_webhook_check.py delete
```

### Vercel Deployment
```bash
# List deployments
vercel ls

# Check logs (replace with actual deployment URL)
vercel logs https://deployment-url.vercel.app

# Deploy current directory
vercel --prod
```

### Testing Endpoints
```bash
# Test GET request
curl -X GET "https://domain.com/api/endpoint"

# Test POST with JSON (simulate Telegram)
curl -X POST "https://domain.com/api/webhook" \
  -H "Content-Type: application/json" \
  -d '{"message":{"chat":{"id":123},"text":"test"}}'
```

### Configuration Validation
```bash
# Check local configuration
python src/core/config.py

# Test environment variable availability
curl "https://domain.com/api/debug"
```

## Summary

This troubleshooting session revealed that serverless platform requirements can be highly specific and may not follow standard patterns. The key breakthrough was understanding that Vercel's Python runtime has specific handler format requirements that differ from other serverless platforms.

**Total resolution time:** ~3 hours of systematic debugging
**Root cause:** Platform-specific handler format requirement
**Final solution:** BaseHTTPRequestHandler class implementation

The experience reinforces the importance of systematic debugging, starting with infrastructure verification before diving into code complexity. When all code variations fail identically, the issue is almost always infrastructure or platform configuration, not application logic.