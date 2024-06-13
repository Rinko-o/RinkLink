# RinkLink

A non invasive Discord bot for linking Discord accounts with Roblox usernames and managing verification.

## Features

- **Linking**: Link your Discord account with your Roblox username.
- **Verification**: Verify your Roblox account ownership with username confirmation.
- **Role Management**: Automatically assign a "Verified Roblox Account" role upon verification.
- **Nickname Update**: Update Discord nicknames with Roblox usernames for linked accounts.

## Commands

- `!link <roblox_username>` - Link your Discord account with a Roblox username.
- `!unlink` - Unlink your Discord account from a linked Roblox account.
- `!checklink` - Check if your Discord account is linked to a Roblox account.

## Requirements

- Python 3.8+
- Libraries listed in `requirements.txt`
- Discord Bot Token (get it from [Discord Developer Portal](https://discord.com/developers/applications))

## Setup

1. Clone the repository:

   ```bash
   none lol
Install dependencies:

```pip install -r requirements.txt```

Create a .env file in the root directory and add your Discord Bot Token:

```DISCORD_BOT_TOKEN=your_discord_bot_token_here```


Run the bot:

```python bot.py```

### Configuration
Adjust rate limits and cooldowns in bot.py as needed.
Customize role names and permissions to match your Discord server setup.\


### Contributing
Contributions are welcome! Fork the repository and submit a pull request.

### License
This project is licensed under the MIT License - see the LICENSE file for details.

### Instructions:

Replace `{DISCORD_SERVER_ID}` with your actual Discord server ID to generate the Discord badge correctly. This template provides a structured overview of your Discord bot's functionality, setup instructions, configuration details, and guidelines for contributing. Adjust the content as necessary to fit your specific bot's features and requirements.