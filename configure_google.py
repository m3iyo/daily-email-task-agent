#!/usr/bin/env python3
"""
Interactive script to help configure Google API credentials
"""

import os
import json
from pathlib import Path

def create_google_credentials_guide():
    """Create a guide for setting up Google API credentials"""
    print("Google API setup guide")
    print("=" * 50)
    print()
    
    print("Step 1: Create Google Cloud project")
    print("-" * 35)
    print("1. Go to https://console.cloud.google.com")
    print("2. Create a new project or select existing")
    print("3. Name it 'Email Task Agent' or similar")
    print()
    
    print("Step 2: Enable required APIs")
    print("-" * 30)
    print("1. In Google Cloud Console, go to 'APIs & Services' > 'Library'")
    print("2. Search and enable these APIs:")
    print("   - Gmail API")
    print("   - Google Tasks API")
    print("3. Click 'Enable' for each")
    print()
    
    print("Step 3: Create OAuth credentials")
    print("-" * 35)
    print("1. Go to 'APIs & Services' > 'Credentials'")
    print("2. Click '+ CREATE CREDENTIALS' > 'OAuth client ID'")
    print("3. If asked, configure OAuth consent screen:")
    print("   - User Type: External")
    print("   - App name: Email Task Agent")
    print("   - User support email: your email")
    print("   - Developer contact: your email")
    print("   - Add scopes:")
    print("     https://www.googleapis.com/auth/gmail.readonly")
    print("     https://www.googleapis.com/auth/tasks")
    print("   - Add test users: your email")
    print("4. For OAuth client ID:")
    print("   - Application type: Desktop application")
    print("   - Name: Email Task Agent")
    print("5. Download the JSON file")
    print("6. Save it as 'credentials.json' in this directory")
    print()
    
    print("Step 4: Test connection")
    print("-" * 25)
    print("1. Run: python test_google_apis.py")
    print("2. Follow OAuth flow in browser")
    print("3. Grant permissions for Gmail and Tasks")
    print()
    
    print("Done. Your Google APIs will be ready to use.")
    print()
    
    # Check if credentials file exists
    creds_file = Path("credentials.json")
    if creds_file.exists():
        print("OK: Found credentials.json file")
        
        # Validate it's a valid JSON
        try:
            with open(creds_file) as f:
                creds = json.load(f)
            
            if "installed" in creds or "web" in creds:
                print("OK: Credentials file appears valid")
                return True
            else:
                print("WARN: Credentials file format may be incorrect")
                return False
                
        except json.JSONDecodeError:
            print("FAIL: Credentials file is not valid JSON")
            return False
    else:
        print("FAIL: credentials.json not found")
        print("Please download it from Google Cloud Console")
        return False

def main():
    """Main function"""
    if create_google_credentials_guide():
        print("\nReady to test Google API connection.")
        print("Run: python test_google_apis.py")
    else:
        print("\nPlease set up credentials.json first")
        print("Follow the guide above")

if __name__ == "__main__":
    main()
