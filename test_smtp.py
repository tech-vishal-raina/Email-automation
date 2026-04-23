#!/usr/bin/env python3
"""
SMTP connection test script for debugging authentication issues.
"""

import smtplib
import ssl
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings

def test_smtp_connection():
    """Test SMTP connection and authentication with detailed error reporting."""
    print('=== SMTP CONNECTION TEST ===')
    print(f'Host: {settings.SMTP_HOST}')
    print(f'Port: {settings.SMTP_PORT}')
    print(f'Username: {settings.SMTP_USERNAME}')
    print(f'Password: {"SET" if settings.SMTP_PASSWORD else "NOT_SET"}')
    
    if not all([settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
        print('❌ Missing required SMTP credentials')
        return False
    
    try:
        print('\n🔗 Connecting to SMTP server...')
        
        if settings.SMTP_PORT == 465:
            # SSL from the start
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context)
            print('✅ SSL connection established')
        else:
            # STARTTLS (port 587 standard)
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.ehlo()
            print('✅ Initial connection established')
            
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            print('✅ STARTTLS encryption enabled')
        
        print('\n🔐 Attempting authentication...')
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        print('✅ Authentication successful!')
        
        server.quit()
        print('✅ Connection closed properly')
        return True
        
    except smtplib.SMTPAuthenticationError as exc:
        print(f'\n❌ SMTP Authentication Error: {exc}')
        print('\n🔍 Common causes and solutions:')
        print('1. Gmail: Use an App Password, not your account password')
        print('   → Enable 2FA: https://myaccount.google.com/security')
        print('   → Generate App Password: https://myaccount.google.com/apppasswords')
        print('2. Check for typos in username/password')
        print('3. Ensure "Less secure app access" is enabled (if not using App Password)')
        print('4. Try unlocking the captcha: https://accounts.google.com/displayunlockcaptcha')
        return False
        
    except smtplib.SMTPConnectError as exc:
        print(f'\n❌ SMTP Connection Error: {exc}')
        print('🔍 Common causes:')
        print('1. Firewall blocking SMTP ports')
        print('2. Incorrect SMTP host/port')
        print('3. Network connectivity issues')
        return False
        
    except Exception as exc:
        print(f'\n❌ Unexpected error: {exc}')
        print(f'Error type: {type(exc).__name__}')
        return False

if __name__ == '__main__':
    success = test_smtp_connection()
    sys.exit(0 if success else 1)
