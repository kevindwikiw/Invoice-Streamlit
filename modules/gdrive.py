# modules/gdrive.py
import streamlit as st

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# GANTI DENGAN ID FOLDER GOOGLE DRIVE KAMU
# (Buka folder di browser > lihat URL > copy kode aneh di belakang slash terakhir)
PARENT_FOLDER_ID = "1a1A0EezwDaKp27X-MuGOmxMV6SC_5cHp"

def upload_and_share(file_obj, filename, client_email):
    """
    Returns: (bool success, str link/error_msg)
    """
    try:
        # Load credentials dari secrets.toml
        # Pastikan di .streamlit/secrets.toml sudah ada bagian [gcp_service_account]
        creds_dict = dict(st.secrets["gcp_service_account"])
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=creds)

        # 1. Upload File
        file_metadata = {
            'name': filename,
            'parents': [PARENT_FOLDER_ID]
        }
        
        # Penting: Reset pointer file ke awal sebelum upload
        file_obj.seek(0)
        
        media = MediaIoBaseUpload(file_obj, mimetype='application/pdf', resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        file_id = file.get('id')
        web_link = file.get('webViewLink')

        # 2. Share ke Email Klien (jika ada)
        status_msg = "Berhasil simpan ke Drive."
        if client_email and "@" in client_email:
            user_permission = {
                'type': 'user',
                'role': 'reader', # Klien cuma bisa baca/download
                'emailAddress': client_email
            }
            # Ini yang bikin Google ngirim email notifikasi otomatis
            service.permissions().create(
                fileId=file_id,
                body=user_permission,
                emailMessage=f"Halo, berikut Invoice {filename}. Terima kasih.",
                sendNotificationEmail=True 
            ).execute()
            status_msg = f"Terkirim ke email {client_email} & tersimpan di Drive."
            
        return True, web_link, status_msg

    except Exception as e:
        return False, None, str(e)