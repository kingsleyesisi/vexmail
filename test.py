#!/usr/bin/env python3
"""
Test script for VexMail email operations
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_get_emails():
    """Test getting emails"""
    print("Testing GET /api/emails...")
    response = requests.get(f"{BASE_URL}/api/emails")
    if response.status_code == 200:
        emails = response.json()
        print(f"✓ Successfully fetched {len(emails)} emails")
        if emails:
            print(f"  First email: {emails[0]['subject']}")
            print(f"  Is read: {emails[0].get('is_read', False)}")
        return emails
    else:
        print(f"✗ Failed to fetch emails: {response.status_code}")
        return []

def test_mark_as_read(email_id):
    """Test marking email as read"""
    print(f"Testing POST /api/emails/{email_id}/read...")
    response = requests.post(f"{BASE_URL}/api/emails/{email_id}/read")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Successfully marked email as read")
        return True
    else:
        print(f"✗ Failed to mark email as read: {response.status_code}")
        return False

def test_mark_as_unread(email_id):
    """Test marking email as unread"""
    print(f"Testing POST /api/emails/{email_id}/unread...")
    response = requests.post(f"{BASE_URL}/api/emails/{email_id}/unread")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Successfully marked email as unread")
        return True
    else:
        print(f"✗ Failed to mark email as unread: {response.status_code}")
        return False

def test_delete_email(email_id):
    """Test deleting email"""
    print(f"Testing DELETE /api/emails/{email_id}...")
    response = requests.delete(f"{BASE_URL}/api/emails/{email_id}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Successfully deleted email")
        return True
    else:
        print(f"✗ Failed to delete email: {response.status_code}")
        return False

def test_batch_operations(email_ids):
    """Test batch operations"""
    print("Testing POST /api/emails/batch...")
    
    # Test batch mark as read
    data = {
        "operation": "read",
        "uids": email_ids[:2]  # Mark first 2 as read
    }
    response = requests.post(f"{BASE_URL}/api/emails/batch", json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Successfully queued batch read operation")
    else:
        print(f"✗ Failed batch read operation: {response.status_code}")

def main():
    """Run all tests"""
    print("Starting VexMail API tests...\n")
    
    # Test 1: Get emails
    emails = test_get_emails()
    if not emails:
        print("No emails to test with. Exiting.")
        return
    
    print()
    
    # Test 2: Mark as read
    first_email_id = emails[0]['id']
    test_mark_as_read(first_email_id)
    
    print()
    
    # Test 3: Mark as unread
    test_mark_as_unread(first_email_id)
    
    print()
    
    # Test 4: Batch operations
    email_ids = [email['id'] for email in emails[:3]]
    test_batch_operations(email_ids)
    
    print()
    
    # Test 5: Delete email (use second email to avoid deleting the first one we just tested)
    if len(emails) > 1:
        second_email_id = emails[1]['id']
        test_delete_email(second_email_id)
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main()