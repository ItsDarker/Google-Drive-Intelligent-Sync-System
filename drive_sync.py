import os
import io
import json
import pickle
import logging
import time
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
CONFIG_FILE = 'config.json'
TOKEN_FILE = 'state/token.pickle'
LOG_FILE = 'logs/drive_sync.log'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# --- SETUP LOGGING ---
def setup_logging():
    """Sets up logging to file and console."""
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, mode='w'), # Overwrite log each time
            logging.StreamHandler()
        ]
    )

# --- AUTHENTICATION ---
def get_drive_service():
    """Authenticates with Google Drive and returns the service object."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.error(f"Failed to refresh token: {e}")
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logging.error(f"Failed to get new token: {e}")
                return None
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('drive', 'v3', credentials=creds)
        logging.info("Successfully authenticated with Google Drive.")
        return service
    except Exception as e:
        logging.error(f"Failed to build Drive service: {e}")
        return None

# --- FILE OPERATIONS ---

def get_export_details(mime_type):
    """Returns the export MIME type and file extension for Google-native files."""
    export_map = {
        'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
        'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
        'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
        'application/vnd.google-apps.drawing': ('image/png', '.png'),
        'application/vnd.google-apps.jam': ('application/pdf', '.pdf'),
    }
    return export_map.get(mime_type)

def download_file(service, file_item, local_path):
    """Downloads a single file, handling both regular and Google-native files."""
    file_id = file_item.get('id')
    file_name = file_item.get('name')
    mime_type = file_item.get('mimeType')
    
    is_google_native = 'google-apps' in mime_type
    
    request = None
    final_local_path = local_path

    if is_google_native:
        export_details = get_export_details(mime_type)
        if not export_details:
            logging.warning(f"Unsupported Google-native file type '{mime_type}' for file '{file_name}'. Skipping.")
            return False
        
        export_mime_type, extension = export_details
        final_local_path = os.path.splitext(local_path)[0] + extension
        logging.info(f"Exporting Google-native file '{file_name}' as '{os.path.basename(final_local_path)}'...")
        request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
    else:
        file_size = int(file_item.get('size', 0))
        if os.path.exists(local_path) and os.path.getsize(local_path) == file_size:
            logging.info(f"File '{local_path}' already exists and is up to date. Skipping.")
            return True
        logging.info(f"Downloading '{file_name}'...")
        request = service.files().get_media(fileId=file_id)

    retries = 5
    for i in range(retries):
        try:
            fh = io.FileIO(final_local_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request, chunksize=20*1024*1024)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logging.info(f"Download progress for '{file_name}': {int(status.progress() * 100)}%")
            
            logging.info(f"Successfully downloaded '{os.path.basename(final_local_path)}'.")
            return True
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                logging.warning(f"Download failed with server error {e.resp.status}. Retrying in {2**i} seconds...")
                time.sleep(2**i)
            else:
                logging.error(f"Download failed for '{file_name}' with HttpError: {e}")
                return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during download of '{file_name}': {e}")
            return False
    
    logging.error(f"Failed to download '{file_name}' after {retries} retries.")
    return False

def sync_folder(service, folder_id, local_path):
    """Recursively syncs a Google Drive folder to a local path."""
    if not os.path.exists(local_path):
        os.makedirs(local_path)
        logging.info(f"Created local directory: '{local_path}'")

    page_token = None
    list_retries = 5
    for i in range(list_retries):
        try:
            while True:
                response = service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, size)',
                    pageToken=page_token
                ).execute()

                for item in response.get('files', []):
                    item_name = item.get('name')
                    item_path = os.path.join(local_path, item_name)

                    if item.get('mimeType') == 'application/vnd.google-apps.folder':
                        sync_folder(service, item.get('id'), item_path)
                    else:
                        download_file(service, item, item_path)

                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    return  # Successfully finished listing this folder

        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                logging.warning(f"Server error {e.resp.status} when listing folder '{folder_id}'. Retrying in {2**i} seconds...")
                time.sleep(2**i)
            else:
                logging.error(f"Failed to list files in folder '{folder_id}' with non-retriable HttpError: {e}")
                return
        except Exception as e:
            logging.error(f"An unexpected error occurred when listing folder '{folder_id}': {e}")
            return
    
    logging.error(f"Failed to list folder '{folder_id}' after {list_retries} retries.")


# --- MAIN ---
def main():
    """Main function to run the sync process."""
    setup_logging()
    logging.info("--- Starting Google Drive Sync ---")

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        drive_folder_id = config.get('drive_settings', {}).get('folder_id')
        local_download_dir = config.get('local_settings', {}).get('download_directory', 'data')
    except FileNotFoundError:
        logging.error(f"Configuration file '{CONFIG_FILE}' not found.")
        return
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in '{CONFIG_FILE}'.")
        return

    if not drive_folder_id or drive_folder_id == 'YOUR_FOLDER_ID_HERE':
        logging.error("Please set your 'folder_id' in the 'config.json' file.")
        return

    service = get_drive_service()
    if service:
        logging.info(f"Starting sync from Google Drive folder ID: {drive_folder_id}")
        logging.info(f"Local download directory: {os.path.abspath(local_download_dir)}")
        sync_folder(service, drive_folder_id, local_download_dir)

    logging.info("--- Google Drive Sync Finished ---")

if __name__ == '__main__':
    main()