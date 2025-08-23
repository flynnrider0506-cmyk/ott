#!/usr/bin/env python3
"""
OTT Weekly Releases Bot - Notification Script
Sends a curated weekly list of newly released OTT movies and shows in India to Telegram.
"""

import os
import requests
import datetime
from datetime import datetime as dt

# --- Configuration ---
STREAMING_API_KEY = os.getenv("STREAMING_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Helper Functions ---

def safe_get(url, headers=None, params=None, timeout=20):
    """Safely perform a GET request and return JSON, handling errors."""
    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {url}: {e}")
        return {}

def get_week_range():
    """
    Calculate the date range for the past week, from the Friday of the week before last
    to the most recent Friday.
    """
    today = datetime.date.today()
    # Find the most recent Friday (could be today)
    last_friday_offset = (today.weekday() - 4) % 7
    last_friday = today - datetime.timedelta(days=last_friday_offset)
    # The start of the 7-day window is 6 days before the last Friday
    start_date = last_friday - datetime.timedelta(days=6)
    return start_date, last_friday

# --- Core Logic ---

def fetch_new_releases(start_date, end_date):
    """Fetch new releases from the Streaming Availability API for a given date range."""
    print(f"Fetching releases from {start_date} to {end_date}...")
    results = []
    # Fetch a few pages to ensure we get all releases for the week
    for page in range(1, 3):
        url = "https://streaming-availability.p.rapidapi.com/v2/search/basic"
        headers = {
            "x-rapidapi-key": STREAMING_API_KEY,
            "x-rapidapi-host": "streaming-availability.p.rapidapi.com"
        }
        params = {
            "country": "in",
            "services": "netflix,prime,hotstar,zee5,jio,sonyliv",
            "type": "all",
            "order_by": "date",
            "page": page,
            "output_language": "en"
        }
        data = safe_get(url, headers=headers, params=params)
        if not data.get("result"):
            break
        
        for item in data["result"]:
            release_date_str = item.get("releaseDate") or item.get("firstAirDate")
            if not release_date_str:
                continue

            try:
                release_date = dt.strptime(release_date_str, "%Y-%m-%d").date()
                if start_date <= release_date <= end_date:
                    results.append(item)
            except ValueError:
                continue # Ignore items with invalid date formats

    # Remove duplicates based on title and year
    unique_releases = []
    seen_titles = set()
    for item in results:
        title = item.get("title") or item.get("name", "Unknown")
        year = item.get("year")
        identifier = (title, year)
        if identifier not in seen_titles:
            unique_releases.append(item)
            seen_titles.add(identifier)

    print(f"Found {len(unique_releases)} unique new releases.")
    return unique_releases

def enrich_with_omdb(releases):
    """Enrich release data with details from OMDb."""
    if not OMDB_API_KEY:
        print("OMDb API key not set. Skipping enrichment.")
        return releases

    print("Enriching releases with OMDb data...")
    enriched_list = []
    for item in releases:
        title = item.get("title") or item.get("name", "Unknown")
        omdb_url = "http://www.omdbapi.com/"
        params = {"apikey": OMDB_API_KEY, "t": title}
        omdb_data = safe_get(omdb_url, params=params)

        item["imdbRating"] = omdb_data.get("imdbRating", "N/A")
        item["plot"] = omdb_data.get("Plot", "No plot available.")
        enriched_list.append(item)
    return enriched_list

def rank_releases(releases):
    """Sort releases by IMDb rating in descending order."""
    def rating_key(item):
        try:
            return float(item.get("imdbRating", 0))
        except (ValueError, TypeError):
            return 0.0
    
    return sorted(releases, key=rating_key, reverse=True)

# --- Formatting and Sending ---

def format_telegram_message(items, start_date, end_date):
    """Format the list of releases into a Markdown-formatted message for Telegram."""
    if not items:
        return f"🎬 *No new OTT releases found for {start_date.strftime('%d %b')} - {end_date.strftime('%d %b')}*"

    start_str = start_date.strftime('%d %b')
    end_str = end_date.strftime('%d %b')
    message_header = f"🎬 *OTT Releases in India ({start_str} - {end_str})*\n"
    message_header += "──────────────────────────\n\n"
    
    message_lines = [message_header]
    for item in items:
        title = item.get("title") or item.get("name", "Unknown")
        rating = item.get("imdbRating", "N/A")
        
        # Extract platform names
        platforms = []
        streaming_info = item.get("streamingInfo", {})
        for country_data in streaming_info.values():
            for service, service_data in country_data.items():
                 platforms.append(service.capitalize())
        platforms_str = ", ".join(sorted(list(set(platforms)))) or "N/A"

        release_date_str = item.get("releaseDate") or item.get("firstAirDate", "N/A")
        try:
            release_date_formatted = dt.strptime(release_date_str, "%Y-%m-%d").strftime("%d %b %Y")
        except ValueError:
            release_date_formatted = "N/A"

        plot = item.get("plot", "No plot available.")
        if len(plot) > 350:
            plot = plot[:347] + "..."

        message_lines.append(f"📽️ *{title}* (IMDb: {rating})\n")
        message_lines.append(f"🗓️ Release Date: {release_date_formatted}\n")
        message_lines.append(f"📺 Platform(s): {platforms_str}\n")
        message_lines.append(f"📝 {plot}\n\n")

    return "".join(message_lines)

def send_telegram_message(text):
    """Sends the formatted message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials (BOT_TOKEN, CHAT_ID) are not set. Skipping message send.")
        return

    print("Sending message to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=payload, timeout=20)
        response.raise_for_status()
        print("Message sent successfully to Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message to Telegram: {e}")
        print(f"Response: {e.response.text if e.response else 'No response'}")

# --- Main Execution ---

def main():
    """Main function to run the bot."""
    print("🚀 Starting weekly OTT release bot...")
    
    # Ensure all required environment variables are set
    if not all([STREAMING_API_KEY, OMDB_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("❌ Missing one or more required environment variables. Aborting.")
        return

    # 1. Get date range for the past week
    start_date, end_date = get_week_range()

    # 2. Fetch new releases
    new_releases = fetch_new_releases(start_date, end_date)
    if not new_releases:
        print("No new releases found for the period. Exiting.")
        # Still send a message to confirm it ran
        send_telegram_message(f"🎬 No new OTT releases found for {start_date.strftime('%d %b')} - {end_date.strftime('%d %b')}")
        return

    # 3. Enrich with OMDb data
    enriched_releases = enrich_with_omdb(new_releases)

    # 4. Rank releases by IMDb rating
    ranked_releases = rank_releases(enriched_releases)

    # 5. Format the message
    message = format_telegram_message(ranked_releases, start_date, end_date)

    # 6. Send to Telegram
    send_telegram_message(message)

    print("✅ Bot finished its run successfully.")

if __name__ == "__main__":
    main()
