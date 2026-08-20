# Telegram Like Bot

A Telegram bot for sending Facebook likes automatically.

## Features

- Send likes to Facebook UIDs
- Auto-like system starting at 7 AM daily
- Target like limits
- Admin control panel
- Group notifications

## Deployment on Render

### Steps:

1. Fork this repository
2. Create a new Web Service on Render
3. Connect your repository
4. Add environment variables:
   - `BOT_TOKEN`: Your Telegram bot token
   - `GROUP_ID`: Telegram group ID (negative number)
   - `ADMIN_IDS`: Comma-separated admin user IDs
   - `API_URL`: Facebook like API URL
   - `MEDIA_URL`: Video/Image URL for notifications

5. Deploy!

## Local Development

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
