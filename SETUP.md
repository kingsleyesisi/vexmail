# Quick Setup Guide

## What Changed

This application has been completely simplified from a complex multi-file system to a clean, beginner-friendly email client.

### Before (Complex)
- 20+ files with scattered functionality
- Complex caching, threading, and service layers
- Multiple dependencies (PostgreSQL, Redis, etc.)
- Difficult to understand for beginners

### After (Simple)
- **2 main files**: `app.py` and `templates/index.html`
- Clean, well-commented code
- Only 4 dependencies
- Uses Supabase for database (already configured)
- Easy to read and modify

## Files Overview

```
project/
├── app.py              # Main Flask application (250 lines, beginner-friendly)
├── templates/
│   └── index.html      # Gmail-like interface (clean HTML/JS)
├── requirements.txt    # Only 4 dependencies
├── .env               # Your configuration
├── .env.example       # Example configuration
├── README.md          # Complete documentation
└── LICENSE            # MIT License
```

## Setup in 3 Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- Flask (web framework)
- Flask-CORS (API access)
- Supabase (database client)
- python-decouple (environment variables)

### 2. Configure Email

Edit `.env` file and add your email:

```env
IMAP_SERVER=imap.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
```

For Gmail: Create an app password at https://myaccount.google.com/apppasswords

### 3. Run

```bash
python app.py
```

Open http://localhost:5000

## Database

The Supabase database is already configured and has one table:

**emails** table:
- id (uuid)
- email_id (text, unique)
- subject (text)
- sender (text)
- date (text)
- body (text)
- is_read (boolean)
- is_starred (boolean)
- created_at (timestamp)

## Features

- View emails in Gmail-like interface
- Mark emails as read/starred
- Sync emails from your email server
- Real-time statistics
- Clean, responsive design

## How It Works

1. **Sync**: Fetch emails from IMAP server
2. **Store**: Save to Supabase database
3. **Display**: Show in beautiful interface
4. **Manage**: Read, star, organize emails

## Code is Beginner-Friendly

- Clear variable names
- Helpful comments
- Simple structure
- No complex patterns
- Easy to modify

## Next Steps

Read the full README.md for:
- Detailed documentation
- API endpoints
- Customization tips
- Troubleshooting
- Learning resources

## Support

If you need help:
1. Check README.md
2. Read code comments
3. Check browser console (F12)
4. Verify .env configuration
