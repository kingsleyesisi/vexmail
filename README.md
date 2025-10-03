# Simple Email Client

A beginner-friendly Gmail-like email client that receives and displays emails in real-time. Built with Python Flask and Supabase.

![Email Client](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![Supabase](https://img.shields.io/badge/Supabase-Enabled-orange.svg)

## Features

- **Gmail-like Interface**: Clean, modern UI similar to Gmail
- **Real-time Updates**: Emails update automatically in the database
- **Email Management**: Read, star, and organize your emails
- **Simple Setup**: Just 3 steps to get started
- **Beginner Friendly**: Clear, well-commented code

## What This App Does

This application:
1. Connects to your email account via IMAP (Gmail, Outlook, etc.)
2. Fetches your emails and stores them in Supabase database
3. Displays them in a beautiful Gmail-like interface
4. Lets you read, star, and manage your emails

## Prerequisites

- Python 3.8 or higher
- A Gmail account (or any IMAP-enabled email)
- Internet connection

## Quick Start

### Step 1: Clone and Install

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### Step 2: Configure Your Email

1. Open the `.env` file in the project root
2. Add your email credentials:

```env
# Email Configuration
IMAP_SERVER=imap.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
```

**For Gmail users:**
- You need to create an "App Password" (not your regular password)
- Go to: https://myaccount.google.com/apppasswords
- Enable 2-factor authentication first
- Generate an app password and use it in the `.env` file

**For other email providers:**
- Outlook: `imap.outlook.com`
- Yahoo: `imap.mail.yahoo.com`
- Use your regular email and password

### Step 3: Run the Application

```bash
python app.py
```

Open your browser and go to: **http://localhost:5000**

## How to Use

### First Time Setup

1. Open the app in your browser
2. Click the **"Sync Emails"** button
3. Wait while your emails are fetched from your email server
4. Your emails will appear in the list!

### Managing Emails

- **Read Email**: Click on any email to read its full content
- **Star Email**: Click the star icon to mark important emails
- **Sync**: Click "Sync Emails" to fetch new emails

### Understanding the Dashboard

- **Total Emails**: Shows all emails in your inbox
- **Unread**: Shows how many emails you haven't read yet
- **Starred**: Shows emails you've marked as important

## Project Structure

```
simple-email-client/
├── app.py                  # Main application file
├── templates/
│   └── index.html         # Frontend interface
├── requirements.txt       # Python dependencies
├── .env                   # Your configuration
├── .env.example          # Example configuration
└── README.md             # This file
```

## Code Overview

### app.py - Main Application

The main file contains:
- **Flask Setup**: Web server configuration
- **Supabase Connection**: Database connection
- **Email Functions**: Fetch and store emails
- **API Routes**: Endpoints for the frontend

Key functions:
- `connect_to_imap()`: Connects to your email server
- `fetch_emails_from_server()`: Gets emails from IMAP
- `sync_emails()`: Syncs emails to Supabase
- Various API endpoints for managing emails

### templates/index.html - Frontend

The interface includes:
- **Email List**: Shows all your emails
- **Email Detail Modal**: Read full email content
- **Stats Dashboard**: See email counts
- **Simple JavaScript**: Easy to understand and modify

## Database Schema

The app uses Supabase with a simple `emails` table:

| Column      | Type      | Description                    |
|-------------|-----------|--------------------------------|
| id          | uuid      | Unique identifier              |
| email_id    | text      | Original email ID from server  |
| subject     | text      | Email subject                  |
| sender      | text      | Sender's email address         |
| date        | text      | When email was sent            |
| body        | text      | Email content                  |
| is_read     | boolean   | Has been read                  |
| is_starred  | boolean   | Marked as important            |
| created_at  | timestamp | When stored in database        |

## API Endpoints

| Endpoint                      | Method | Description                |
|-------------------------------|--------|----------------------------|
| `/`                          | GET    | Main page                  |
| `/api/emails`                | GET    | Get all emails             |
| `/api/emails/<id>`           | GET    | Get single email           |
| `/api/sync`                  | POST   | Sync emails from server    |
| `/api/emails/<id>/star`      | POST   | Toggle star status         |
| `/api/emails/<id>/read`      | POST   | Toggle read status         |
| `/api/stats`                 | GET    | Get email statistics       |
| `/api/health`                | GET    | Health check               |

## Troubleshooting

### "Could not connect to email server"

**Solution:**
1. Check your email credentials in `.env`
2. For Gmail, make sure you're using an App Password
3. Verify your internet connection

### "Authentication failed"

**Solution:**
1. Gmail: Use App Password, not regular password
2. Other providers: Check if IMAP is enabled in your email settings

### "No emails showing"

**Solution:**
1. Click the "Sync Emails" button
2. Check browser console for errors (F12)
3. Make sure your email account has emails

### Port already in use

**Solution:**
```bash
# Kill the process using port 5000
lsof -ti:5000 | xargs kill -9

# Or run on a different port
# Edit app.py and change: app.run(host='0.0.0.0', port=5001)
```

## Understanding the Code

### How Email Syncing Works

```python
# 1. Connect to email server
mail = connect_to_imap()

# 2. Fetch emails
emails = fetch_emails_from_server(limit=50)

# 3. Store in Supabase
for email in emails:
    supabase.table('emails').insert(email).execute()
```

### How the Frontend Works

```javascript
// 1. Load emails from API
async function loadEmails() {
    const response = await fetch('/api/emails');
    const data = await response.json();
    renderEmails(data.emails);
}

// 2. Open email detail
function openEmail(emailId) {
    // Fetch email details and show in modal
}

// 3. Sync new emails
function syncEmails() {
    // Call API to fetch from email server
}
```

## Customization

### Change Email Limit

Edit `app.py`:
```python
# Change 50 to any number
emails = fetch_emails_from_server(limit=100)
```

### Change App Title

Edit `templates/index.html`:
```html
<h1>Your Custom Title</h1>
```

### Change Colors

Edit the Tailwind classes in `templates/index.html`:
```html
<!-- Change blue-600 to any color -->
<button class="bg-blue-600">Sync</button>
```

## Security Notes

- Never commit your `.env` file to GitHub
- Use App Passwords for Gmail (never use your main password)
- The app only reads emails (doesn't send or delete)
- Data is stored securely in Supabase

## Tech Stack

- **Backend**: Python Flask
- **Database**: Supabase (PostgreSQL)
- **Frontend**: HTML, TailwindCSS, Vanilla JavaScript
- **Email**: IMAP protocol

## Learning Resources

### For Beginners

- **Flask**: https://flask.palletsprojects.com/
- **Supabase**: https://supabase.com/docs
- **IMAP**: https://docs.python.org/3/library/imaplib.html
- **TailwindCSS**: https://tailwindcss.com/docs

### Understanding the Code

1. **app.py**: Start here - read the comments
2. **index.html**: Look at the HTML structure first
3. **JavaScript**: Read the functions one by one

## Contributing

This is a simple educational project. Feel free to:
- Add features
- Improve the code
- Fix bugs
- Share your improvements

## License

MIT License - Feel free to use this for learning or personal projects.

## Support

If you run into issues:
1. Check the Troubleshooting section
2. Read the error messages carefully
3. Check your `.env` configuration
4. Make sure Supabase is working

## What's Next?

Ideas for improvements:
- Add email search functionality
- Implement email folders
- Add email composition (sending emails)
- Create a mobile app version
- Add email filtering and rules

---

**Happy coding! 🎉**

Made with ❤️ for learning Python and web development
