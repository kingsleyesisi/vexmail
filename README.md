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

## Prerequisites

- Python 3.8 or higher
- A Gmail account (or any IMAP-enabled email)
- Internet connection

## Quick Start

### Step 1: Install Dependencies

```bash
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

### Step 3: Run the Application

```bash
python app.py
```

Open your browser and go to: **http://localhost:5000**

## Project Structure

This project uses a flat structure to be as simple as possible.

```
simple-email-client/
├── app.py              # Main application logic
├── index.html          # Frontend interface
├── requirements.txt    # Python dependencies
├── .env                # Configuration (Email & Database)
└── README.md           # This file
```

## Database Setup

The application uses Supabase. If you need to set up the database manually, run this SQL in your Supabase SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS emails (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email_id text UNIQUE NOT NULL,
  subject text,
  sender text,
  date text,
  body text,
  is_read boolean DEFAULT false,
  is_starred boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_emails_created_at ON emails(created_at DESC);
```

## How it Works

1. **Sync**: Clicking "Sync Emails" connects to your email provider (IMAP).
2. **Fetch**: It grabs the latest emails.
3. **Store**: Emails are saved to Supabase (if they aren't there already).
4. **Display**: The app reads from Supabase and shows them in `index.html`.

## Customization

- **Change Fetch Limit**: In `app.py`, change `fetch_emails_from_server(limit=50)` to your desired number.
- **Change UI**: Edit `index.html`. It uses TailwindCSS for styling.

## Troubleshooting

- **"Could not connect to email server"**: Check your `.env` credentials. Use an App Password for Gmail.
- **Dependencies Error**: Run `pip install -r requirements.txt` again.
- **Port In Use**: If port 5000 is taken, `app.py` will fail. Kill the process using port 5000 or change the port in `app.py`.

---

**Happy coding! 🎉**
