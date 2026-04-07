#!/usr/bin/env python3
"""
Test script to verify Google APIs (Gmail and Tasks) are working
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_gmail_connection():
    """Test Gmail API connection"""
    print("Testing Gmail API connection...")
    
    try:
        from services.gmail import GmailService
        
        gmail_service = GmailService()
        
        if gmail_service.test_connection():
            print("OK: Gmail API connection successful")
            
            # Try fetching a few emails
            emails = gmail_service.get_recent_emails(max_results=5, hours_back=24)
            print(f"OK: Found {len(emails)} recent emails")
            
            return True
        else:
            print("FAIL: Gmail API connection failed")
            return False
            
    except Exception as e:
        print(f"FAIL: Gmail API error: {e}")
        return False

def test_tasks_connection():
    """Test Google Tasks API connection"""
    print("Testing Google Tasks API connection...")
    
    try:
        from services.tasks import GoogleTasksService
        
        tasks_service = GoogleTasksService()
        
        if tasks_service.test_connection():
            print("OK: Google Tasks API connection successful")
            
            # Try creating a test task
            test_task_id = tasks_service.create_task(
                title="Test Task from Email Agent",
                description="This is a test task created by the Email & Task Agent"
            )
            
            if test_task_id:
                print("OK: Successfully created test task")
                
                # Clean up - delete the test task
                tasks_service.delete_task(test_task_id)
                print("OK: Cleaned up test task")
            
            return True
        else:
            print("FAIL: Google Tasks API connection failed")
            return False
            
    except Exception as e:
        print(f"FAIL: Google Tasks API error: {e}")
        return False

def test_email_processing():
    """Test email processing pipeline"""
    print("Testing email processing pipeline...")
    
    try:
        from services.email_processor import EmailProcessor
        
        processor = EmailProcessor()
        print("OK: Email processor initialized")
        
        # Test processing would require actual emails
        # For now, just verify it can be instantiated
        return True
        
    except Exception as e:
        print(f"FAIL: Email processor error: {e}")
        return False

def main():
    """Main test function"""
    print("Testing Google APIs for Email & Task Agent")
    print("=" * 50)
    
    # Check if credentials file exists
    if not Path("credentials.json").exists():
        print("FAIL: credentials.json not found")
        print("Please run: python configure_google.py")
        return 1
    
    tests = [
        ("Gmail API", test_gmail_connection),
        ("Google Tasks API", test_tasks_connection),
        ("Email Processing", test_email_processing),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} test...")
        try:
            if test_func():
                passed += 1
                print(f"OK: {test_name} test PASSED")
            else:
                failed += 1
                print(f"FAIL: {test_name} test FAILED")
        except Exception as e:
            failed += 1
            print(f"FAIL: {test_name} test FAILED with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests passed. Google APIs are ready.")
        print("\nNext steps:")
        print("1. Ensure Ollama is running and model is pulled")
        print("2. Run: python run.py")
        print("3. Open: http://localhost:8000")
    else:
        print("Some tests failed. Check the errors above.")
        if "credentials.json" in str(failed):
            print("Run: python configure_google.py for setup help")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
