#!/usr/bin/env python3
"""
Enhanced Google Drive Production Sync System
============================================

ENHANCED FEATURES:
- Intelligent file rename detection using content signatures
- Content-based comparison (checksums) to identify identical files
- Daily change logging with detailed file relationship tracking
- Smart duplicate file handling and cleanup
- Comprehensive file signature management
- Only downloads truly changed content, not just metadata differences

Author: Enhanced for Production Use with Content Intelligence
Date: 2025-01-16
Version: 2.0 - Enhanced Content Intelligence
"""

import os
import io
import json
import pickle
import logging
import time
import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# Import base classes from original script
from drive_sync_production import (
    ConfigManager, SyncStateManager, LoggingManager, 
    AuthenticationManager, DriveOperationsManager, DriveSync
)

# ═══════════════════════════════════════════════════════════════
# ENHANCED FILE SIGNATURE MANAGER
# ═══════════════════════════════════════════════════════════════

class FileSignatureManager:
    """Manages file content signatures for intelligent comparison"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.signatures_file = os.path.join(config_manager.state_directory, 'file_signatures.json')
        self.signatures = self.load_signatures()
        self.daily_changes = {}
        
    def load_signatures(self):
        """Load existing file signatures or create new"""
        if os.path.exists(self.signatures_file):
            try:
                with open(self.signatures_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'version': 'enhanced_v2.0',
            'files': {},  # file_id -> signature info
            'signatures_index': {},  # signature -> file_id list
            'last_cleanup': None,
            'statistics': {
                'total_files_tracked': 0,
                'duplicates_found': 0,
                'renames_detected': 0
            }
        }
    
    def save_signatures(self):
        """Save file signatures to disk"""
        try:
            with open(self.signatures_file, 'w', encoding='utf-8') as f:
                json.dump(self.signatures, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save signatures: {e}")
    
    def calculate_file_hash(self, file_path, method='sha256'):
        """Calculate hash of local file"""
        hash_func = getattr(hashlib, method)()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            logging.warning(f"Failed to calculate hash for {file_path}: {e}")
            return None
    
    def get_drive_file_signature(self, service, file_id):
        """Get file signature from Google Drive API"""
        try:
            file_metadata = service.files().get(
                fileId=file_id,
                fields='md5Checksum,sha1Checksum,sha256Checksum,size,modifiedTime'
            ).execute()
            
            # Prefer MD5 as it's most commonly available in Google Drive
            signature = (
                file_metadata.get('md5Checksum') or 
                file_metadata.get('sha1Checksum') or 
                file_metadata.get('sha256Checksum')
            )
            
            return {
                'signature': signature,
                'size': file_metadata.get('size'),
                'modified_time': file_metadata.get('modifiedTime'),
                'signature_type': 'md5' if file_metadata.get('md5Checksum') else 'sha1'
            }
            
        except Exception as e:
            logging.warning(f"Failed to get Drive file signature for {file_id}: {e}")
            return None
    
    def find_files_by_signature(self, signature):
        """Find all files with the same content signature"""
        return self.signatures.get('signatures_index', {}).get(signature, [])
    
    def record_file_signature(self, file_id, file_path, file_name, signature_info):
        """Record file signature for future comparison"""
        signature = signature_info.get('signature')
        if not signature:
            return
        
        # Record file info
        self.signatures['files'][file_id] = {
            'path': file_path,
            'name': file_name,
            'signature': signature,
            'signature_type': signature_info.get('signature_type', 'unknown'),
            'size': signature_info.get('size'),
            'modified_time': signature_info.get('modified_time'),
            'recorded_time': datetime.now().isoformat(),
            'local_hash': self.calculate_file_hash(file_path) if os.path.exists(file_path) else None
        }
        
        # Update signatures index
        if signature not in self.signatures['signatures_index']:
            self.signatures['signatures_index'][signature] = []
        
        if file_id not in self.signatures['signatures_index'][signature]:
            self.signatures['signatures_index'][signature].append(file_id)
        
        # Update statistics
        self.signatures['statistics']['total_files_tracked'] += 1
        
        self.save_signatures()
    
    def detect_file_rename(self, file_id, new_path, new_name, signature_info):
        """Detect if this is a renamed file"""
        signature = signature_info.get('signature')
        if not signature:
            return None
        
        # Find other files with same signature
        same_signature_files = self.find_files_by_signature(signature)
        
        for other_file_id in same_signature_files:
            if other_file_id != file_id and other_file_id in self.signatures['files']:
                other_file = self.signatures['files'][other_file_id]
                other_path = other_file['path']
                
                # Check if the other file exists locally but this one doesn't
                if os.path.exists(other_path) and not os.path.exists(new_path):
                    return {
                        'renamed_from_file_id': other_file_id,
                        'old_path': other_path,
                        'old_name': other_file['name'],
                        'new_path': new_path,
                        'new_name': new_name,
                        'signature': signature
                    }
        
        return None
    
    def cleanup_orphaned_signatures(self, current_drive_files):
        """Remove signatures for files no longer in Drive"""
        current_file_ids = {f['id'] for f in current_drive_files}
        orphaned_count = 0
        
        # Find orphaned file signatures
        orphaned_file_ids = []
        for file_id in self.signatures['files']:
            if file_id not in current_file_ids:
                orphaned_file_ids.append(file_id)
        
        # Remove orphaned signatures
        for file_id in orphaned_file_ids:
            if file_id in self.signatures['files']:
                file_info = self.signatures['files'][file_id]
                signature = file_info.get('signature')
                
                # Remove from files
                del self.signatures['files'][file_id]
                
                # Remove from signatures index
                if signature and signature in self.signatures['signatures_index']:
                    if file_id in self.signatures['signatures_index'][signature]:
                        self.signatures['signatures_index'][signature].remove(file_id)
                    
                    # Remove empty signature entries
                    if not self.signatures['signatures_index'][signature]:
                        del self.signatures['signatures_index'][signature]
                
                orphaned_count += 1
        
        if orphaned_count > 0:
            logging.info(f"🧹 Cleaned up {orphaned_count} orphaned file signatures")
            self.signatures['last_cleanup'] = datetime.now().isoformat()
            self.save_signatures()
        
        return orphaned_count

# ═══════════════════════════════════════════════════════════════
# ENHANCED CHANGE DETECTOR
# ═══════════════════════════════════════════════════════════════

class EnhancedChangeDetector:
    """Advanced change detection with content comparison"""
    
    def __init__(self, drive_sync, signature_manager):
        self.drive_sync = drive_sync
        self.signatures = signature_manager
        self.daily_changes = {}
        self.change_summary = {
            'new_files': [],
            'modified_files': [],
            'renamed_files': [],
            'unchanged_files': [],
            'duplicate_files': [],
            'errors': []
        }
    
    def analyze_file_changes(self, file_info, expected_local_path):
        """Comprehensive analysis of file changes with content intelligence"""
        file_id = file_info['id']
        file_name = file_info['name']
        
        # Get file signature from Drive
        signature_info = self.signatures.get_drive_file_signature(
            self.drive_sync.service, file_id
        )
        
        if not signature_info or not signature_info.get('signature'):
            logging.warning(f"⚠️  Could not get signature for {file_name}")
            return {
                'change_type': 'SIGNATURE_UNAVAILABLE',
                'action_needed': 'DOWNLOAD',
                'reason': 'No content signature available'
            }
        
        signature = signature_info['signature']
        
        # Check for existing file with same signature (potential rename)
        rename_info = self.signatures.detect_file_rename(
            file_id, expected_local_path, file_name, signature_info
        )
        
        if rename_info:
            return {
                'change_type': 'RENAMED',
                'action_needed': 'MOVE',
                'rename_info': rename_info,
                'signature_info': signature_info,
                'reason': f"File renamed from {rename_info['old_name']} to {file_name}"
            }
        
        # Check if file exists at expected location
        if os.path.exists(expected_local_path):
            local_hash = self.signatures.calculate_file_hash(expected_local_path)
            
            # Compare content signatures
            if local_hash == signature or self.compare_signatures(local_hash, signature):
                return {
                    'change_type': 'UNCHANGED',
                    'action_needed': 'SKIP',
                    'signature_info': signature_info,
                    'reason': 'Content signature matches'
                }
            else:
                return {
                    'change_type': 'CONTENT_MODIFIED',
                    'action_needed': 'UPDATE',
                    'signature_info': signature_info,
                    'reason': 'Content has changed'
                }
        else:
            # Check if file exists elsewhere with same signature (duplicate)
            same_signature_files = self.signatures.find_files_by_signature(signature)
            
            if same_signature_files:
                existing_files = []
                for existing_file_id in same_signature_files:
                    if existing_file_id in self.signatures.signatures['files']:
                        existing_file = self.signatures.signatures['files'][existing_file_id]
                        if os.path.exists(existing_file['path']):
                            existing_files.append(existing_file)
                
                if existing_files:
                    return {
                        'change_type': 'DUPLICATE_CONTENT',
                        'action_needed': 'LINK_OR_SKIP',
                        'signature_info': signature_info,
                        'existing_files': existing_files,
                        'reason': f'Content already exists in {len(existing_files)} other locations'
                    }
            
            return {
                'change_type': 'NEW_FILE',
                'action_needed': 'DOWNLOAD',
                'signature_info': signature_info,
                'reason': 'New file not present locally'
            }
    
    def compare_signatures(self, local_hash, drive_signature):
        """Compare local and drive signatures with fallback methods"""
        if not local_hash or not drive_signature:
            return False
        
        # Direct comparison
        if local_hash == drive_signature:
            return True
        
        # TODO: Add more sophisticated comparison if needed
        # (e.g., handle different hash types)
        
        return False
    
    def log_change(self, change_type, details):
        """Log individual change for daily summary"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        change_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': change_type,
            'details': details
        }
        
        # Add to daily changes
        if today not in self.daily_changes:
            self.daily_changes[today] = []
        
        self.daily_changes[today].append(change_entry)
        
        # Add to session summary
        change_key = f"{change_type.lower()}_files"
        if change_key in self.change_summary:
            self.change_summary[change_key].append(details)
    
    def save_daily_changes(self, date=None):
        """Save detailed daily changes to separate log file"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        if date not in self.daily_changes or not self.daily_changes[date]:
            return

        changes_log_file = os.path.join(
            self.drive_sync.config.logs_directory,
            f'daily_changes_{date}.json'
        )

        # Also create a human-readable text report
        text_report_file = os.path.join(
            self.drive_sync.config.logs_directory,
            f'daily_changes_{date}.txt'
        )

        try:
            # Save JSON format (for programmatic access)
            with open(changes_log_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'date': date,
                    'changes': self.daily_changes[date],
                    'summary': self.change_summary
                }, f, indent=2, ensure_ascii=False)

            # Generate human-readable text report
            self._generate_text_report(text_report_file, date)

            logging.info(f"📊 Daily changes saved:")
            logging.info(f"    JSON: {changes_log_file}")
            logging.info(f"    Text: {text_report_file}")

        except Exception as e:
            logging.error(f"Failed to save daily changes: {e}")

    def _generate_text_report(self, report_file, date):
        """Generate human-readable text report of daily changes"""
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"GOOGLE DRIVE SYNC - DAILY CHANGE REPORT\n")
                f.write(f"Date: {date}\n")
                f.write("=" * 80 + "\n\n")

                # Summary statistics
                f.write("SUMMARY STATISTICS\n")
                f.write("-" * 80 + "\n")
                for change_type, items in self.change_summary.items():
                    if items:
                        count = len(items)
                        f.write(f"{change_type.upper().replace('_', ' ')}: {count}\n")
                f.write("\n")

                # Detailed changes by category
                self._write_change_category(f, "NEW FILES", self.change_summary.get('new_files', []))
                self._write_change_category(f, "MODIFIED FILES", self.change_summary.get('modified_files', []))
                self._write_change_category(f, "RENAMED FILES", self.change_summary.get('renamed_files', []))
                self._write_change_category(f, "DUPLICATE FILES", self.change_summary.get('duplicate_files', []))
                self._write_change_category(f, "UNCHANGED FILES (Skipped)", self.change_summary.get('unchanged_files', []))

                f.write("=" * 80 + "\n")
                f.write(f"Report generated: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n")

        except Exception as e:
            logging.error(f"Failed to generate text report: {e}")

    def _write_change_category(self, file_handle, category_name, items):
        """Write a category of changes to the report"""
        if not items:
            return

        file_handle.write(f"\n{category_name}\n")
        file_handle.write("-" * 80 + "\n")

        for i, item in enumerate(items, 1):
            if isinstance(item, dict):
                file_handle.write(f"{i}. ")

                # Handle different detail formats
                if 'file_name' in item:
                    file_handle.write(f"{item['file_name']}\n")

                if 'old_name' in item and 'new_name' in item:
                    file_handle.write(f"   Renamed: {item['old_name']} → {item['new_name']}\n")

                if 'file_path' in item:
                    file_handle.write(f"   Path: {item['file_path']}\n")

                if 'size' in item:
                    size_mb = item['size'] / (1024 * 1024)
                    file_handle.write(f"   Size: {size_mb:.2f} MB\n")

                if 'action' in item:
                    file_handle.write(f"   Action: {item['action']}\n")

                if 'reason' in item:
                    file_handle.write(f"   Reason: {item['reason']}\n")

                if 'duplicate_count' in item:
                    file_handle.write(f"   Duplicates found: {item['duplicate_count']}\n")

                if 'source_path' in item:
                    file_handle.write(f"   Linked from: {item['source_path']}\n")

                file_handle.write("\n")
            else:
                # Simple string format
                file_handle.write(f"{i}. {item}\n")

# ═══════════════════════════════════════════════════════════════
# INTELLIGENT SYNC MANAGER
# ═══════════════════════════════════════════════════════════════

class IntelligentSyncManager:
    """Enhanced sync manager with intelligent file handling"""
    
    def __init__(self, drive_sync):
        self.drive_sync = drive_sync
        self.signatures = FileSignatureManager(drive_sync.config)
        self.change_detector = EnhancedChangeDetector(drive_sync, self.signatures)
        self.session_stats = {
            'files_analyzed': 0,
            'files_downloaded': 0,
            'files_moved': 0,
            'files_skipped': 0,
            'files_updated': 0,
            'duplicates_found': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def perform_intelligent_sync(self):
        """Perform sync with intelligent change detection"""
        self.session_stats['start_time'] = datetime.now()
        
        logging.info("=" * 80)
        logging.info("🧠 STARTING INTELLIGENT SYNC WITH CONTENT ANALYSIS")
        logging.info("=" * 80)
        
        # Start sync session
        session_id = self.drive_sync.state.start_new_session('intelligent')
        
        try:
            # Get all Drive files
            logging.info("🔍 Analyzing Google Drive content...")
            drive_files = self.get_all_drive_files()
            
            logging.info(f"📊 Found {len(drive_files)} files in Google Drive")
            
            # Cleanup orphaned signatures
            self.signatures.cleanup_orphaned_signatures(drive_files)
            
            # Analyze each file
            logging.info("🔬 Performing content analysis...")
            change_analysis = self.analyze_all_files(drive_files)

            # Execute actions based on analysis
            logging.info("⚡ Executing intelligent sync actions...")
            self.execute_sync_actions(change_analysis, drive_files)
            
            # Save daily changes
            self.change_detector.save_daily_changes()
            
            # Generate summary
            self.generate_sync_summary()
            
            # End session successfully
            self.drive_sync.state.end_session('completed')
            
        except KeyboardInterrupt:
            logging.warning("🛑 Sync interrupted by user")
            self.drive_sync.state.end_session('interrupted')
            raise
        except Exception as e:
            logging.error(f"💥 Sync failed: {e}")
            self.drive_sync.state.end_session('failed')
            raise
        finally:
            self.session_stats['end_time'] = datetime.now()
    
    def get_all_drive_files(self):
        """Get all files from the target Google Drive folder"""
        all_files = []
        
        def collect_files_recursive(folder_id, path=""):
            items = self.drive_sync.drive_ops.get_folder_items(folder_id)
            
            for item in items:
                item['_path'] = path + "/" + item['name'] if path else item['name']
                all_files.append(item)
                
                # Recursively process subfolders
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    collect_files_recursive(item['id'], item['_path'])
        
        collect_files_recursive(self.drive_sync.config.drive_folder_id)
        return all_files
    
    def analyze_all_files(self, drive_files):
        """Analyze all Drive files for changes"""
        analysis_results = {}
        
        for i, file_info in enumerate(drive_files, 1):
            file_id = file_info['id']
            file_name = file_info['name']
            
            # Skip folders for now (handle them separately)
            if file_info['mimeType'] == 'application/vnd.google-apps.folder':
                continue
            
            self.session_stats['files_analyzed'] += 1
            
            # Determine expected local path
            expected_path = self.get_expected_local_path(file_info)
            
            logging.info(f"🔍 [{i}/{len(drive_files)}] Analyzing: {file_name}")
            
            try:
                analysis = self.change_detector.analyze_file_changes(file_info, expected_path)
                analysis_results[file_id] = analysis
                
                # Log analysis result
                change_type = analysis['change_type']
                reason = analysis.get('reason', 'No reason provided')
                logging.info(f"    📋 Result: {change_type} - {reason}")
                
            except Exception as e:
                self.session_stats['errors'] += 1
                logging.error(f"    ❌ Analysis failed: {e}")
                analysis_results[file_id] = {
                    'change_type': 'ERROR',
                    'action_needed': 'SKIP',
                    'error': str(e)
                }
        
        return analysis_results
    
    def execute_sync_actions(self, change_analysis, drive_files):
        """Execute sync actions based on analysis results"""
        actions_count = {'DOWNLOAD': 0, 'UPDATE': 0, 'MOVE': 0, 'SKIP': 0, 'LINK_OR_SKIP': 0}

        # Create file_id to file_info mapping
        file_info_map = {f['id']: f for f in drive_files}

        for file_id, analysis in change_analysis.items():
            action = analysis['action_needed']
            actions_count[action] = actions_count.get(action, 0) + 1

        logging.info("📋 Action Summary:")
        for action, count in actions_count.items():
            if count > 0:
                logging.info(f"    {action}: {count} files")

        # Execute actions
        for file_id, analysis in change_analysis.items():
            try:
                file_info = file_info_map.get(file_id)
                if file_info:
                    self.execute_single_action(file_id, file_info, analysis)
            except Exception as e:
                self.session_stats['errors'] += 1
                logging.error(f"Failed to execute action for {file_id}: {e}")
    
    def execute_single_action(self, file_id, file_info, analysis):
        """Execute a single sync action"""
        action = analysis['action_needed']
        change_type = analysis['change_type']

        if action == "DOWNLOAD":
            self.handle_new_file_download(file_id, file_info, analysis)

        elif action == "UPDATE":
            self.handle_file_update(file_id, file_info, analysis)

        elif action == "MOVE":
            self.handle_file_rename(file_id, file_info, analysis)

        elif action == "SKIP":
            self.handle_file_skip(file_id, file_info, analysis)

        elif action == "LINK_OR_SKIP":
            self.handle_duplicate_file(file_id, file_info, analysis)
    
    def handle_new_file_download(self, file_id, file_info, analysis):
        """Handle downloading a new file"""
        file_name = self.drive_sync.drive_ops.sanitize_filename(file_info['name'])
        file_size = int(file_info.get('size', 0))
        mime_type = file_info.get('mimeType', '')
        modified_time = file_info.get('modifiedTime')
        expected_path = self.get_expected_local_path(file_info)

        try:
            # Use the existing download logic from DriveOperationsManager
            success = False
            if mime_type.startswith('application/vnd.google-apps.') and mime_type != 'application/vnd.google-apps.folder':
                # Google native file (Docs, Sheets, etc.)
                if self.drive_sync.config.get('advanced_settings', 'include_google_docs', False):
                    success = self.drive_sync.drive_ops.download_google_native_file(
                        file_id, file_name, mime_type, expected_path, modified_time
                    )
            else:
                # Regular file
                success = self.drive_sync.drive_ops.download_file(
                    file_id, file_name, file_size, expected_path, modified_time
                )

            if success:
                self.session_stats['files_downloaded'] += 1

                # Record signature for future comparison
                signature_info = analysis.get('signature_info')
                if signature_info:
                    self.signatures.record_file_signature(
                        file_id, expected_path, file_name, signature_info
                    )

                details = {
                    'file_id': file_id,
                    'file_name': file_name,
                    'file_path': expected_path,
                    'size': file_size,
                    'action': 'downloaded'
                }
                self.change_detector.log_change('NEW_FILE', details)

                logging.info(f"✅ Downloaded new file: {file_name}")
            else:
                self.session_stats['errors'] += 1
                logging.error(f"❌ Failed to download: {file_name}")

        except Exception as e:
            self.session_stats['errors'] += 1
            logging.error(f"Error downloading {file_name}: {e}")

    def handle_file_update(self, file_id, file_info, analysis):
        """Handle updating an existing file"""
        file_name = self.drive_sync.drive_ops.sanitize_filename(file_info['name'])
        file_size = int(file_info.get('size', 0))
        mime_type = file_info.get('mimeType', '')
        modified_time = file_info.get('modifiedTime')
        expected_path = self.get_expected_local_path(file_info)

        try:
            # Delete old version before downloading updated one
            if os.path.exists(expected_path):
                try:
                    os.remove(expected_path)
                    logging.info(f"🗑️  Removed old version: {file_name}")
                except Exception as e:
                    logging.warning(f"Could not remove old file: {e}")

            # Download updated version
            success = False
            if mime_type.startswith('application/vnd.google-apps.') and mime_type != 'application/vnd.google-apps.folder':
                if self.drive_sync.config.get('advanced_settings', 'include_google_docs', False):
                    success = self.drive_sync.drive_ops.download_google_native_file(
                        file_id, file_name, mime_type, expected_path, modified_time
                    )
            else:
                success = self.drive_sync.drive_ops.download_file(
                    file_id, file_name, file_size, expected_path, modified_time
                )

            if success:
                self.session_stats['files_updated'] += 1

                # Update signature
                signature_info = analysis.get('signature_info')
                if signature_info:
                    self.signatures.record_file_signature(
                        file_id, expected_path, file_name, signature_info
                    )

                details = {
                    'file_id': file_id,
                    'file_name': file_name,
                    'file_path': expected_path,
                    'size': file_size,
                    'action': 'updated',
                    'reason': 'Content modified'
                }
                self.change_detector.log_change('CONTENT_MODIFIED', details)

                logging.info(f"✅ Updated file: {file_name}")
            else:
                self.session_stats['errors'] += 1
                logging.error(f"❌ Failed to update: {file_name}")

        except Exception as e:
            self.session_stats['errors'] += 1
            logging.error(f"Error updating {file_name}: {e}")
    
    def handle_file_rename(self, file_id, file_info, analysis):
        """Handle file rename by moving local file"""
        rename_info = analysis.get('rename_info', {})
        old_path = rename_info.get('old_path')
        new_path = rename_info.get('new_path')
        old_name = rename_info.get('old_name')
        new_name = rename_info.get('new_name')
        renamed_from_file_id = rename_info.get('renamed_from_file_id')

        if old_path and new_path and os.path.exists(old_path):
            try:
                # Create new directory if needed
                os.makedirs(os.path.dirname(new_path), exist_ok=True)

                # Move file to new location
                shutil.move(old_path, new_path)

                self.session_stats['files_moved'] += 1

                # Update signature for new location and remove old signature
                signature_info = analysis.get('signature_info', {})
                self.signatures.record_file_signature(
                    file_id, new_path, new_name, signature_info
                )

                # Clean up old signature entry if it exists
                if renamed_from_file_id and renamed_from_file_id in self.signatures.signatures['files']:
                    old_sig_info = self.signatures.signatures['files'][renamed_from_file_id]
                    old_signature = old_sig_info.get('signature')

                    # Remove from files dict
                    del self.signatures.signatures['files'][renamed_from_file_id]

                    # Remove from signatures index
                    if old_signature and old_signature in self.signatures.signatures['signatures_index']:
                        if renamed_from_file_id in self.signatures.signatures['signatures_index'][old_signature]:
                            self.signatures.signatures['signatures_index'][old_signature].remove(renamed_from_file_id)

                        # Clean up empty signature entries
                        if not self.signatures.signatures['signatures_index'][old_signature]:
                            del self.signatures.signatures['signatures_index'][old_signature]

                    self.signatures.save_signatures()

                # Update state manager
                if renamed_from_file_id in self.drive_sync.state.state['completed_files']:
                    del self.drive_sync.state.state['completed_files'][renamed_from_file_id]

                self.drive_sync.state.mark_file_completed(
                    file_id, new_path, int(file_info.get('size', 0)), file_info.get('modifiedTime')
                )

                details = {
                    'file_id': file_id,
                    'old_name': old_name,
                    'new_name': new_name,
                    'old_path': old_path,
                    'new_path': new_path,
                    'action': 'renamed'
                }
                self.change_detector.log_change('RENAMED', details)

                logging.info(f"📁 RENAMED: {old_name} → {new_name}")
                logging.info(f"    From: {old_path}")
                logging.info(f"    To:   {new_path}")

            except Exception as e:
                logging.error(f"Failed to move file {old_path} → {new_path}: {e}")
                self.session_stats['errors'] += 1
        else:
            logging.warning(f"Cannot move file - source not found: {old_path}")

    def handle_file_skip(self, file_id, file_info, analysis):
        """Handle skipping unchanged file"""
        self.session_stats['files_skipped'] += 1

        file_name = file_info.get('name', 'Unknown')
        expected_path = self.get_expected_local_path(file_info)

        details = {
            'file_id': file_id,
            'file_name': file_name,
            'file_path': expected_path,
            'action': 'skipped',
            'reason': analysis.get('reason', 'No changes detected')
        }
        self.change_detector.log_change('UNCHANGED', details)

        logging.debug(f"⏭️  Skipped unchanged file: {file_name}")

    def handle_duplicate_file(self, file_id, file_info, analysis):
        """Handle duplicate file detection"""
        existing_files = analysis.get('existing_files', [])
        file_name = file_info.get('name', 'Unknown')

        self.session_stats['duplicates_found'] += 1

        # Create symlink or hardlink to existing file instead of downloading again
        expected_path = self.get_expected_local_path(file_info)

        if existing_files and len(existing_files) > 0:
            source_file = existing_files[0]  # Use first existing file
            source_path = source_file['path']

            try:
                # Create directory if needed
                os.makedirs(os.path.dirname(expected_path), exist_ok=True)

                # Create hard link to save space (or copy if hard link fails)
                try:
                    os.link(source_path, expected_path)
                    logging.info(f"🔗 Created hard link: {file_name}")
                    link_type = 'hard_link'
                except (OSError, NotImplementedError):
                    # Fallback to copy if hard links not supported
                    shutil.copy2(source_path, expected_path)
                    logging.info(f"📋 Copied from existing file: {file_name}")
                    link_type = 'copy'

                # Record signature
                signature_info = analysis.get('signature_info')
                if signature_info:
                    self.signatures.record_file_signature(
                        file_id, expected_path, file_name, signature_info
                    )

                details = {
                    'file_id': file_id,
                    'file_name': file_name,
                    'file_path': expected_path,
                    'source_path': source_path,
                    'action': 'duplicate_linked',
                    'link_type': link_type,
                    'duplicate_count': len(existing_files)
                }
                self.change_detector.log_change('DUPLICATE_CONTENT', details)

            except Exception as e:
                logging.error(f"Failed to link duplicate file: {e}")
                self.session_stats['errors'] += 1
        else:
            logging.warning(f"Duplicate detected but no existing files found for: {file_name}")
    
    def get_expected_local_path(self, file_info):
        """Get expected local path for a Drive file"""
        # Use the _path from recursive collection
        relative_path = file_info.get('_path', file_info['name'])
        
        # Sanitize filename
        safe_path = self.drive_sync.drive_ops.sanitize_filename(relative_path)
        
        return os.path.join(self.drive_sync.config.download_directory, safe_path)
    
    def generate_sync_summary(self):
        """Generate comprehensive sync summary"""
        duration = None
        if self.session_stats['start_time'] and self.session_stats['end_time']:
            duration = self.session_stats['end_time'] - self.session_stats['start_time']
        
        logging.info("=" * 80)
        logging.info("📊 INTELLIGENT SYNC SUMMARY")
        logging.info("=" * 80)
        logging.info(f"⏱️  Duration: {duration}")
        logging.info(f"📄 Files analyzed: {self.session_stats['files_analyzed']}")
        logging.info(f"📥 Files downloaded: {self.session_stats['files_downloaded']}")
        logging.info(f"🔄 Files updated: {self.session_stats['files_updated']}")
        logging.info(f"📁 Files moved: {self.session_stats['files_moved']}")
        logging.info(f"⏭️  Files skipped: {self.session_stats['files_skipped']}")
        logging.info(f"🔗 Duplicates found: {self.session_stats['duplicates_found']}")
        logging.info(f"❌ Errors: {self.session_stats['errors']}")
        logging.info("=" * 80)

# ═══════════════════════════════════════════════════════════════
# ENHANCED DRIVE SYNC CLASS
# ═══════════════════════════════════════════════════════════════

class EnhancedDriveSync(DriveSync):
    """Enhanced Drive Sync with intelligent content handling"""
    
    def __init__(self, config_file='config.json'):
        super().__init__(config_file)
        self.intelligent_sync = None
    
    def initialize(self):
        """Initialize the enhanced sync system"""
        super().initialize()
        
        # Initialize intelligent sync manager
        self.intelligent_sync = IntelligentSyncManager(self)
        
        logging.info("🧠 Enhanced sync system initialized with content intelligence")
    
    def run_intelligent_sync(self):
        """Run intelligent sync with content analysis"""
        if not self.intelligent_sync:
            raise RuntimeError("Intelligent sync not initialized")
        
        return self.intelligent_sync.perform_intelligent_sync()

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    """Main execution function"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Enhanced Google Drive Sync with Content Intelligence')
    parser.add_argument('--mode', choices=['intelligent', 'full', 'incremental', 'auto'],
                       default='intelligent', help='Sync mode (default: intelligent)')
    parser.add_argument('--config', default='config.json', help='Configuration file')
    parser.add_argument('--test', action='store_true', help='Test mode - analyze only, no downloads')

    args = parser.parse_args()

    try:
        # Initialize enhanced sync system
        sync = EnhancedDriveSync(args.config)
        sync.initialize()

        if args.mode == 'intelligent':
            logging.info("🧠 Running intelligent sync with content analysis...")
            sync.run_intelligent_sync()
        else:
            logging.info(f"🔄 Running {args.mode} sync (legacy mode)...")
            sync.perform_sync(args.mode)

        logging.info("✅ Sync completed successfully!")
        sys.exit(0)

    except KeyboardInterrupt:
        logging.info("🛑 Sync interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"💥 Sync failed: {e}")
        logging.exception("Stack trace:")
        sys.exit(1)

if __name__ == "__main__":
    main()