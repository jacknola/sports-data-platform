import traceback
from master_dashboard import get_predictions, SHEET_NAME
import gspread
from gspread.utils import ValueInputOption

def upload_to_sheets(data_dict: dict):
    client = gspread.service_account(filename="service_account.json")
    spreadsheet = client.open(SHEET_NAME)
    
    tab_map = {"nba": "NBA_Spreads", "ncaab": "NCAAB_Spreads", "props": "Player_Props"}
    
    for key, tab_name in tab_map.items():
        sheet = spreadsheet.worksheet(tab_name)
        sheet.clear()
        
        sheet.update(
            range_name='A1', 
            values=data_dict[key], 
            value_input_option=ValueInputOption.user_entered 
        )
        print(f"Updated {tab_name}")

try:
    upload_to_sheets(get_predictions())
except BaseException as e:
    traceback.print_exc()
