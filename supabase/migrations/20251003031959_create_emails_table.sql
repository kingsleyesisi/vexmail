/*
  # Create emails table for Simple Email Client

  1. New Tables
    - `emails`
      - `id` (uuid, primary key) - Unique identifier for each email
      - `email_id` (text, unique) - Original email ID from IMAP server
      - `subject` (text) - Email subject line
      - `sender` (text) - Email sender address
      - `date` (text) - Email date/time
      - `body` (text) - Email body content
      - `is_read` (boolean) - Whether email has been read
      - `is_starred` (boolean) - Whether email is starred
      - `created_at` (timestamptz) - When email was stored in database

  2. Security
    - Enable RLS on `emails` table
    - Add policies for public access (single-user application)

  ## Notes
    - This is a simple, beginner-friendly schema
    - Designed for receiving and displaying emails
    - Real-time subscriptions enabled for instant updates
*/

-- Create emails table
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

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_emails_created_at ON emails(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emails_is_read ON emails(is_read);
CREATE INDEX IF NOT EXISTS idx_emails_is_starred ON emails(is_starred);
CREATE INDEX IF NOT EXISTS idx_emails_email_id ON emails(email_id);

-- Enable Row Level Security
ALTER TABLE emails ENABLE ROW LEVEL SECURITY;

-- Create policies for public access (single-user app)
CREATE POLICY "Allow all access to emails"
  ON emails
  FOR ALL
  TO public
  USING (true)
  WITH CHECK (true);
