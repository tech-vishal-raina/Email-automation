#!/usr/bin/env python3
"""
Environment diagnostic script for SMTP authentication issues.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def main():
    print('=== ENVIRONMENT DIAGNOSTICS ===')
    print(f'Current directory: {Path.cwd()}')
    
    # Check .env file
    env_file = Path('.env')
    env_example = Path('.env.example')
    print(f'.env exists: {env_file.exists()}')
    print(f'.env.example exists: {env_example.exists()}')
    
    if not env_file.exists() and env_example.exists():
        print('⚠️  .env file missing but .env.example exists')
        print('Creating .env from .env.example...')
        with open(env_example, 'r') as src, open(env_file, 'w') as dst:
            dst.write(src.read())
        print('✅ .env created from .env.example')
        print('Please edit .env with your actual credentials')
        return 1
    
    # Load .env
    load_dotenv()
    print('\n=== ENVIRONMENT VARIABLES ===')
    smtp_vars = ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SENDER_EMAIL']
    
    missing_vars = []
    for var in smtp_vars:
        value = os.getenv(var, 'NOT_SET')
        if 'PASSWORD' in var:
            display_value = 'SET' if value and value != 'NOT_SET' else 'NOT_SET'
        else:
            display_value = value if value != 'NOT_SET' else 'NOT_SET'
        
        status = '✅' if value and value != 'NOT_SET' else '❌'
        print(f'{status} {var}: {display_value}')
        
        if not value or value == 'NOT_SET':
            missing_vars.append(var)
    
    if missing_vars:
        print(f'\n❌ Missing variables: {", ".join(missing_vars)}')
        print('Please set these in your .env file')
        return 1
    
    print('\n✅ All required environment variables are set')
    return 0

if __name__ == '__main__':
    sys.exit(main())
