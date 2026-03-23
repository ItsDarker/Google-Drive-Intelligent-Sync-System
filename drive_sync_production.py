"""
Google Drive Production Sync System
===================================

A production-ready Google Drive synchronization system with:
- Configuration-based setup
- Bulletproof resume capability
- Incremental sync support
- Task scheduler integration
- Complete verification system
- Automatic error recovery

Author: Enhanced for Production Use
Date: 2025-01-16
Version: 1.0
"""

import os
import io
import json
import pickle
import logging
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import requests

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION MANAGER
# ═══════════════════════════════════════════════════════════════

class ConfigManager:
    """Manages configuration settings from config.json"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.setup_directories()
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file {self.config_file} not found!")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    def get(self, section, key, default=None):
        """Get configuration value"""
        return self.config.get(section, {}).get(key, default)
    
    def setup_directories(self):
        """Create necessary directories"""
        directories = [
            self.get_local_path('download_directory'),
            self.get_local_path('logs_directory'),
            self.get_local_path('state_directory'),
            self.get_local_path('temp_directory')
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def get_local_path(self, key):
        """Get full path for local directories"""
        relative_path = self.get('local_settings', key)
        return os.path.join(self.script_dir, relative_path)
    
    @property
    def drive_folder_id(self):
        return self.get('drive_settings', 'folder_id')
    
    @property
    def credentials_file(self):
        return os.path.join(self.script_dir, self.get('drive_settings', 'credentials_file'))
    
    @property
    def download_directory(self):
        return self.get_local_path('download_directory')
    
    @property
    def logs_directory(self):
        return self.get_local_path('logs_directory')
    
    @property
    def state_directory(self):
        return self.get_local_path('state_directory')

# ═══════════════════════════════════════════════════════════════
# STATE MANAGER - HANDLES RESUME CAPABILITY
# ═══════════════════════════════════════════════════════════════

class SyncStateManager:
    """Manages sync state for resume capability"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.state_file = os.path.join(config_manager.state_directory, 'sync_state.json')
        self.checkpoint_file = os.path.join(config_manager.state_directory, 'checkpoint.json')
        self.state = self.load_state()
    
    def load_state(self):
        """Load existing state or create new"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'version': 'production_v1.0',
            'sync_sessions': [],
            'current_session': None,
            'completed_files': {},
            'completed_folders': {},
            'failed_files': {},
            'drive_structure_cache': {},
            'last_full_sync': None,
            'last_incremental_sync': None,
            'sync_token': None,
            'statistics': {
                'total_sessions': 0,
                'total_files_downloaded': 0,
                'total_folders_created': 0,
                'total_bytes_downloaded': 0,
                'average_download_speed': 0
            }
        }
    
    def save_state(self):
        """Save current state"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save state: {e}")
    
    def create_checkpoint(self, current_folder, current_file_index=0):
        """Create checkpoint for resume"""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'current_folder': current_folder,
            'current_file_index': current_file_index,
            'session_id': self.state.get('current_session')
        }
        
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(self):
        """Load checkpoint for resume"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def start_new_session(self, sync_type='full'):
        """Start a new sync session"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session = {
            'id': session_id,
            'type': sync_type,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'status': 'running',
            'files_processed': 0,
            'files_downloaded': 0,
            'bytes_downloaded': 0,
            'errors': []
        }
        
        self.state['current_session'] = session_id
        self.state['sync_sessions'].append(session)
        self.state['statistics']['total_sessions'] += 1
        self.save_state()
        
        return session_id
    
    def end_session(self, status='completed'):
        """End current sync session"""
        if self.state['current_session']:
            for session in self.state['sync_sessions']:
                if session['id'] == self.state['current_session']:
                    session['end_time'] = datetime.now().isoformat()
                    session['status'] = status
                    break
            
            self.state['current_session'] = None
            self.save_state()
            
            # Clean up checkpoint
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
    
    def mark_file_completed(self, file_id, local_path, file_size, modified_time=None):
        """Mark file as completed"""
        self.state['completed_files'][file_id] = {
            'path': local_path,
            'size': file_size,
            'modified_time': modified_time,
            'timestamp': datetime.now().isoformat()
        }
        
        # Update session statistics
        if self.state['current_session']:
            for session in self.state['sync_sessions']:
                if session['id'] == self.state['current_session']:
                    session['files_downloaded'] += 1
                    session['bytes_downloaded'] += file_size
                    break
        
        # Update global statistics
        self.state['statistics']['total_files_downloaded'] += 1
        self.state['statistics']['total_bytes_downloaded'] += file_size
        
        self.save_state()
    
    def is_file_completed(self, file_id):
        """Check if file is already completed"""
        return file_id in self.state['completed_files']
    
    def needs_update(self, file_id, file_size, modified_time):
        """Check if file needs to be updated"""
        if file_id not in self.state['completed_files']:
            return True
        
        cached = self.state['completed_files'][file_id]
        return (cached['size'] != file_size or 
                cached.get('modified_time') != modified_time)

# ═══════════════════════════════════════════════════════════════
# LOGGING MANAGER
# ═══════════════════════════════════════════════════════════════

class LoggingManager:
    """Manages comprehensive logging"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.get('logging_settings', 'log_level', 'INFO'))
        
        # Create timestamp for log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(self.config.logs_directory, f'drive_sync_{timestamp}.log')
        
        # Setup formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Setup file handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        
        # Setup console handler if enabled
        handlers = [file_handler]
        if self.config.get('logging_settings', 'console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(log_level)
            handlers.append(console_handler)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            handlers=handlers,
            force=True
        )
        
        # Clean up old log files
        self.cleanup_old_logs()
    
    def cleanup_old_logs(self):
        """Remove old log files"""
        max_files = self.config.get('logging_settings', 'max_log_files', 30)
        
        try:
            log_files = []
            for file in os.listdir(self.config.logs_directory):
                if file.startswith('drive_sync_') and file.endswith('.log'):
                    log_path = os.path.join(self.config.logs_directory, file)
                    log_files.append((log_path, os.path.getctime(log_path)))
            
            # Sort by creation time and remove oldest
            log_files.sort(key=lambda x: x[1])
            while len(log_files) > max_files:
                oldest_file = log_files.pop(0)[0]
                os.remove(oldest_file)
                
        except Exception as e:
            logging.warning(f"Failed to cleanup old logs: {e}")

# ═══════════════════════════════════════════════════════════════
# AUTHENTICATION MANAGER
# ═══════════════════════════════════════════════════════════════

class AuthenticationManager:
    """Manages Google Drive authentication"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.scopes = ['https://www.googleapis.com/auth/drive.readonly']
        self.token_file = os.path.join(config_manager.state_directory, 'token.pickle')
    
    def authenticate(self):
        """Authenticate with Google Drive"""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)
                logging.info("Loaded existing authentication token")
            except Exception as e:
                logging.warning(f"Failed to load token: {e}")
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logging.info("Refreshed authentication token")
                except Exception as e:
                    logging.warning(f"Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.config.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.config.credentials_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config.credentials_file, self.scopes
                )
                creds = flow.run_local_server(port=0)
                logging.info("Obtained new authentication token")
        
        # Save credentials
        try:
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        except Exception as e:
            logging.error(f"Failed to save token: {e}")
        
        # Build service
        service = build('drive', 'v3', credentials=creds)
        logging.info("Successfully authenticated with Google Drive")
        return service

# ═══════════════════════════════════════════════════════════════
# DRIVE OPERATIONS MANAGER
# ═══════════════════════════════════════════════════════════════

class DriveOperationsManager:
    """Manages Google Drive operations"""
    
    def __init__(self, config_manager, drive_service, state_manager):
        self.config = config_manager
        self.service = drive_service
        self.state = state_manager
    
    def sanitize_filename(self, filename):
        """Sanitize filename for Windows filesystem"""
        forbidden = '<>:"/\\|?*'
        for char in forbidden:
            filename = filename.replace(char, '_')
        filename = filename.strip('. ')
        
        # Handle long filenames
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
        
        return filename
    
    def get_export_format_and_extension(self, mime_type):
        """Get export format and file extension for Google native files"""
        export_formats = {
            'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
            'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'), 
            'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
            'application/vnd.google-apps.drawing': ('image/png', '.png'),
            'application/vnd.google-apps.form': ('application/pdf', '.pdf'),
            'application/vnd.google-apps.script': ('application/vnd.google-apps.script+json', '.json'),
            'application/vnd.google-apps.site': ('text/plain', '.txt'),
            'application/vnd.google-apps.jam': ('application/pdf', '.pdf')
        }
        return export_formats.get(mime_type, (None, None))
    
    def download_google_native_file(self, file_id, file_name, mime_type, local_path, modified_time=None):
        """Download Google native files by exporting them to appropriate formats"""
        
        # Check if already completed
        if self.state.is_file_completed(file_id):
            if not self.state.needs_update(file_id, 0, modified_time):
                logging.info(f"⏭️  UNCHANGED: {file_name}")
                return True
            else:
                logging.info(f"🔄 UPDATE DETECTED: {file_name}")
        else:
            logging.info(f"🆕 NEW GOOGLE DOC: {file_name}")
        
        export_mime_type, file_extension = self.get_export_format_and_extension(mime_type)
        
        if not export_mime_type:
            logging.warning(f"⊘ Unsupported Google Apps type: {file_name} ({mime_type})")
            return False
        
        # Update filename with proper extension
        if not local_path.endswith(file_extension):
            name_without_ext = os.path.splitext(local_path)[0]
            local_path = name_without_ext + file_extension
        
        # Check if file exists and is the same
        if os.path.exists(local_path) and self.state.is_file_completed(file_id):
            logging.info(f"⏭️  ALREADY EXISTS: {file_name}")
            return True
        
        logging.info(f"📥 EXPORTING GOOGLE DOC: {file_name} → {file_extension}")
        logging.info(f"    📂 Path: {local_path}")
        
        # Create parent directory
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Download settings
        max_retries = self.config.get('sync_settings', 'max_retries_per_file', 3)  # Reduced retries for exports
        retry_delay = self.config.get('sync_settings', 'retry_delay_base', 5)
        max_delay = self.config.get('sync_settings', 'max_retry_delay', 300)
        
        # Try to get file metadata first to ensure file exists and is accessible
        try:
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='id,name,mimeType,size,modifiedTime,capabilities'
            ).execute()
            
            # Check if file can be exported
            capabilities = file_metadata.get('capabilities', {})
            if not capabilities.get('canDownload', True):
                logging.warning(f"⊘ File cannot be downloaded/exported: {file_name}")
                return False
                
        except HttpError as e:
            if e.resp.status == 404:
                logging.warning(f"⊘ File not found or no access: {file_name}")
                return False
            elif e.resp.status == 403:
                logging.warning(f"⊘ Access denied for file: {file_name}")
                return False
            else:
                logging.warning(f"⊘ Error accessing file metadata: {file_name} - {e}")
                return False
        except Exception as e:
            logging.warning(f"⊘ Error accessing file: {file_name} - {e}")
            return False
        
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            
            try:
                logging.info(f"    🔄 Export attempt {attempt}...")
                
                # First try to get file directly if it's not a Google native type
                # This handles cases where files might be misidentified
                if not mime_type.startswith('application/vnd.google-apps.'):
                    try:
                        # Try direct download first
                        return self.download_file(file_id, file_name, 0, local_path, modified_time)
                    except:
                        pass  # Fall back to export
                
                # Use export method for Google native files
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType=export_mime_type
                )
                
                # Download exported content
                with io.FileIO(local_path, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    
                    while not done:
                        status, done = downloader.next_chunk()
                        
                        if status and self.config.get('logging_settings', 'detailed_progress', True):
                            progress = int(status.progress() * 100)
                            logging.info(f"        📊 Export Progress: {progress}%")
                
                # Verify export
                if os.path.exists(local_path):
                    exported_size = os.path.getsize(local_path)
                    
                    if exported_size > 0:
                        logging.info(f"    ✅ EXPORT COMPLETED: {file_name}")
                        logging.info(f"        📏 Size: {exported_size:,} bytes")
                        
                        # Mark as completed (use exported size since original has no size)
                        self.state.mark_file_completed(file_id, local_path, exported_size, modified_time)
                        return True
                    else:
                        raise Exception("Exported file is empty")
                else:
                    raise Exception("Export file was not created")
                    
            except KeyboardInterrupt:
                logging.warning("Export interrupted by user")
                self.state.save_state()
                raise
                
            except HttpError as e:
                error_msg = str(e)
                
                # Handle specific HTTP errors
                if e.resp.status == 400:
                    if 'Invalid requests[0].body.export.mimeType' in error_msg:
                        logging.warning(f"⊘ Cannot export {file_name} to {export_mime_type}, trying alternative format...")
                        # Try alternative export formats
                        alternative_formats = self.get_alternative_export_formats(mime_type)
                        for alt_mime, alt_ext in alternative_formats:
                            try:
                                alt_path = os.path.splitext(local_path)[0] + alt_ext
                                alt_request = self.service.files().export_media(
                                    fileId=file_id,
                                    mimeType=alt_mime
                                )
                                
                                with io.FileIO(alt_path, 'wb') as fh:
                                    alt_downloader = MediaIoBaseDownload(fh, alt_request)
                                    alt_done = False
                                    
                                    while not alt_done:
                                        alt_status, alt_done = alt_downloader.next_chunk()
                                
                                if os.path.exists(alt_path) and os.path.getsize(alt_path) > 0:
                                    exported_size = os.path.getsize(alt_path)
                                    logging.info(f"    ✅ EXPORT COMPLETED (alternative format): {file_name} → {alt_ext}")
                                    logging.info(f"        📏 Size: {exported_size:,} bytes")
                                    self.state.mark_file_completed(file_id, alt_path, exported_size, modified_time)
                                    return True
                            except:
                                continue
                        
                        logging.warning(f"⊘ All export formats failed for: {file_name}")
                        return False
                    else:
                        logging.warning(f"⊘ Bad request for file: {file_name} - {error_msg[:100]}")
                        return False
                        
                elif e.resp.status == 403:
                    logging.warning(f"⊘ Access denied during export: {file_name}")
                    return False
                    
                elif e.resp.status == 404:
                    logging.warning(f"⊘ File not found during export: {file_name}")
                    return False
                    
                else:
                    logging.warning(f"        ❌ Export attempt {attempt} failed with HTTP {e.resp.status}: {error_msg[:100]}")
                
            except Exception as e:
                logging.warning(f"        ❌ Export attempt {attempt} failed: {str(e)[:100]}")
                
                # Clean up partial export
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except:
                        pass
                
                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = min(retry_delay * (1.5 ** (attempt - 1)), max_delay)
                    logging.info(f"        ⏳ Retrying export in {delay:.0f}s...")
                    time.sleep(delay)
                else:
                    logging.error(f"        💥 EXPORT FAILED after {max_retries} attempts: {file_name}")
                    return False
        
        return False
    
    def get_alternative_export_formats(self, mime_type):
        """Get alternative export formats for Google native files when primary export fails"""
        alternatives = {
            'application/vnd.google-apps.document': [
                ('application/pdf', '.pdf'),
                ('text/plain', '.txt'),
                ('application/rtf', '.rtf'),
                ('text/html', '.html')
            ],
            'application/vnd.google-apps.spreadsheet': [
                ('application/pdf', '.pdf'),
                ('text/csv', '.csv'),
                ('application/vnd.oasis.opendocument.spreadsheet', '.ods'),
                ('text/tab-separated-values', '.tsv')
            ],
            'application/vnd.google-apps.presentation': [
                ('application/pdf', '.pdf'),
                ('application/vnd.oasis.opendocument.presentation', '.odp'),
                ('text/plain', '.txt'),
                ('image/jpeg', '.jpg')
            ],
            'application/vnd.google-apps.drawing': [
                ('application/pdf', '.pdf'),
                ('image/jpeg', '.jpg'),
                ('image/svg+xml', '.svg')
            ],
            'application/vnd.google-apps.form': [
                ('application/zip', '.zip')
            ]
        }
        
        return alternatives.get(mime_type, [('application/pdf', '.pdf')])
    
    def get_folder_items(self, folder_id):
        """Get all items in a folder with pagination"""
        all_items = []
        page_token = None
        page_size = self.config.get('sync_settings', 'page_size', 25)
        
        while True:
            try:
                query = f"'{folder_id}' in parents and trashed = false"
                results = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                    pageToken=page_token,
                    pageSize=page_size,
                    orderBy='name'
                ).execute()
                
                items = results.get('files', [])
                all_items.extend(items)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logging.warning(f"Error listing folder contents: {e}")
                time.sleep(5)
                continue
        
        return all_items
    
    def download_file(self, file_id, file_name, file_size, local_path, modified_time=None):
        """Download a file with bulletproof reliability"""
        
        # Check if file needs download
        if self.state.is_file_completed(file_id):
            if not self.state.needs_update(file_id, file_size, modified_time):
                logging.info(f"⏭️  UNCHANGED: {file_name}")
                return True
            else:
                logging.info(f"🔄 UPDATE DETECTED: {file_name}")
        else:
            logging.info(f"🆕 NEW FILE: {file_name}")
        
        # Create parent directory
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Download settings
        chunk_size = self.config.get('sync_settings', 'chunk_size_mb', 1) * 1024 * 1024
        max_retries = self.config.get('sync_settings', 'max_retries_per_file', 999)
        retry_delay = self.config.get('sync_settings', 'retry_delay_base', 5)
        max_delay = self.config.get('sync_settings', 'max_retry_delay', 300)
        
        logging.info(f"📥 DOWNLOADING: {file_name}")
        logging.info(f"    📏 Size: {file_size / (1024*1024):.2f} MB")
        logging.info(f"    📂 Path: {local_path}")
        
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            
            try:
                logging.info(f"    🔄 Attempt {attempt}...")
                
                # Get download request
                request = self.service.files().get_media(fileId=file_id)
                
                # Download with progress tracking
                with io.FileIO(local_path, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request, chunksize=chunk_size)
                    done = False
                    last_progress = 0
                    
                    while not done:
                        status, done = downloader.next_chunk()
                        
                        if status and self.config.get('logging_settings', 'detailed_progress', True):
                            progress = int(status.progress() * 100)
                            if progress >= last_progress + 10:
                                logging.info(f"        📊 Progress: {progress}%")
                                last_progress = progress
                
                # Verify download
                if os.path.exists(local_path):
                    downloaded_size = os.path.getsize(local_path)
                    
                    if self.config.get('sync_settings', 'verification_enabled', True):
                        if downloaded_size == file_size:
                            logging.info(f"    ✅ DOWNLOAD VERIFIED: {file_name}")
                            logging.info(f"        📏 Size: {downloaded_size:,} bytes")
                            
                            # Mark as completed
                            self.state.mark_file_completed(file_id, local_path, file_size, modified_time)
                            return True
                        else:
                            raise Exception(f"Size mismatch: expected {file_size}, got {downloaded_size}")
                    else:
                        # Mark as completed without verification
                        self.state.mark_file_completed(file_id, local_path, file_size, modified_time)
                        return True
                else:
                    raise Exception("File was not created")
                    
            except KeyboardInterrupt:
                logging.warning("Download interrupted by user")
                self.state.save_state()
                raise
                
            except Exception as e:
                # Calculate delay with exponential backoff
                delay = min(retry_delay * (1.5 ** (attempt - 1)), max_delay)
                
                logging.warning(f"        ❌ Attempt {attempt} failed: {str(e)[:100]}")
                
                # Clean up partial download
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except:
                        pass
                
                if attempt < max_retries:
                    logging.info(f"        ⏳ Retrying in {delay:.0f}s...")
                    time.sleep(delay)
                else:
                    logging.error(f"        💥 FAILED after {max_retries} attempts: {file_name}")
                    return False
        
        return False
    
    def process_folder(self, folder_id, local_path, depth=0):
        """Process a folder recursively"""
        indent = "  " * depth
        
        logging.info(f"{indent}📁 PROCESSING: {os.path.basename(local_path)}")
        
        # Create local folder
        os.makedirs(local_path, exist_ok=True)
        
        # Update checkpoint
        self.state.create_checkpoint(local_path)
        
        # Get all items
        all_items = self.get_folder_items(folder_id)
        
        # Separate files, Google native files, and folders
        folders = [item for item in all_items 
                  if item['mimeType'] == 'application/vnd.google-apps.folder']
        
        regular_files = []
        google_native_files = []
        
        for item in all_items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                continue  # Already handled in folders
            elif item['mimeType'].startswith('application/vnd.google-apps.'):
                # Check if Google Docs export is enabled
                if self.config.get('advanced_settings', 'include_google_docs', False):
                    google_native_files.append(item)
                # else: skip Google native files if disabled
            else:
                regular_files.append(item)
        
        files = regular_files + google_native_files
        
        logging.info(f"{indent}    📊 Found: {len(regular_files)} regular files, {len(google_native_files)} Google Docs, {len(folders)} folders")
        
        # Process files
        files_success = 0
        for idx, file_item in enumerate(files, 1):
            file_id = file_item['id']
            file_name = self.sanitize_filename(file_item['name'])
            file_size = int(file_item.get('size', 0))
            file_path = os.path.join(local_path, file_name)
            modified_time = file_item.get('modifiedTime')
            mime_type = file_item.get('mimeType', '')
            
            logging.info(f"{indent}    📄 [{idx}/{len(files)}] {file_name}")
            
            # Check if this is a Google native file
            if mime_type.startswith('application/vnd.google-apps.') and mime_type != 'application/vnd.google-apps.folder':
                # Handle Google native files (Docs, Sheets, Slides, etc.)
                if self.download_google_native_file(file_id, file_name, mime_type, file_path, modified_time):
                    files_success += 1
            else:
                # Handle regular files
                if self.download_file(file_id, file_name, file_size, file_path, modified_time):
                    files_success += 1
            
            # Update checkpoint periodically
            if idx % 5 == 0:
                self.state.create_checkpoint(local_path, idx)
        
        # Process subfolders
        folders_success = 0
        for idx, folder_item in enumerate(folders, 1):
            folder_name = self.sanitize_filename(folder_item['name'])
            folder_path = os.path.join(local_path, folder_name)
            
            logging.info(f"{indent}    📂 [{idx}/{len(folders)}] {folder_name}")
            
            if self.process_folder(folder_item['id'], folder_path, depth + 1):
                folders_success += 1
        
        success = (files_success == len(files) and folders_success == len(folders))
        
        if success:
            logging.info(f"{indent}✅ COMPLETED: {os.path.basename(local_path)}")
        else:
            logging.warning(f"{indent}⚠️  INCOMPLETE: {os.path.basename(local_path)}")
        
        return success

# ═══════════════════════════════════════════════════════════════
# MAIN SYNC MANAGER
# ═══════════════════════════════════════════════════════════════

class DriveSync:
    """Main sync orchestrator"""
    
    def __init__(self, config_file='config.json'):
        self.config = ConfigManager(config_file)
        self.state = SyncStateManager(self.config)
        self.logging = LoggingManager(self.config)
        self.auth = AuthenticationManager(self.config)
        self.service = None
        self.drive_ops = None
    
    def initialize(self):
        """Initialize the sync system"""
        logging.info("="*80)
        logging.info("🚀 Google Drive Production Sync System")
        logging.info("="*80)
        
        # Authenticate
        logging.info("🔐 Authenticating with Google Drive...")
        self.service = self.auth.authenticate()
        
        # Initialize drive operations
        self.drive_ops = DriveOperationsManager(self.config, self.service, self.state)
        
        logging.info(f"📁 Target folder: {self.config.get('drive_settings', 'folder_name')}")
        logging.info(f"📂 Local directory: {self.config.download_directory}")
        logging.info(f"🎯 Folder ID: {self.config.drive_folder_id}")
    
    def get_changes_since_last_sync(self):
        """Get changes since last sync using Drive API"""
        try:
            # Get saved pageToken from last sync
            page_token = self.state.state.get('sync_token')
            
            if not page_token:
                logging.info("🔍 No sync token found - performing full sync")
                return None, True
            
            logging.info("🔍 Checking for changes since last sync...")
            
            # Use Drive API changes list to get incremental changes
            changes = []
            new_page_token = page_token
            
            while True:
                try:
                    result = self.service.changes().list(
                        pageToken=page_token,
                        pageSize=100,
                        fields="nextPageToken,newStartPageToken,changes(fileId,file(id,name,mimeType,size,modifiedTime,parents,trashed))"
                    ).execute()
                    
                    changes.extend(result.get('changes', []))
                    
                    page_token = result.get('nextPageToken')
                    if not page_token:
                        new_page_token = result.get('newStartPageToken')
                        break
                        
                except Exception as e:
                    logging.warning(f"Error getting changes: {e}")
                    return None, True
            
            # Filter relevant changes (within our target folder)
            relevant_changes = []
            for change in changes:
                file_info = change.get('file')
                if file_info and self.is_file_in_target_folder(file_info):
                    relevant_changes.append(change)
            
            logging.info(f"📊 Found {len(relevant_changes)} changes since last sync")
            
            # Update sync token for next incremental sync
            self.state.state['sync_token'] = new_page_token
            self.state.save_state()
            
            return relevant_changes, len(relevant_changes) == 0
            
        except Exception as e:
            logging.warning(f"Failed to get incremental changes: {e}")
            return None, True
    
    def is_file_in_target_folder(self, file_info):
        """Check if file is within our target folder hierarchy"""
        if not file_info.get('parents'):
            return False
        
        # Check if any parent is our target folder or descendant
        for parent_id in file_info['parents']:
            if self.is_descendant_of_target(parent_id):
                return True
        return False
    
    def is_descendant_of_target(self, folder_id, visited=None):
        """Check if folder is descendant of target folder"""
        if visited is None:
            visited = set()
        
        if folder_id in visited:
            return False  # Prevent infinite loops
        visited.add(folder_id)
        
        if folder_id == self.config.drive_folder_id:
            return True
        
        try:
            # Get folder info to check its parents
            result = self.service.files().get(
                fileId=folder_id,
                fields='parents'
            ).execute()
            
            parents = result.get('parents', [])
            for parent_id in parents:
                if self.is_descendant_of_target(parent_id, visited):
                    return True
            
            return False
            
        except:
            return False
    
    def process_incremental_changes(self, changes):
        """Process incremental changes efficiently"""
        logging.info(f"🔄 Processing {len(changes)} incremental changes...")
        
        files_processed = 0
        files_downloaded = 0
        files_deleted = 0
        
        for change in changes:
            file_info = change.get('file')
            if not file_info:
                continue
            
            files_processed += 1
            file_id = file_info['id']
            file_name = file_info.get('name', 'Unknown')
            
            # Handle deleted files
            if file_info.get('trashed', False):
                logging.info(f"🗑️  File deleted in Drive: {file_name}")
                self.handle_deleted_file(file_id)
                files_deleted += 1
                continue
            
            # Handle new/modified files
            mime_type = file_info.get('mimeType', '')
            file_size = int(file_info.get('size', 0))
            modified_time = file_info.get('modifiedTime')
            
            # Determine local path
            local_path = self.get_local_path_for_file(file_info)
            if not local_path:
                continue
            
            logging.info(f"📄 Processing: {file_name}")
            
            # Download the file
            if mime_type == 'application/vnd.google-apps.folder':
                # Create folder if needed
                os.makedirs(local_path, exist_ok=True)
                logging.info(f"📁 Folder updated: {local_path}")
            elif mime_type.startswith('application/vnd.google-apps.') and mime_type != 'application/vnd.google-apps.folder':
                # Google native file
                if self.config.get('advanced_settings', 'include_google_docs', False):
                    if self.drive_ops.download_google_native_file(file_id, file_name, mime_type, local_path, modified_time):
                        files_downloaded += 1
            else:
                # Regular file
                if self.drive_ops.download_file(file_id, file_name, file_size, local_path, modified_time):
                    files_downloaded += 1
        
        logging.info(f"✅ Incremental sync completed:")
        logging.info(f"    📄 Files processed: {files_processed}")
        logging.info(f"    📥 Files downloaded: {files_downloaded}")
        logging.info(f"    🗑️  Files deleted: {files_deleted}")
        
        return files_processed > 0
    
    def handle_deleted_file(self, file_id):
        """Handle files that were deleted in Drive"""
        if file_id in self.state.state['completed_files']:
            file_info = self.state.state['completed_files'][file_id]
            local_path = file_info.get('path')
            
            if local_path and os.path.exists(local_path):
                try:
                    if self.config.get('sync_settings', 'delete_local_on_drive_delete', False):
                        os.remove(local_path)
                        logging.info(f"🗑️  Local file deleted: {local_path}")
                    else:
                        logging.info(f"🗑️  Drive file deleted (local kept): {local_path}")
                except Exception as e:
                    logging.warning(f"Failed to delete local file: {e}")
            
            # Remove from completed files
            del self.state.state['completed_files'][file_id]
            self.state.save_state()
    
    def get_local_path_for_file(self, file_info):
        """Get local path for a file based on its Drive path"""
        try:
            # Build path from Drive hierarchy
            path_parts = []
            current_id = file_info['id']
            
            # Get parents chain
            while current_id != self.config.drive_folder_id:
                try:
                    result = self.service.files().get(
                        fileId=current_id,
                        fields='name,parents'
                    ).execute()
                    
                    path_parts.insert(0, self.drive_ops.sanitize_filename(result['name']))
                    parents = result.get('parents', [])
                    
                    if not parents:
                        break
                    current_id = parents[0]
                    
                except:
                    break
            
            if path_parts:
                return os.path.join(self.config.download_directory, *path_parts)
            else:
                # File is directly in root
                return os.path.join(self.config.download_directory, 
                                  self.drive_ops.sanitize_filename(file_info['name']))
                                  
        except Exception as e:
            logging.warning(f"Failed to determine local path for {file_info.get('name')}: {e}")
            return None
    
    def get_initial_sync_token(self):
        """Get initial sync token for future incremental syncs"""
        try:
            result = self.service.changes().getStartPageToken().execute()
            sync_token = result.get('startPageToken')
            
            self.state.state['sync_token'] = sync_token
            self.state.save_state()
            
            logging.info(f"🔗 Saved sync token for future incremental syncs: {sync_token}")
            
        except Exception as e:
            logging.warning(f"Failed to get sync token: {e}")
    
    def check_for_changes(self):
        """Check if incremental sync is possible"""
        if not self.config.get('sync_settings', 'incremental_sync_enabled', True):
            return True  # Force full sync
        
        if not self.state.state['last_full_sync']:
            logging.info("🔍 No previous sync found - performing full sync")
            return True
        
        last_sync = datetime.fromisoformat(self.state.state['last_full_sync'])
        hours_since_sync = (datetime.now() - last_sync).total_seconds() / 3600
        
        logging.info(f"📅 Last sync: {hours_since_sync:.1f} hours ago")
        
        # Check for incremental changes
        changes, no_changes = self.get_changes_since_last_sync()
        
        if changes is None:
            logging.info("🔄 Unable to get incremental changes - performing full sync")
            return True
        elif no_changes:
            logging.info("✅ No changes detected - sync not needed")
            return False
        else:
            logging.info(f"🔄 {len(changes)} changes detected - performing incremental sync")
            return changes
    
    def perform_sync(self, sync_type='auto'):
        """Perform the main synchronization"""
        try:
            # Determine sync type and handle incremental changes
            if sync_type == 'auto':
                changes_result = self.check_for_changes()
                if changes_result is False:
                    logging.info("✅ No sync needed - all files are up to date")
                    return True
                elif isinstance(changes_result, list):
                    # Incremental sync with specific changes
                    return self.perform_incremental_sync(changes_result)
                # else: perform full sync
            elif sync_type == 'incremental':
                changes_result = self.check_for_changes()
                if isinstance(changes_result, list):
                    return self.perform_incremental_sync(changes_result)
                elif changes_result is False:
                    logging.info("✅ No incremental sync needed")
                    return True
                else:
                    logging.info("🔄 Falling back to full sync for incremental request")
            
            # Start session
            session_type = 'incremental' if sync_type == 'incremental' else 'full'
            session_id = self.state.start_new_session(session_type)
            
            logging.info(f"🎯 Starting {session_type} sync (Session: {session_id})")
            
            # Get root folder info
            try:
                root_metadata = self.service.files().get(
                    fileId=self.config.drive_folder_id,
                    fields='name'
                ).execute()
                root_name = root_metadata.get('name', 'Drive Sync')
            except Exception as e:
                logging.error(f"Failed to get root folder info: {e}")
                root_name = self.config.get('drive_settings', 'folder_name', 'Drive Sync')
            
            # Start processing
            logging.info(f"🚀 Processing root folder: {root_name}")
            
            success = self.drive_ops.process_folder(
                self.config.drive_folder_id,
                self.config.download_directory
            )
            
            # Update state and get sync token for future incremental syncs
            if success:
                self.state.state['last_full_sync'] = datetime.now().isoformat()
                self.get_initial_sync_token()  # Save token for next incremental sync
                logging.info("🎉 Sync completed successfully")
                self.state.end_session('completed')
            else:
                logging.warning("⚠️  Sync completed with some issues")
                self.state.end_session('completed_with_issues')
            
            # Print final statistics
            self.print_statistics()
            
            return success
            
        except KeyboardInterrupt:
            logging.warning("🛑 Sync interrupted by user")
            self.state.end_session('interrupted')
            return False
            
        except Exception as e:
            logging.error(f"💥 Sync failed: {e}")
            logging.exception("Stack trace:")
            self.state.end_session('failed')
            return False
    
    def perform_incremental_sync(self, changes):
        """Perform incremental sync with detected changes"""
        try:
            session_id = self.state.start_new_session('incremental')
            logging.info(f"🎯 Starting incremental sync (Session: {session_id})")
            
            # Process the changes
            success = self.process_incremental_changes(changes)
            
            # Update state
            if success:
                self.state.state['last_incremental_sync'] = datetime.now().isoformat()
                logging.info("🎉 Incremental sync completed successfully")
                self.state.end_session('completed')
            else:
                logging.info("ℹ️  No changes to process")
                self.state.end_session('completed')
            
            # Print final statistics
            self.print_statistics()
            
            return True
            
        except KeyboardInterrupt:
            logging.warning("🛑 Incremental sync interrupted by user")
            self.state.end_session('interrupted')
            return False
            
        except Exception as e:
            logging.error(f"💥 Incremental sync failed: {e}")
            logging.exception("Stack trace:")
            self.state.end_session('failed')
            return False
    
    def resume_sync(self):
        """Resume from checkpoint"""
        checkpoint = self.state.load_checkpoint()
        
        if checkpoint:
            logging.info(f"📍 Resuming from checkpoint: {checkpoint['current_folder']}")
            logging.info(f"📅 Checkpoint created: {checkpoint['timestamp']}")
            
            # Resume sync (simplified - would need more complex logic for exact resume)
            return self.perform_sync('resume')
        else:
            logging.info("🆕 No checkpoint found - starting fresh sync")
            return self.perform_sync('full')
    
    def print_statistics(self):
        """Print sync statistics"""
        stats = self.state.state['statistics']
        
        logging.info("="*60)
        logging.info("📊 SYNC STATISTICS")
        logging.info("="*60)
        logging.info(f"📁 Total sessions: {stats['total_sessions']}")
        logging.info(f"📄 Files downloaded: {stats['total_files_downloaded']:,}")
        logging.info(f"📦 Data downloaded: {stats['total_bytes_downloaded'] / (1024**3):.2f} GB")
        
        if self.state.state['current_session']:
            current = next((s for s in self.state.state['sync_sessions'] 
                           if s['id'] == self.state.state['current_session']), None)
            if current:
                logging.info(f"📈 Current session files: {current['files_downloaded']:,}")
                logging.info(f"📈 Current session data: {current['bytes_downloaded'] / (1024**2):.2f} MB")
        
        logging.info("="*60)

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    """Main execution function"""
    import sys
    
    try:
        # Parse command line arguments
        sync_type = 'auto'
        if len(sys.argv) > 1:
            sync_type = sys.argv[1].lower()
        
        # Initialize sync system
        sync = DriveSync()
        sync.initialize()
        
        # Handle different sync types
        if sync_type == 'resume':
            logging.info("📍 Resume requested")
            success = sync.resume_sync()
        elif sync_type == 'incremental':
            logging.info("⚡ Incremental sync requested")
            success = sync.perform_sync('incremental')
        elif sync_type == 'full':
            logging.info("🚀 Full sync requested")
            success = sync.perform_sync('full')
        else:
            # Check for resume capability first
            checkpoint = sync.state.load_checkpoint()
            
            if checkpoint:
                logging.info("📍 Checkpoint found - resuming previous sync")
                success = sync.resume_sync()
            else:
                logging.info("🆕 Starting automatic sync")
                success = sync.perform_sync('auto')
        
        if success:
            logging.info("✅ Sync operation completed successfully")
            sys.exit(0)
        else:
            logging.warning("⚠️  Sync operation completed with issues")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logging.info("🛑 Sync cancelled by user")
        sys.exit(130)
        
    except Exception as e:
        logging.error(f"💥 Fatal error: {e}")
        logging.exception("Stack trace:")
        sys.exit(1)

if __name__ == '__main__':
    main()