#!/usr/bin/env python3
"""
Simple OAuth test to verify Google authentication works
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_python_version():
    """Ensure the runtime is compatible with the pinned dependencies."""
    current = sys.version_info[:3]
    if current < (3, 11):
        print(f"FAIL: Python 3.11+ required, found {sys.version.split()[0]}")
        return False
    if current >= (3, 14):
        print(f"FAIL: Python 3.14+ is not supported by the pinned SQLAlchemy version, found {sys.version.split()[0]}")
        return False
    return True

def test_oauth():
    """Test OAuth authentication with minimal setup"""
    print("Testing Google OAuth authentication")
    print("=" * 45)

    if not check_python_version():
        return False
    
    # Check credentials file
    if not Path("credentials.json").exists():
        print("FAIL: credentials.json not found")
        return False
    
    print("OK: Found credentials.json")
    
    # Set SQLite database to avoid PostgreSQL dependency
    os.environ["DATABASE_URL"] = "sqlite:///./data/email_agent.db"
    
    try:
        print("Attempting Gmail authentication...")
        from services.gmail import GmailService
        
        # This will trigger the OAuth flow
        gmail_service = GmailService()
        print("OK: Gmail authentication successful")
        
        # Test connection
        print("Testing Gmail API connection...")
        if gmail_service.test_connection():
            print("OK: Gmail API connection working")
            return True
        else:
            print("FAIL: Gmail API connection failed")
            return False
            
    except Exception as e:
        print(f"FAIL: authentication failed: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you've added your email as a test user in Google Cloud Console")
        print("2. Go to: https://console.cloud.google.com/apis/credentials/consent")
        print("3. Add your Gmail account to OAuth test users")
        print("4. Make sure Gmail API is enabled")
        return False

if __name__ == "__main__":
    if test_oauth():
        print("\nGoogle authentication is working")
        print("You can now run: python test_google_apis.py")
    else:
        print("\nPlease fix the authentication issue first")
