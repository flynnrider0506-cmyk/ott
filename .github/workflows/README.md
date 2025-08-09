# OTT Weekly Releases Bot (Telegram)

This repository sends a curated weekly list of OTT releases in India to a Telegram chat.

## Files
- `main.py` - script that fetches releases, enriches with OMDb, ranks and sends to Telegram.
- `.github/workflows/weekly.yml` - GitHub Actions workflow to run the script weekly.
- `requirements.txt` - dependencies.

## Setup
1. Create a GitHub repository and upload these files.
2. Add repository secrets (Settings → Secrets and variables → Actions):
   - `STREAMING_API_KEY` (RapidAPI Streaming Availability key)
   - `OMDB_API_KEY` (OMDb API key)
   - `TELEGRAM_BOT_TOKEN` (Telegram bot token from @BotFather)
   - `TELEGRAM_CHAT_ID` (Your Telegram user/chat id)
3. Optionally test by going to the Actions tab in GitHub and running the workflow manually (Run workflow).
4. You will receive a Telegram message every Friday with the week's OTT releases.

## Notes
- This script uses free tiers of APIs. Rate limits may apply.
- If the streaming API does not include release dates for some items, they will be skipped.
- The message limits of Telegram apply; very long lists may be truncated.
