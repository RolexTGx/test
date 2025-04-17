Here’s a more polished and well-structured version of your README file:

---

# **MN-Bot**

**MN-Bot** is an advanced Telegram bot designed to automatically post torrent files from [1TamilBlasters](https://www.1tamilblasters.gold) to a specified Telegram channel. The bot performs periodic checks to ensure the latest torrents are fetched and posted seamlessly.

---

## **Features**

- 🚀 **Automatic Torrent Fetching**: Scrapes torrent files from 1TamilBlasters and posts them to a Telegram channel.
- 🛠️ **Flask Health Check**: Includes a lightweight Flask server to monitor the bot's health.
- ✂️ **Safe Message Splitting**: Splits long messages into manageable chunks to avoid truncation issues.
- 🔄 **Threaded Flask Server**: Ensures the Flask server runs in a separate thread, preventing any interference with the bot’s core functionality.
- ☁️ **Cloud Deployment Ready**: Compatible with platforms like [Koyeb](https://www.koyeb.com) and [Render](https://render.com).

---

## **Requirements**

### **Python Libraries**
Install the required libraries by running the following command:
```bash
pip install -r requirements.txt
```

---

## **Configuration**

Ensure the following configurations are set in the `config.py` file:

- **BOT**: The bot's token.
- **API**: The Telegram API ID and API Hash.
- **OWNER**: The Telegram user ID of the bot's owner.
- **CHANNEL**: The Telegram channel ID where torrents will be posted.

---

## **How to Run**

### **Local Environment**

1. Clone the repository:
    ```bash
    git clone https://github.com/RolexTGx/test.git
    cd test
    ```

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Run the bot:
    ```bash
    python bot.py
    ```

### **Deployment**

#### **Koyeb**

1. Log in to [Koyeb](https://www.koyeb.com).
2. Create a new service and link it to your GitHub repository.
3. Set the `PYTHON_ENV` to `production` and add all required environment variables (e.g., `BOT_TOKEN`, `API_ID`, `API_HASH`, etc.) in the service configuration.
4. Deploy the service.

#### **Render**

1. Log in to [Render](https://render.com).
2. Create a new web service and connect it to your GitHub repository.
3. Add the necessary environment variables like `BOT_TOKEN`, `API_ID`, `API_HASH`, etc.
4. Set the Start Command to:
    ```bash
    python bot.py
    ```
5. Deploy the service.

---

## **Notes**

- The bot requires **valid Telegram API credentials** to function.
- Ensure the target Telegram channel allows the bot to post messages.
- The bot performs periodic checks every **15 minutes** to fetch and post new torrents.

---

## **License**

This project is licensed under the **MIT License**. Feel free to use, modify, and distribute it as per the terms of the license.

---

This version improves readability and structure while maintaining all the original details. Let me know if you need further adjustments!
