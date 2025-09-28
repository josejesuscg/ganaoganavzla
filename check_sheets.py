# check_sheets.py
import os
from dotenv import load_dotenv
load_dotenv()

import gspread
from google.oauth2.service_account import Credentials

GOOGLE_CREDS = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credenciales.json")
SHEET_ID = os.getenv("SHEET_ID")

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(GOOGLE_CREDS, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
print("Pestañas en la hoja:", [ws.title for ws in sh.worksheets()])
ws = sh.worksheet(os.getenv("SHEET_TAB_TICKETS","Tickets"))
print("Encabezado fila 1:", ws.row_values(1))
