import imaplib
import email
import os
import json
from email.header import decode_header

def get_email_body(msg):
    """
    Parses an email message and returns the body content.
    It prioritizes the plain text part of multipart emails.
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                except (UnicodeDecodeError, AttributeError):
                    body = part.get_payload(decode=True).decode("latin-1", errors="ignore")
                break
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="ignore")
        except (UnicodeDecodeError, AttributeError):
            body = msg.get_payload(decode=True).decode("latin-1", errors="ignore")
    return body

def decode_header_part(header_part):
    """
    Decodes a header part, returning it as a UTF-8 string.
    """
    decoded, encoding = header_part
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or "utf-8", errors="ignore")
    return decoded

def main():
    IMAP_SERVER = os.environ.get("IMAP_SERVER", "mail.nextrade.online")
    EMAIL_USER  = os.environ.get("EMAIL_USER",  "info@nextrade.online")
    EMAIL_PASS  = os.environ.get("EMAIL_PASS",  "Kingsley419.")
    OUTPUT_FILE = os.environ.get("EMAIL_JSON_OUTPUT", "email_dump.json")
    DUMP_COUNT  = 10  # number of most recent emails to dump

    if not all([IMAP_SERVER, EMAIL_USER, EMAIL_PASS]):
        print("Error: Please set IMAP_SERVER, EMAIL_USER, and EMAIL_PASS environment variables.")
        return

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('INBOX')

        status, messages = mail.search(None, 'ALL')
        if status != 'OK':
            print("Error searching for emails.")
            return

        message_ids = messages[0].split()
        total = len(message_ids)
        if total == 0:
            print("No emails found in INBOX.")
            return

        # Take the last DUMP_COUNT IDs and reverse them so highest ID (newest) comes first
        last_ids = message_ids[-DUMP_COUNT:][::-1] if total >= DUMP_COUNT else message_ids[::-1]
        all_emails = []

        for eid in last_ids:
            status, msg_data = mail.fetch(eid, '(RFC822)')
            if status != 'OK':
                print(f"Warning: could not fetch email ID {eid.decode()}. Skipping.")
                continue

            raw_email = msg_data[0][1]
            msg       = email.message_from_bytes(raw_email)

            subject_hdr = decode_header(msg.get("Subject", ""))[0]
            from_hdr    = decode_header(msg.get("From", ""))[0]
            subject     = decode_header_part(subject_hdr)
            sender      = decode_header_part(from_hdr)
            body        = get_email_body(msg)

            all_emails.append({
                "id":      eid.decode(),
                "subject": subject,
                "from":    sender,
                "body":    body
            })

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_emails, f, ensure_ascii=False, indent=4)

        print(f"Dumped {len(all_emails)} most recent emails (newest first) to {OUTPUT_FILE}")

    except imaplib.IMAP4.error as e:
        print(f"An IMAP error occurred: {e}")
    finally:
        if mail:
            mail.logout()

if __name__ == "__main__":
    main()
