"""
Google Drive Production Sync - Setup Validator
==============================================

This script validates that your environment is properly configured
for the Google Drive Production Sync System.

Run this before your first sync to catch any configuration issues.
"""

import os
import sys
import json
import subprocess
import importlib.util

def print_header(title):
    print("=" * 60)
    print(f" {title}")
    print("=" * 60)

def print_check(description, status, details=""):
    status_symbol = "✅" if status else "❌"
    print(f"{status_symbol} {description}")
    if details:
        print(f"   {details}")
    print()

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    is_valid = version >= (3, 7)
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print_check(
        "Python Version", 
        is_valid,
        f"Version: {version_str} (Required: 3.7+)"
    )
    return is_valid

def check_required_packages():
    """Check if required Python packages are installed"""
    required_packages = [
        'google.auth',
        'google_auth_oauthlib',
        'googleapiclient'
    ]
    
    all_installed = True
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            all_installed = False
            missing_packages.append(package)
    
    if all_installed:
        print_check("Python Packages", True, "All required packages installed")
    else:
        print_check(
            "Python Packages", 
            False,
            f"Missing: {', '.join(missing_packages)}"
        )
        print("   Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        print()
    
    return all_installed

def check_config_file():
    """Check if config.json exists and is valid"""
    config_file = "config.json"
    
    if not os.path.exists(config_file):
        print_check("Configuration File", False, f"{config_file} not found")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Check required sections
        required_sections = ['drive_settings', 'local_settings', 'sync_settings']
        missing_sections = [section for section in required_sections if section not in config]
        
        if missing_sections:
            print_check(
                "Configuration File", 
                False,
                f"Missing sections: {', '.join(missing_sections)}"
            )
            return False
        
        # Check folder ID
        folder_id = config.get('drive_settings', {}).get('folder_id', '')
        if not folder_id or folder_id == "1NiYBfZqkbXHuDLfDrfhNYlDETjdwKLRq":
            print_check(
                "Configuration File", 
                False,
                "Update folder_id in drive_settings with your Google Drive folder ID"
            )
            return False
        
        print_check(
            "Configuration File", 
            True,
            f"Valid configuration loaded (Folder ID: {folder_id[:20]}...)"
        )
        return True
        
    except json.JSONDecodeError as e:
        print_check("Configuration File", False, f"Invalid JSON: {e}")
        return False
    except Exception as e:
        print_check("Configuration File", False, f"Error reading file: {e}")
        return False

def check_credentials_file():
    """Check if credentials.json exists"""
    creds_file = "credentials.json"
    
    if not os.path.exists(creds_file):
        print_check("Credentials File", False, f"{creds_file} not found")
        print("   Download from Google Cloud Console and rename to credentials.json")
        print()
        return False
    
    try:
        with open(creds_file, 'r') as f:
            creds = json.load(f)
        
        if 'installed' not in creds and 'web' not in creds:
            print_check("Credentials File", False, "Invalid credentials format")
            return False
        
        print_check("Credentials File", True, "Valid credentials file found")
        return True
        
    except json.JSONDecodeError:
        print_check("Credentials File", False, "Invalid JSON format")
        return False
    except Exception as e:
        print_check("Credentials File", False, f"Error reading file: {e}")
        return False

def check_directories():
    """Check if required directories can be created"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        directories = [
            config.get('local_settings', {}).get('download_directory', 'data'),
            config.get('local_settings', {}).get('logs_directory', 'logs'),
            config.get('local_settings', {}).get('state_directory', 'state'),
            config.get('local_settings', {}).get('temp_directory', 'temp')
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print_check(
                    "Directory Creation", 
                    False,
                    f"Cannot create {directory}: {e}"
                )
                return False
        
        print_check("Directory Creation", True, "All required directories created")
        return True
        
    except Exception as e:
        print_check("Directory Creation", False, f"Error: {e}")
        return False

def check_disk_space():
    """Check available disk space"""
    try:
        statvfs = os.statvfs('.')
        available_bytes = statvfs.f_bavail * statvfs.f_frsize
        available_gb = available_bytes / (1024**3)
        
        if available_gb < 1:
            print_check(
                "Disk Space", 
                False,
                f"Only {available_gb:.2f} GB available (Need more for large syncs)"
            )
            return False
        else:
            print_check(
                "Disk Space", 
                True,
                f"{available_gb:.2f} GB available"
            )
            return True
            
    except:
        # Windows doesn't have statvfs, use alternative method
        try:
            import shutil
            total, used, free = shutil.disk_usage('.')
            free_gb = free / (1024**3)
            
            if free_gb < 1:
                print_check(
                    "Disk Space", 
                    False,
                    f"Only {free_gb:.2f} GB available (Need more for large syncs)"
                )
                return False
            else:
                print_check(
                    "Disk Space", 
                    True,
                    f"{free_gb:.2f} GB available"
                )
                return True
                
        except Exception as e:
            print_check("Disk Space", False, f"Cannot check disk space: {e}")
            return False

def check_internet_connection():
    """Check internet connectivity"""
    try:
        import urllib.request
        urllib.request.urlopen('https://www.google.com', timeout=10)
        print_check("Internet Connection", True, "Connected to internet")
        return True
    except Exception:
        print_check("Internet Connection", False, "Cannot reach internet")
        return False

def main():
    """Run all validation checks"""
    print_header("Google Drive Production Sync - Setup Validation")
    
    checks = [
        ("Python Version", check_python_version),
        ("Required Packages", check_required_packages),
        ("Configuration File", check_config_file),
        ("Credentials File", check_credentials_file),
        ("Directory Creation", check_directories),
        ("Disk Space", check_disk_space),
        ("Internet Connection", check_internet_connection)
    ]
    
    passed_checks = 0
    total_checks = len(checks)
    
    for check_name, check_func in checks:
        try:
            if check_func():
                passed_checks += 1
        except Exception as e:
            print_check(check_name, False, f"Unexpected error: {e}")
    
    print_header("Validation Summary")
    
    success_rate = (passed_checks / total_checks) * 100
    
    print(f"Passed: {passed_checks}/{total_checks} checks ({success_rate:.0f}%)")
    print()
    
    if passed_checks == total_checks:
        print("🎉 VALIDATION SUCCESSFUL!")
        print("Your system is ready for Google Drive sync.")
        print()
        print("Next steps:")
        print("1. Run: sync_full.bat (for first complete sync)")
        print("2. Run: setup_scheduler.bat (for daily automation)")
        print()
    else:
        print("⚠️  VALIDATION INCOMPLETE")
        print(f"Please fix the {total_checks - passed_checks} failed check(s) above.")
        print()
        print("Common solutions:")
        print("- Install Python packages: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        print("- Download credentials.json from Google Cloud Console")
        print("- Update folder_id in config.json")
        print("- Ensure stable internet connection")
        print()
        print("After fixing issues, run this validator again.")
        print()
    
    return passed_checks == total_checks

if __name__ == '__main__':
    success = main()
    if not success:
        sys.exit(1)