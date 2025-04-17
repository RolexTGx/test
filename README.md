# MN-Bot

MN-Bot is an advanced Telegram bot designed to automatically post torrent files from [1TamilBlasters](https://www.1tamilblasters.gold) to a specified Telegram channel. The bot runs periodic checks every 15 minutes to fetch and post new torrents.

## Features
- **Automatic Torrent Fetching**: Scrapes torrent files from 1TamilBlasters and posts them to a Telegram channel.
- **Flask Health Check**: A lightweight Flask server to indicate that the bot is running.
- **Safe Message Splitting**: Handles long messages gracefully by splitting them into chunks.
- **Threaded Flask Server**: Runs Flask in a separate thread to ensure it doesn't block the bot's main functionality.
- **Cloud Deployment Support**: Works with deployment platforms like [Koyeb](https://www.koyeb.com) and [Render](https://render.com).

---

## Requirements

### Python Libraries
Install the required libraries using:
```bash
pip install -r requirements.txt
```
Configurations
Make sure to configure the following in the config.py file:

BOT: Contains the bot's token.
API: Contains API ID and API Hash for Telegram.
OWNER: The Telegram user ID of the bot's owner.
CHANNEL: The Telegram channel ID to which torrents will be posted.

How to Run
Local Environment
Clone the repository:
bash
git clone https://github.com/RolexTGx/test.git
cd test
Install dependencies:
bash
pip install -r requirements.txt
Run the bot:
bash
python bot.py
Deployment
Koyeb
Log in to Koyeb.
Create a new service and link it to your GitHub repository.
Set the PYTHON_ENV to production and ensure all required environment variables (e.g., BOT_TOKEN, API_ID, API_HASH, etc.) are added in the service configuration.
Deploy the service.
Render
Log in to Render.
Create a new web service and connect it to your GitHub repository.
Add environment variables like BOT_TOKEN, API_ID, API_HASH, etc.
Set the Start Command to:
bash
python bot.py
Deploy the service.
Notes
The bot requires valid Telegram API credentials to function.
Make sure the target Telegram channel allows the bot to post messages.
The bot uses periodic checks every 15 minutes to fetch and post new torrents.
License
This project is licensed under the MIT License. Feel free to use, modify, and distribute it as per the terms of the license.

