import os
import requests
import datetime
from datetime import datetime as dt

# Config via GitHub Secrets
STREAMING_API_KEY = os.getenv("STREAMING_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Helper: safe request
def safe_get(url, headers=None, params=None, timeout=15):
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("HTTP error:", e)
        return {}

# Compute the week range (last Friday .. this Friday)
def week_range():
    today = datetime.date.today()
    # Find most recent Friday (could be today)
    offset = (today.weekday() - 4) % 7
    last_friday = today - datetime.timedelta(days=offset)
    # We want the 7-day window ending on last_friday
    start = last_friday - datetime.timedelta(days=6)
    end = last_friday
    return start, end

# Fetch releases from Streaming Availability API (RapidAPI)
def fetch_streaming_releases(page=1):
    url = "https://streaming-availability.p.rapidapi.com/v2/search/basic"
    headers = {
        "x-rapidapi-key": STREAMING_API_KEY,
        "x-rapidapi-host": "streaming-availability.p.rapidapi.com"
    }
    params = {
        "country": "in",
        "services": "netflix,prime,hotstar,zee5,jio,sonyliv,mxplayer,voot",
        "type": "all",
        "order_by": "date",
        "page": page,
        "output_language": "en"
    }
    return safe_get(url, headers=headers, params=params)

# Get OMDb info (by title fallback to searching)
def omdb_info_by_title(title):
    if not OMDB_API_KEY:
        return {"imdbRating":"N/A","Plot":"No plot available"}
    try:
        url = "http://www.omdbapi.com/"
        params = {"apikey": OMDB_API_KEY, "t": title}
        r = requests.get(url, params=params, timeout=10).json()
        return {"imdbRating": r.get("imdbRating","N/A"), "Plot": r.get("Plot","No plot available")}
    except:
        return {"imdbRating":"N/A","Plot":"No plot available"}

# Build the weekly list
def build_weekly_list():
    start, end = week_range()
    # Fetch first 2 pages to be safe
    results = []
    for p in (1,2):
        data = fetch_streaming_releases(page=p)
        for item in data.get("result", []):
            # Each item may contain a release date field in different keys
            rd = item.get("releaseDate") or item.get("firstAirDate") or item.get("release_date") or item.get("originalRelease")
            # Normalize date if present
            date_ok = False
            if rd:
                try:
                    rd_date = dt.strptime(rd[:10], "%Y-%m-%d").date()
                    if start <= rd_date <= end:
                        date_ok = True
                        release_date = rd_date.strftime("%d %b %Y")
                except:
                    date_ok = False
            else:
                date_ok = False

            # Sometimes streaming API doesn't include release date; skip if not in range
            if not date_ok:
                continue

            title = item.get("title") or item.get("name") or item.get("originalTitle") or "Unknown"
            # get platforms - streamingInfo keys like 'in' -> services
            platforms = []
            sinfo = item.get("streamingInfo") or {}
            # streamingInfo may have country keys; for safety, gather service names if present
            for country_key in sinfo:
                for service_key, svcdata in sinfo.get(country_key, {}).items():
                    platforms.append(service_key)
            platforms = list(dict.fromkeys(platforms))  # unique

            # get OMDb info
            omdb = omdb_info_by_title(title)
            imdb_rating = omdb.get("imdbRating","N/A")
            plot = omdb.get("Plot","No plot available")

            results.append({
                "title": title,
                "release_date": release_date,
                "platforms": ", ".join(platforms) if platforms else "Unknown",
                "imdb": imdb_rating,
                "plot": plot
            })
    # Sort by IMDb (numeric where possible), then by title
    def rating_key(x):
        try:
            return float(x["imdb"])
        except:
            return 0.0
    results.sort(key=lambda x: (rating_key(x), x["title"]), reverse=True)
    return results, start, end

# Format message (detailed)
def format_message(items, start, end):
    if not items:
        return f"🎬 No OTT releases found between {start} and {end}."
    header = f"🎬 *OTT Releases in India*  ({start.strftime('%d %b')} - {end.strftime('%d %b')})\n"
    header += "─────────────────────────────\n\n"
    lines = [header]
    for it in items:
        lines.append(f"📽️ *{it['title']}*  (IMDb: {it['imdb']})\n")
        lines.append(f"Release Date: {it['release_date']}  |  Platform: {it['platforms']}\n")
        # truncate plot to avoid very long messages
        plot = it['plot'] or ""
        if len(plot) > 350:
            plot = plot[:347] + "..."
        lines.append(f"📝 {plot}\n\n")
    return "".join(lines)

# Send message to Telegram (supports Markdown)
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing Telegram credentials.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode":"Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        print("Telegram send status:", r.status_code, r.text)
    except Exception as e:
        print("Failed to send telegram:", e)

def main():
    items, start, end = build_weekly_list()
    message = format_message(items, start, end)
    send_telegram(message)

if __name__ == "__main__":
    main()
