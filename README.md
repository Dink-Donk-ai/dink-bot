# Dink-Bot: A Discord Bitcoin Trading Simulator

Dink-Bot is a Discord bot that allows users to simulate Bitcoin trading within a Discord server. Users start with a virtual cash balance and can buy and sell simulated Bitcoin based on real-time (slightly delayed) price data fetched from the CoinGecko API.

## Features

### User Commands:

*   `!help`: Displays a list of available commands.
*   `!balance`: Shows your current virtual cash (USD) and Bitcoin (BTC) balances, your total portfolio net worth, and your overall profit/loss since starting.
*   `!buy <amount_usd>`: Buy a specified amount of Bitcoin using your virtual USD. Use `!buy all` to spend all your available cash.
*   `!sell <amount_btc>`: Sell a specified amount of your virtual Bitcoin. Use `!sell all` to sell all your BTC.
*   `!stats`: Displays current Bitcoin market statistics (price, 30-day SMA, 90-day range) and a leaderboard of the top users by net worth.
*   `!history`: Shows your last 10 buy/sell transactions with amounts, prices, and timestamps.

### Automated Features:

*   **Daily Digest**: Posts a daily market summary at 8:00 AM UTC, including BTC price, 24h/7d change, 30-day SMA, 30-day volatility, and the 90-day price range.
*   **HODL Buy Alert**: If BTC price drops more than 30% (configurable) from its 90-day high, the bot will post an alert (once per day) suggesting it might be a good time to buy the dip.
*   **Price Updates**: Bitcoin price data is fetched and updated every 5 minutes.

### Admin Commands (Require Admin User ID):

*   `!admin resetuser <user_mention_or_id>`: Resets a user's account to the initial cash balance ($1,000.00) and 0 BTC.
*   `!admin givecash <user_mention_or_id> <usd_amount>`: Gives (or takes, if negative) a specified amount of USD to/from a user.
*   `!admin givebtc <user_mention_or_id> <btc_amount>`: Gives (or takes, if negative) a specified amount of BTC to/from a user.

## Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd dink-bot-1 # Or your repository name
    ```

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Variables:**
    Create a `.env` file in the root directory of the project or set these environment variables in your deployment environment (e.g., Railway):

    ```env
    DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN"
    DISCORD_CHANNEL_ID="YOUR_TARGET_DISCORD_CHANNEL_ID"
    DATABASE_URL="YOUR_POSTGRESQL_DATABASE_URL" # e.g., postgresql://user:pass@host:port/dbname
    DISCORD_WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL_FOR_NOTIFICATIONS" # Currently unused, but good to have
    DISCORD_ADMIN_USER_IDS="YOUR_DISCORD_USER_ID,ANOTHER_ADMIN_USER_ID" # Comma-separated Discord User IDs
    ```

    *   `DISCORD_BOT_TOKEN`: Your Discord application's bot token.
    *   `DISCORD_CHANNEL_ID`: The ID of the specific Discord channel where the bot should operate.
    *   `DATABASE_URL`: Connection string for your PostgreSQL database.
    *   `DISCORD_WEBHOOK_URL`: A Discord webhook URL (currently planned for extended notifications, but present in config).
    *   `DISCORD_ADMIN_USER_IDS`: A comma-separated list of Discord user IDs who will have access to admin commands.

## Running the Bot

Once the environment variables are set and dependencies are installed:

```bash
python live_bot.py
```

## Database Schema

The bot uses a PostgreSQL database with the following main tables:

*   `users`: Stores user information (`uid`, `name`, `cash_c`, `btc_c`).
*   `transactions`: Logs all buy/sell transactions (`transaction_id`, `uid`, `name`, `transaction_type`, `btc_amount_sats`, `usd_amount_cents`, `price_at_transaction_cents`, `timestamp`).
*   `prices`: Intended for storing historical price data (currently fetched on-demand from CoinGecko but table exists for future use).

The database tables are created automatically if they don't exist when the bot starts.

## Contributing

Contributions, issues, and feature requests are welcome. Please feel free to fork the repository and submit a pull request.

---
*This bot is for educational and entertainment purposes only. Trading is simulated and does not involve real currency.* 