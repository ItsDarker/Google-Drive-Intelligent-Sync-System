# Google Drive Intelligent Sync System

A production-ready, intelligent synchronization system for Google Drive that maintains an exact local copy of your Drive folder with minimal bandwidth usage and intelligent file handling.

## 📋 Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [GCP Setup Guide (Complete Step-by-Step)](#gcp-setup-guide-complete-step-by-step)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Windows Task Scheduler Setup](#windows-task-scheduler-setup)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Support & Maintenance](#support--maintenance)

---

## ✨ Features

### Core Functionality
- **Intelligent File Rename Detection**: Detects renamed files and moves them instead of re-downloading
- **Content-Based Comparison**: Uses checksums to skip unchanged content, saving bandwidth
- **Incremental Sync**: Only downloads changed/new files after the initial sync
- **Resume Capability**: Automatically resumes interrupted syncs from where they left off
- **Comprehensive Logging**: Detailed logs of all sync operations with timestamps
- **Error Recovery**: Automatic retry mechanism with exponential backoff

### Advanced Features
- **Duplicate Detection**: Identifies and cleans up duplicate files
- **Daily Change Logging**: Tracks what changed each day with detailed comparisons
- **File Signature Management**: Maintains checksums for intelligent comparison
- **Parallel Downloads**: Speeds up large-scale synchronization
- **Google Docs Support**: Optionally includes Google Docs, Sheets, Slides exports
- **Verification System**: Verifies all downloaded files match source

### Windows Integration
- **Batch Script Automation**: Simple `.bat` scripts for easy execution
- **PowerShell Health Checks**: Monitor sync system health and status
- **Windows Task Scheduler**: Automated daily/scheduled sync capability
- **Silent Mode**: Background sync without console windows

---

## 📦 Prerequisites

### System Requirements
- **OS**: Windows 10/11
- **RAM**: Minimum 4GB (recommended 8GB for large drives)
- **Storage**: Sufficient space for your entire Google Drive
- **Internet**: Stable connection (sync can pause and resume)

### Software Requirements
- **Python 3.8 or higher**: Download from [python.org](https://www.python.org/downloads/)
  - During installation, **MUST CHECK** "Add Python to PATH"
- **pip** (usually comes with Python)
- **Google Account**: With Google Drive access

### Required Python Packages
These will be installed in the Installation section:
```
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
```

---

## 🔐 GCP Setup Guide (Complete Step-by-Step)

This section walks you through creating a Google Cloud Project and obtaining credentials to run the sync system.

### Part 1: Create a Google Cloud Project

#### Step 1.1: Access Google Cloud Console
1. Open your web browser and go to: [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. If you don't have a Google account, create one at [https://accounts.google.com/signup](https://accounts.google.com/signup)
3. Sign in with your Google account

#### Step 1.2: Create a New Project
1. In the Google Cloud Console, look for the **Project Selector** at the top (shows current project name)
2. Click the **Project Selector** dropdown
3. Click the **NEW PROJECT** button in the popup
4. Fill in the project details:
   - **Project name**: Enter `Drive Sync` (or any name you prefer)
   - **Organization**: Leave blank (or select your organization if applicable)
   - **Location**: Leave as default
5. Click **CREATE** button
6. Wait for the project to be created (usually takes 30 seconds to 1 minute)
7. Once created, you'll see a notification. Click on it or navigate back to the project selector to view your new project

#### Step 1.3: Enable Required APIs
1. Once in your new project, click the **hamburger menu** (three horizontal lines) in the top-left corner
2. Navigate to: **APIs & Services** → **Library**
3. In the search box at the top, search for: `Google Drive API`
4. Click on **Google Drive API** from the results
5. Click the **ENABLE** button (blue button at the top)
6. Wait for the API to be enabled (you'll see "API enabled" confirmation)
7. Go back to the **APIs & Services** → **Library**
8. Search for: `Google Drive Activity API`
9. Click and **ENABLE** this API as well
10. Return to **APIs & Services** → **Library** one more time
11. Search for: `Google Picker API`
12. Click and **ENABLE** this API too

✅ **Verification**: Go to **APIs & Services** → **Enabled APIs and services**. You should see at least "Google Drive API" listed.

---

### Part 2: Create OAuth 2.0 Credentials

#### Step 2.1: Create OAuth Consent Screen
1. In Google Cloud Console, go to: **APIs & Services** → **OAuth consent screen**
2. Select **User Type**: Choose **External** (unless you're in a Google Workspace organization)
3. Click **CREATE**
4. Fill in the OAuth Consent Screen form:
   - **App name**: Enter `Drive Sync`
   - **User support email**: Enter your email address
   - **Developer contact information**: Enter your email address
5. Click **SAVE AND CONTINUE**
6. On the "Scopes" page, click **ADD OR REMOVE SCOPES**
7. In the search box, search for and select these scopes:
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/drive.file`
8. Click **UPDATE** and then **SAVE AND CONTINUE**
9. On the "Test users" page, click **ADD USERS**
10. Enter your email address as a test user
11. Click **ADD** then **SAVE AND CONTINUE**
12. Review your app information and click **BACK TO DASHBOARD**

✅ **Verification**: You should see "Testing" status on the OAuth consent screen.

#### Step 2.2: Create Desktop Application Credentials
1. In Google Cloud Console, go to: **APIs & Services** → **Credentials**
2. Click the **+ CREATE CREDENTIALS** button at the top
3. Select **OAuth Client ID** from the dropdown
4. For "Application Type", select: **Desktop Application**
5. Name it: `Drive Sync Client` (or any name)
6. Click **CREATE**
7. A popup will appear with your credentials. Click **DOWNLOAD** button
8. **IMPORTANT**: A `.json` file will be downloaded to your Downloads folder
9. **Rename this file to** `credentials.json`
10. **Move this file** to the Drive-Sync-update project folder (same location as the `.bat` and `.py` files)

⚠️ **IMPORTANT SECURITY NOTES**:
- Never share this `credentials.json` file with anyone
- Never commit it to public repositories (it will be in `.gitignore`)
- This file contains sensitive authentication information
- Keep multiple backups in a secure location

✅ **Verification**: Check that `credentials.json` exists in your project folder and contains JSON content starting with `{"installed": ...}`

---

### Part 3: Test Your GCP Setup

1. Open Command Prompt or PowerShell in your project folder
2. Run: `python validate_setup.py`
3. This will verify:
   - Python installation
   - Required packages
   - credentials.json file
   - Google Cloud API connectivity
4. If all checks pass ✅, your GCP setup is complete!

---

## 📥 Installation

### Step 0: Set Up Configuration Files from Examples

Before doing anything else, create your configuration files from the provided examples:

1. **Copy `config.example.json` to `config.json`**:
   ```cmd
   copy config.example.json config.json
   ```

2. **Copy `credentials.example.json` to `credentials.json`** (placeholder):
   ```cmd
   copy credentials.example.json credentials.json
   ```

3. **Update `config.json` with your folder ID**:
   - Open `config.json` in a text editor (Notepad, VS Code, etc.)
   - Find the line: `"folder_id": "YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE"`
   - Replace with your actual Google Drive folder ID (see [Finding Your Google Drive Folder ID](#finding-your-google-drive-folder-id))
   - Save the file

4. **You'll replace `credentials.json` later** after completing GCP setup (see Step 2.2 in the GCP guide)

### Step 1: Install Python Dependencies

1. Open **Command Prompt** or **PowerShell**
2. Navigate to the Drive-Sync-update folder:
   ```cmd
   cd C:\Path\To\Drive-Sync-update
   ```
3. Install required Python packages:
   ```cmd
   pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
   ```
4. Verify installation:
   ```cmd
   pip list
   ```
   You should see the three packages listed.

### Step 2: Verify Setup

Run the validation script to ensure everything is configured correctly:
```cmd
python validate_setup.py
```

Expected output:
```
✓ Python version 3.8+
✓ Required packages installed
✓ credentials.json found and valid
✓ Configuration file valid
✓ Folders structure ready
```

### Step 3: First-Time Authorization

The first time you run the sync, you'll need to authorize the application:

1. Run: `sync_intelligent.bat`
2. A browser window will open asking you to sign in to your Google account
3. Click **Allow** to grant Drive Sync permission to access your Google Drive
4. The browser will show a confirmation message
5. Return to the Command Prompt/PowerShell and the sync will begin

---

## ⚙️ Configuration

### config.json Overview

The `config.json` file controls all aspects of the sync. Here's what each section does:

```json
{
  "drive_settings": {
    "folder_id": "YOUR_FOLDER_ID",
    "folder_name": "PROJECT",
    "credentials_file": "credentials.json"
  },
  "local_settings": {
    "download_directory": "data",
    "logs_directory": "logs",
    "state_directory": "state",
    "temp_directory": "temp"
  },
  "sync_settings": {
    "chunk_size_mb": 1,
    "page_size": 25,
    "timeout_seconds": 600,
    "max_retries_per_file": 999,
    "retry_delay_base": 5,
    "max_retry_delay": 300,
    "verification_enabled": true,
    "incremental_sync_enabled": true
  },
  "scheduler_settings": {
    "daily_sync_enabled": true,
    "sync_time": "02:00",
    "max_runtime_hours": 12,
    "notification_enabled": true
  },
  "logging_settings": {
    "log_level": "INFO",
    "max_log_files": 30,
    "detailed_progress": true,
    "console_output": true
  },
  "advanced_settings": {
    "parallel_downloads": true,
    "bandwidth_limit_mbps": 0,
    "exclude_file_types": [],
    "include_google_docs": true,
    "checksum_verification": true
  }
}
```

### Key Configuration Options

#### Drive Settings
- **folder_id**: The Google Drive folder to sync. [See how to find your folder ID](#finding-your-google-drive-folder-id)
- **folder_name**: Display name for your folder
- **credentials_file**: Path to your `credentials.json` (default: `credentials.json`)

#### Sync Settings
- **chunk_size_mb**: Download chunk size (smaller = more stable, larger = faster) - **Default: 1MB** (recommended)
- **page_size**: Number of files to fetch per API call (25 is optimal)
- **timeout_seconds**: Maximum seconds to wait for API response (600 = 10 minutes)
- **max_retries_per_file**: How many times to retry failed downloads (999 = unlimited)
- **verification_enabled**: Verify downloads match source files (**recommended: true**)
- **incremental_sync_enabled**: Only download changed files (**recommended: true**)

#### Scheduler Settings
- **daily_sync_enabled**: Enable automatic daily syncs
- **sync_time**: Time to run sync (24-hour format, "HH:MM")
- **max_runtime_hours**: Maximum hours a sync can run before stopping
- **notification_enabled**: Show Windows notifications when done

#### Advanced Settings
- **parallel_downloads**: Download multiple files simultaneously (faster but more bandwidth)
- **bandwidth_limit_mbps**: Limit download speed (0 = unlimited)
- **exclude_file_types**: File extensions to skip (e.g., `[".tmp", ".exe"]`)
- **include_google_docs**: Export Google Docs/Sheets/Slides to PDF/XLSX
- **checksum_verification**: Use checksums to detect duplicate files

### Finding Your Google Drive Folder ID

1. Open [Google Drive](https://drive.google.com)
2. Navigate to the folder you want to sync
3. Look at the URL in your browser, it should look like:
   ```
   https://drive.google.com/drive/folders/1NiYBfZqkbXHuDLfDrfhNYlDETjdwKLRq?usp=sharing
   ```
4. Copy the long ID: `1NiYBfZqkbXHuDLfDrfhNYlDETjdwKLRq`
5. Replace the `folder_id` value in `config.json` with this ID
6. Save the file

---

## 🚀 Usage

### Basic Sync (Interactive)

Run the main sync script with a user interface:
```cmd
sync_intelligent.bat
```

This script:
- Shows detailed progress messages
- Pauses before and after execution
- Displays sync results and log file locations
- Useful for first-time sync or troubleshooting

### Silent Background Sync

Run sync without any console windows or prompts:
```cmd
sync_intelligent_silent.bat
```

This script:
- No pauses or user interaction
- Suitable for scheduled/automated runs
- Still logs everything to files
- Minimal resource usage

### Advanced: Direct Python Execution

For more control, run Python directly:
```cmd
python drive_sync_production.py
```

Or use the enhanced version with rename detection:
```cmd
python enhanced_drive_sync.py --mode intelligent
```

### Available Python Arguments

```cmd
python drive_sync_production.py [options]
  --resume              Resume a previous interrupted sync
  --verify-only         Only verify existing files, don't download
  --config <file>       Use custom config file
  --log-level <level>   Set log level (DEBUG, INFO, WARNING, ERROR)
```

### What Happens During Sync

1. **Authentication**: First time, opens browser for authorization
2. **Discovery**: Lists all files in your Drive folder
3. **Comparison**: Checks local copies against Drive (uses checksums)
4. **Download**: Downloads new/modified files only
5. **Verification**: Verifies downloads are complete and correct
6. **Logging**: Records all actions with timestamps
7. **State Saving**: Saves sync state for resume capability

### Understanding Log Files

After each sync, logs are saved in the `logs/` folder:

- **drive_sync_YYYYMMDD_HHMMSS.log** - Complete detailed log of sync operations
- **daily_changes_YYYYMMDD.json** - Machine-readable list of changes
- **daily_changes_YYYYMMDD.txt** - Human-readable summary of changes

Example log entry:
```
2025-03-23 18:45:23 - INFO - Starting sync for folder: DAIODE (1NiYBfZqkbXHuDLfDrfhNYlDETjdwKLRq)
2025-03-23 18:45:24 - INFO - Retrieving file list from Google Drive...
2025-03-23 18:45:25 - INFO - Found 156 files/folders
2025-03-23 18:45:26 - INFO - Comparing with local copy...
2025-03-23 18:45:30 - INFO - Download required for 12 files (5.2 GB total)
2025-03-23 18:47:45 - INFO - Sync completed successfully
```

---

## ⏱️ Windows Task Scheduler Setup

Automatically sync your drive on a schedule. This section shows how to set up automatic daily syncs.

### Manual Setup (Recommended for Beginners)

#### Step 1: Open Task Scheduler
1. Press `Win + R` to open the Run dialog
2. Type: `taskschd.msc`
3. Press Enter
4. Click "Yes" if prompted by User Account Control

#### Step 2: Create a New Task
1. In the right panel, click **Create Task**
2. In the "General" tab:
   - **Name**: `Google Drive Intelligent Sync`
   - **Description**: `Automatically sync Google Drive to local folder`
   - **Check**: "Run whether user is logged in or not"
   - **Check**: "Run with highest privileges"

#### Step 3: Configure Schedule
1. Go to the **Triggers** tab
2. Click **New**
3. Configure the trigger:
   - **Begin the task**: On a schedule
   - **Recurring**: Daily
   - **Start**: Pick today's date
   - **Repeat**: Every 1 day
   - **Time**: Set to your desired time (e.g., 2:00 AM)
   - **Check**: "Enabled"
4. Click **OK**

#### Step 4: Configure Action
1. Go to the **Actions** tab
2. Click **New**
3. Set action details:
   - **Action**: Start a program
   - **Program/script**: `C:\Windows\System32\cmd.exe`
   - **Add arguments**: `/c "C:\Path\To\Drive-Sync-update\sync_intelligent_silent.bat"`
   - **Start in**: `C:\Path\To\Drive-Sync-update`
4. Click **OK**

#### Step 5: Configure Conditions
1. Go to the **Conditions** tab
2. **Power**: Uncheck "Stop if the computer switches to battery power"
3. **Network**: Check "Start only if the following network connection is available"
4. Click **OK**

#### Step 6: Finish
1. Click **OK** to create the task
2. You may be prompted for your Windows password (required for elevated privileges)
3. The task is now created!

### Automated Setup

Use the provided setup script:
```cmd
setup_intelligent_scheduler.bat
```

This script will:
- Automatically create the scheduled task
- Set it to run daily at 2:00 AM
- Configure proper permissions
- Enable all necessary options

**Usage**:
```cmd
setup_intelligent_scheduler.bat
```

Follow the on-screen prompts to confirm.

### Testing Your Scheduled Task

1. In Task Scheduler, find your task in the list
2. Right-click on it
3. Select **Run** to test immediately
4. Check the logs folder to verify it ran successfully

### Adjusting Schedule

To change when the sync runs:
1. Open Task Scheduler
2. Find your task: `Google Drive Intelligent Sync`
3. Right-click → **Properties**
4. Go to **Triggers** tab
5. Double-click the trigger
6. Change the time
7. Click **OK** and **OK** again

### Disabling/Enabling Schedule

1. Open Task Scheduler
2. Find your task
3. Right-click → **Enable** or **Disable**

---

## 🔧 Troubleshooting

### Issue: "credentials.json not found"

**Cause**: The credentials file is missing or in the wrong location.

**Solution**:
1. Verify you completed the [GCP Setup Guide](#gcp-setup-guide-complete-step-by-step)
2. Ensure `credentials.json` is in the same folder as `sync_intelligent.bat`
3. Check the filename is exactly `credentials.json` (case-sensitive on some systems)
4. Re-download from GCP Console if needed

### Issue: "Failed to authenticate with Google"

**Cause**: Invalid credentials or expired token.

**Solution**:
1. Delete the `state/token.pickle` file
2. Run the sync again - it will re-authenticate
3. Verify your Google account and project are still valid
4. Check that OAuth consent screen is set up correctly

### Issue: "Folder ID not found in Google Drive"

**Cause**: Invalid folder ID or permission issues.

**Solution**:
1. Verify the folder ID in `config.json` is correct
2. Open Google Drive and navigate to the folder
3. Copy the folder ID from the URL again
4. Ensure your Google account has access to this folder
5. Try sharing the folder with yourself if issues persist

### Issue: Sync is very slow or freezes

**Cause**: Network issues, large files, or bandwidth limitations.

**Solution**:
1. Check your internet connection speed
2. Reduce `chunk_size_mb` in config.json (try 0.5 or 0.25)
3. Ensure no other programs are using bandwidth
4. Check logs for timeout errors
5. If it freezes, you can stop the sync (Ctrl+C) - it will resume next time

### Issue: "Too many retries" error

**Cause**: Google API rate limiting or network failures.

**Solution**:
1. Wait a few minutes before retrying
2. Reduce `page_size` in config.json from 25 to 10
3. Increase `max_retry_delay` from 300 to 600
4. Check Google Cloud Console for any API issues
5. Verify your internet connection is stable

### Issue: Files not downloading or stuck

**Cause**: Interrupted sync, permission issues, or corrupted state.

**Solution**:
1. Delete `state/sync_state.json` to start fresh
2. Re-run the sync
3. Check file permissions in Windows
4. Ensure the `data/` folder is not read-only
5. Try the enhanced version: `python enhanced_drive_sync.py`

### Issue: Script won't run/Invalid syntax error

**Cause**: Python not installed or not in PATH.

**Solution**:
1. Reinstall Python from [python.org](https://www.python.org/downloads/)
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Restart Command Prompt after installing Python
4. Verify: `python --version` should show your Python version
5. Reinstall packages: `pip install -r requirements.txt`

### Issue: Access denied/Permission error

**Cause**: Folder permissions or file lock.

**Solution**:
1. Ensure you own the `data/` folder or have write permissions
2. Close any files open from the `data/` folder
3. Run Command Prompt as Administrator
4. Check Windows file system for permission errors
5. Temporarily disable antivirus if it's blocking file operations

### Issue: Need to use a different Google Account

**Solution**:
1. Delete `state/token.pickle` file
2. Next sync will ask you to authenticate again
3. Sign in with the different Google account
4. Verify the folder ID is for the same account

### Health Check Script

Run the health check to diagnose system issues:

```cmd
health_check.bat
```

Or with PowerShell for more detailed info:
```powershell
powershell -ExecutionPolicy Bypass -File health_check.ps1
```

This will verify:
- Python installation and version
- All required packages
- credentials.json validity
- Google API connectivity
- Disk space available
- Network connectivity

---

## 📁 Project Structure

```
Drive-Sync-update/
├── README.md                          # This file - Complete documentation
├── config.json                        # Configuration settings (GITIGNORED - do not commit)
├── config.example.json                # Template config file (SAFE to commit - no credentials)
├── credentials.json                   # Google API credentials (GITIGNORED - do not commit)
├── credentials.example.json           # Template credentials file (SAFE to commit - no real credentials)
│
├── CORE SCRIPTS
├── drive_sync_production.py           # Main production-grade sync implementation
├── enhanced_drive_sync.py             # Enhanced version with intelligent features
├── drive_sync.py                      # Simple sync script (backup)
│
├── AUTOMATION SCRIPTS
├── sync_intelligent.bat               # Interactive sync (with pauses)
├── sync_intelligent_silent.bat        # Silent background sync
├── health_check.bat                   # Health check (batch version)
├── health_check.ps1                   # Health check (PowerShell)
├── setup_intelligent_scheduler.bat    # Setup Windows Task Scheduler
├── validate_setup.bat                 # Pre-flight validation
├── validate_setup.py                  # Python setup validator
│
├── STATE & LOGS (Auto-created)
├── state/
│   ├── sync_state.json               # Tracks sync progress
│   ├── token.pickle                  # Google OAuth token
│   └── file_signatures.json          # File checksums for deduplication
├── logs/
│   └── drive_sync_YYYYMMDD_HHMMSS.log  # Detailed operation logs
│
├── DATA (Where files are downloaded)
└── data/
    └── [Your Google Drive folder structure...]
```

### Key Files Explained

| File | Purpose | Edit? | Commit to Git? |
|------|---------|-------|---|
| `config.json` | All configuration settings | ✅ Yes, as needed | ❌ NO (in .gitignore) |
| `config.example.json` | Template configuration | ✅ Yes, for documentation | ✅ YES (no credentials) |
| `credentials.json` | Google API auth (SENSITIVE) | ❌ No, keep safe | ❌ NO (in .gitignore) |
| `credentials.example.json` | Template credentials | ✅ Yes, for documentation | ✅ YES (no real credentials) |
| `drive_sync_production.py` | Main sync logic | ❌ Only if modifying code | ✅ YES |
| `enhanced_drive_sync.py` | Enhanced features | ❌ Only if modifying code | ✅ YES |
| `sync_intelligent.bat` | User-facing script | ❌ Usually not needed | ✅ YES |
| `state/sync_state.json` | Sync progress tracking | ⚠️ Delete to restart sync | ❌ NO (in .gitignore) |
| `state/token.pickle` | OAuth token | ⚠️ Delete to re-authenticate | ❌ NO (in .gitignore) |
| `.gitignore` | Git ignore rules | ❌ Usually not needed | ✅ YES |

---

## 📦 Git and Version Control

### What's Safe to Commit to GitHub

The repository includes a `.gitignore` file that automatically prevents sensitive files from being committed. Here's what's included:

#### ✅ SAFE TO COMMIT (No credentials or sensitive data)
- `README.md` - Complete documentation
- `config.example.json` - Template configuration (placeholder values only)
- `credentials.example.json` - Template credentials (placeholder values only)
- All `*.py` files - Python source code
- All `*.bat` and `*.ps1` files - Automation scripts
- `.gitignore` - Git configuration
- `.claude/` settings

#### ❌ NEVER COMMIT (Automatically excluded by .gitignore)
- `config.json` - YOUR actual configuration with folder ID
- `credentials.json` - YOUR actual Google API credentials
- `data/` folder - YOUR downloaded files
- `logs/` folder - Contains file paths and sync history
- `state/` folder - Contains OAuth tokens and sync state
- `temp/` folder - Temporary files

### Setting Up for GitHub

1. **Initialize Git** (if not already done):
   ```cmd
   git init
   git add .
   git commit -m "Initial commit: Google Drive Sync System"
   ```

2. **Verify `.gitignore` is working**:
   ```cmd
   git status
   ```
   You should NOT see:
   - `config.json`
   - `credentials.json`
   - `data/`
   - `logs/`, `state/`, `temp/`
   - `.claude/settings.local.json`

3. **Create GitHub Repository**:
   - Go to [https://github.com/new](https://github.com/new)
   - Create new repository (e.g., `drive-sync-update`)
   - Add remote and push:
   ```cmd
   git remote add origin https://github.com/YOUR_USERNAME/drive-sync-update.git
   git branch -M main
   git push -u origin main
   ```

### For Users Cloning Your Repository

Users who clone your repository will need to:

1. **Copy example files to create their own configuration**:
   ```cmd
   copy config.example.json config.json
   copy credentials.example.json credentials.json
   ```

2. **Follow the GCP Setup Guide** to fill in actual credentials

3. **Update `config.json`** with their own folder ID

This way, they get your code and structure, but securely create their own configuration!

---

## 🛡️ Security Best Practices

### Protecting credentials.json

1. **Never commit to version control**: Add to `.gitignore`
2. **Never share**: Not with colleagues, not in support forums
3. **Restrict permissions**: Windows file properties → Security → Advanced
4. **Backup securely**: Store copies in encrypted cloud storage or offline
5. **Rotate periodically**: Generate new credentials every 6-12 months
6. **Monitor usage**: Check Google Account Security settings regularly

### Protecting Your Google Drive Access

1. **Enable 2-factor authentication** on your Google account
2. **Review connected apps** in Google Account settings
3. **Use folder sharing carefully** - only share Drive folder with trusted accounts
4. **Monitor sync logs** for unusual access patterns
5. **Set file permissions** appropriately - don't make everything public

---

## 📊 Monitoring & Maintenance

### Regular Tasks

**Daily**:
- Monitor sync logs for errors
- Check available disk space
- Verify recent files are synced

**Weekly**:
- Review logs for patterns
- Check disk usage in `data/` folder
- Verify Windows Task Scheduler is running

**Monthly**:
- Archive old log files (older than 30 days)
- Verify all critical files are downloaded
- Check Google Drive for organizational changes

**Quarterly**:
- Review and update `config.json` if needed
- Test disaster recovery (restore from backup)
- Update Python packages: `pip install --upgrade google-auth-oauthlib`

### Disk Space Management

Check available space:
```cmd
dir /s data\
```

If running low on disk:
1. Delete old log files in `logs/` folder (keep last 7 days)
2. Review and delete large unnecessary files from `data/`
3. Archive older data to external drive
4. Increase available storage or upgrade drive

### Log Rotation

Old logs are automatically archived. To manually clean:
```cmd
del logs\drive_sync_*.log
```

To keep logs for analysis, move them to an archive folder.

---

## 🆘 Support & Maintenance

### Getting Help

1. **Check the Troubleshooting section** above first
2. **Run health check**: `health_check.bat` or `health_check.ps1`
3. **Review logs**: Check `logs/` folder for error messages
4. **Validate setup**: Run `python validate_setup.py`

### Common Log Messages

| Message | Meaning | Action |
|---------|---------|--------|
| `Sync completed successfully` | Everything worked perfectly | ✅ No action needed |
| `Resume sync from checkpoint` | Continuing from previous sync | ✅ Normal operation |
| `File verification failed` | Downloaded file doesn't match source | ♻️ Will retry |
| `Folder not found` | folder_id is invalid | 🔧 Check folder ID in config.json |
| `Authentication failed` | credentials expired | 🔄 Delete token.pickle |
| `Chunk download timeout` | Network too slow | ⚙️ Reduce chunk_size_mb |

### Updating to Newer Version

To update Drive Sync while preserving your configuration:

1. Back up your `config.json` and `credentials.json`
2. Back up your `state/` folder
3. Download the new version
4. Copy your backed-up files back
5. Run validation: `python validate_setup.py`
6. Test with: `sync_intelligent.bat`

### Uninstalling

To completely remove Drive Sync:

1. Delete the Windows scheduled task (if created):
   - Open Task Scheduler
   - Find "Google Drive Intelligent Sync"
   - Delete it
2. Delete the Drive-Sync-update folder (or keep it for backup)
3. No other cleanup needed (no registry entries, no system changes)

⚠️ **Before deleting**: Back up your `data/` folder if it contains important files!

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-01-16 | Enhanced content intelligence, rename detection, deduplication |
| 1.0 | 2024-11-24 | Initial production release, core sync functionality |

---

## 📄 License & Attribution

This project is provided as-is for personal and organizational use.

### Credits

- Built with Google Drive API
- Python implementation using `google-auth-oauthlib` and `google-api-python-client`
- Windows integration via batch scripts and Task Scheduler

---

## ✅ Checklist: Before You Start

- [ ] Downloaded and installed Python 3.8+
- [ ] Created Google Cloud Project
- [ ] Enabled Google Drive API
- [ ] Created OAuth 2.0 credentials
- [ ] Downloaded and placed `credentials.json` in project folder
- [ ] Ran `validate_setup.py` successfully
- [ ] Updated `config.json` with your folder ID
- [ ] Ran first sync with `sync_intelligent.bat`
- [ ] Verified files downloaded to `data/` folder
- [ ] (Optional) Set up Windows Task Scheduler for automatic sync

---

## 🎯 Next Steps

1. **Complete the GCP Setup**: Follow [Part 1-3](#gcp-setup-guide-complete-step-by-step) carefully
2. **Run first sync**: Execute `sync_intelligent.bat`
3. **Check results**: Review the `data/` folder and `logs/` folder
4. **Set up automation** (optional): Run `setup_intelligent_scheduler.bat`
5. **Monitor**: Check logs regularly to ensure smooth operation

---

**Questions?** Check the **Troubleshooting** section or review the detailed logs in the `logs/` folder.

**Happy syncing!** 🚀

---

*Last Updated: 2025-03-23*
*For updates and support, ensure you're using the latest version from the repository.*
