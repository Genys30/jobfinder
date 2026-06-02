"""
upload_to_drive.py
Uploads today's CSV files to Google Drive (jobfinder-data folder).
Runs as part of GitHub Actions after fetch_jobs.py and fetch_gotfriends.py.
"""

import os
import json
import glob
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = os.environ['GDRIVE_FOLDER_ID']
TODAY = datetime.utcnow().strftime('%Y-%m-%d')


def get_drive_service():
    """Authenticate using service account credentials from env variable."""
    service_account_info = json.loads(os.environ['GDRIVE_SERVICE_ACCOUNT'])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=credentials)


def get_existing_files(service, folder_id):
    """Get dict of filename -> file_id for files already in the Drive folder."""
    existing = {}
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name)"
    ).execute()
    for f in results.get('files', []):
        existing[f['name']] = f['id']
    return existing


def upload_csv(service, filepath, folder_id, existing_files):
    """Upload a CSV file; update if it already exists, create if not."""
    filename = os.path.basename(filepath)
    media = MediaFileUpload(filepath, mimetype='text/csv', resumable=False)

    if filename in existing_files:
        # Update existing file
        service.files().update(
            fileId=existing_files[filename],
            media_body=media
        ).execute()
        print(f"  Updated: {filename}")
    else:
        # Create new file
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"  Uploaded: {filename}")


def main():
    print(f"Uploading CSVs for {TODAY} to Google Drive...")
    service = get_drive_service()
    existing_files = get_existing_files(service, FOLDER_ID)

    # Find all CSV files for today
    csv_files = glob.glob(f'*_jobs_{TODAY}.csv')

    if not csv_files:
        print("No CSV files found for today.")
        return

    for filepath in sorted(csv_files):
        upload_csv(service, filepath, FOLDER_ID, existing_files)

    print(f"Done. {len(csv_files)} file(s) uploaded.")


if __name__ == '__main__':
    main()
