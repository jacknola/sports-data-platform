import gspread
client = gspread.service_account(filename="service_account.json")
for sheet in client.openall():
    print(f"Name: '{sheet.title}', ID: {sheet.id}")
