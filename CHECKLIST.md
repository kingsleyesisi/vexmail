# Setup Checklist

Use this checklist to get your Simple Email Client up and running!

## Prerequisites ✅

- [ ] Python 3.8 or higher installed
- [ ] Internet connection
- [ ] Email account (Gmail, Outlook, etc.)
- [ ] Text editor (VS Code, Sublime, etc.)

## Installation Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```
- [ ] Flask installed
- [ ] Flask-CORS installed
- [ ] Supabase client installed
- [ ] python-decouple installed

### 2. Configure Email

Open `.env` file and fill in:

- [ ] Added your IMAP server (e.g., imap.gmail.com)
- [ ] Added your email address
- [ ] Added your email password/app password

**For Gmail users:**
- [ ] Enabled 2-factor authentication
- [ ] Created app password at https://myaccount.google.com/apppasswords
- [ ] Used app password (not regular password)

### 3. Verify Setup

- [ ] Supabase URL is in .env (already configured)
- [ ] Supabase key is in .env (already configured)
- [ ] Email credentials are in .env
- [ ] No syntax errors in .env file

### 4. Test Connection

```bash
python app.py
```

- [ ] Application starts without errors
- [ ] Can access http://localhost:5000
- [ ] Page loads correctly
- [ ] No console errors (press F12)

### 5. Sync Emails

- [ ] Clicked "Sync Emails" button
- [ ] Saw "Syncing..." message
- [ ] Emails appeared in list
- [ ] Statistics updated

### 6. Test Features

- [ ] Can click and read an email
- [ ] Email modal opens correctly
- [ ] Can star/unstar emails
- [ ] Read/unread status works
- [ ] Statistics are accurate

## Troubleshooting Checklist

If something doesn't work:

### Connection Issues
- [ ] Internet connection is working
- [ ] Email server is accessible
- [ ] Credentials are correct
- [ ] For Gmail: using app password

### Application Issues
- [ ] Python 3.8+ is installed
- [ ] All dependencies installed
- [ ] .env file exists
- [ ] No syntax errors in code
- [ ] Port 5000 is not in use

### Browser Issues
- [ ] JavaScript is enabled
- [ ] Browser console shows no errors (F12)
- [ ] Cookies are enabled
- [ ] Cache is cleared

## Verification Tests

Run these to verify everything works:

### Backend Test
```bash
python -c "from app import app, supabase; print('✅ Backend OK')"
```
- [ ] No errors

### Database Test
```bash
python -c "from app import supabase; print(supabase.table('emails').select('id').limit(1).execute())"
```
- [ ] Connection successful

### API Test
Open in browser:
- [ ] http://localhost:5000/api/health
- [ ] http://localhost:5000/api/stats
- [ ] http://localhost:5000/api/emails

## Next Steps

Once everything is working:

- [ ] Read README.md for full documentation
- [ ] Explore the code in app.py
- [ ] Check out the frontend in templates/index.html
- [ ] Try customizing the interface
- [ ] Add your own features

## Learning Checklist

Understand how it works:

### Backend (app.py)
- [ ] Understand Flask routes
- [ ] Know how IMAP works
- [ ] Understand Supabase operations
- [ ] Can modify API endpoints

### Frontend (index.html)
- [ ] Understand HTML structure
- [ ] Know how JavaScript functions work
- [ ] Can modify the interface
- [ ] Understand API calls

### Database
- [ ] Know the table structure
- [ ] Understand queries
- [ ] Can view data in Supabase dashboard

## Customization Ideas

Try these modifications:

- [ ] Change the app title
- [ ] Modify colors/theme
- [ ] Add email search
- [ ] Implement folders
- [ ] Add pagination
- [ ] Create filters

## Support Resources

If you need help:

- [ ] Read README.md
- [ ] Check PROJECT_SUMMARY.md
- [ ] Read code comments
- [ ] Check browser console
- [ ] Verify .env configuration

## Success Indicators

You'll know it's working when:

✅ App starts without errors
✅ Page loads at http://localhost:5000
✅ Can sync emails successfully
✅ Emails display in the list
✅ Can read email content
✅ Can star/unstar emails
✅ Statistics update correctly
✅ No errors in browser console

---

## All Done? 🎉

Congratulations! Your Simple Email Client is now running.

**What to do next:**
1. Explore the features
2. Read the code to learn
3. Try customizing it
4. Build your own features
5. Share what you create!

**Happy coding!** 💻
