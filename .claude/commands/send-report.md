Send the full betting report to Telegram immediately (on-demand, outside the scheduled cron).

Steps:
1. Run the NCAAB analysis: `python backend/run_ncaab_analysis.py`
2. Capture the output
3. Send it to Telegram via the bot

Check that TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in .env first.

If the Telegram service module exists at `backend/app/services/telegram_service.py`, use it.
If not, send directly using the requests library:

```python
import requests, os
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send(text):
    # Split into 4096-char chunks (Telegram limit)
    for i in range(0, len(text), 4096):
        requests.post(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text[i:i+4096], 'parse_mode': 'HTML'}
        )
```

If TELEGRAM_CHAT_ID is empty, remind the user to:
1. Message @userinfobot on Telegram
2. Copy the numeric ID it returns
3. Add it to .env as TELEGRAM_CHAT_ID=<number>

After sending, confirm success with the message timestamp.
