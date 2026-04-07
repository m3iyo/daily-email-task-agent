#!/usr/bin/env python3
"""
Git Security Check Script
Verifies that confidential files are properly ignored by Git
"""

import os
import subprocess
import sys
from pathlib import Path

def check_git_status():
    """Check if confidential files appear in git status"""
    print("Checking Git status for confidential files...")
    
    confidential_files = [
        '.env',
        'credentials.json', 
        'token.json',
        'data/email_agent.db',
        '.env.backup',
        'credentials.json.backup',
        'token.json.backup'
    ]
    
    try:
        # Get git status
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, check=True)
        
        git_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Check for confidential files in git status
        found_confidential = []
        for file_line in git_files:
            if file_line:
                filename = file_line[3:]  # Remove git status prefix
                if any(conf_file in filename for conf_file in confidential_files):
                    found_confidential.append(filename)
        
        if found_confidential:
            print("SECURITY RISK: Confidential files found in git status:")
            for file in found_confidential:
                print(f"   - {file}")
            print("\nThese files should be added to .gitignore")
            return False
        else:
            print("OK: No confidential files found in git status")
            return True
            
    except subprocess.CalledProcessError:
        print("WARN: Not a git repository or git not available")
        return True
    except FileNotFoundError:
        print("WARN: Git not found in PATH")
        return True

def check_gitignore():
    """Check if .gitignore exists and contains confidential files"""
    print("\nChecking .gitignore file...")
    
    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        print("FAIL: .gitignore file not found")
        return False
    
    with open(gitignore_path, 'r') as f:
        gitignore_content = f.read()
    
    required_patterns = [
        '.env',
        'credentials.json',
        'token.json',
        '*.db'
    ]
    
    missing_patterns = []
    for pattern in required_patterns:
        if pattern not in gitignore_content:
            missing_patterns.append(pattern)
    
    if missing_patterns:
        print("WARN: Missing patterns in .gitignore:")
        for pattern in missing_patterns:
            print(f"   - {pattern}")
        return False
    else:
        print("OK: .gitignore contains required confidential file patterns")
        return True

def check_file_existence():
    """Check if confidential files exist"""
    print("\nChecking for confidential files...")
    
    files_to_check = {
        '.env': 'Environment variables',
        'credentials.json': 'Google API credentials',
        'token.json': 'OAuth tokens (auto-generated)',
        '.env.example': 'Environment template',
        'credentials.json.example': 'Credentials template'
    }
    
    for filename, description in files_to_check.items():
        if Path(filename).exists():
            print(f"OK: {filename} - {description}")
        else:
            if filename.endswith('.example'):
                print(f"WARN: {filename} - {description} (template missing)")
            else:
                print(f"FAIL: {filename} - {description} (required file missing)")

def main():
    """Main security check function"""
    print("Git Security Check for Daily Email & Task Agent")
    print("=" * 55)
    
    os.chdir(Path(__file__).parent)
    
    gitignore_ok = check_gitignore()
    git_status_ok = check_git_status()
    check_file_existence()
    
    print("\n" + "=" * 55)
    if gitignore_ok and git_status_ok:
        print("Security check PASSED. Safe to commit to Git.")
        sys.exit(0)
    else:
        print("Security check FAILED. Fix issues before committing.")
        print("\nNext steps:")
        print("1. Review and update .gitignore file")
        print("2. Remove any confidential files from git tracking")
        print("3. Run this script again to verify")
        sys.exit(1)

if __name__ == "__main__":
    main()
