#!/usr/bin/env python3
"""
OTT Weekly Releases Bot - Notification Script
Sends curated weekly list of OTT releases in India to Telegram
"""

import os
import sys
import requests
from datetime import datetime, timedelta
import json

def get_env_variable(var_name):
    """Get environment variable or raise error if not found"""
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Environment variable {var_name} is required but not set")
    return value

def get_weekly_releases():
    """Fetch weekly OTT releases using Streaming Availability API"""
    try:
        api_key = get_env_variable('STREAMING_API_KEY')
        
        # Calculate date range for current week
        today = datetime.now()
        week_start = today - timedelta(days=7)
        week_end = today
        
        headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': 'streaming-availability.p.rapidapi.com'
        }
        
        # API endpoint for new releases in India
        url = "https://streaming-availability.p.rapidapi.com/changes"
        params = {
            'change_type': 'new',
            'item_type': 'show',
            'country': 'in',
            'since': int(week_start.timestamp()),
            'until': int(week_end.timestamp())
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        print(f"Error fetching releases: {e}")
        return None

def enrich_with_omdb(releases):
    """Enrich release data with OMDb API information"""
    try:
        omdb_key = get_env_variable('OMDB_API_KEY')
        enriched_releases = []
        
        for release in releases.get('shows', [])[:20]:  # Limit to 20 to avoid rate limits
            try:
                title = release.get('title', '')
                year = release.get('year', '')
                
                # Query OMDb API
                omdb_url = "http://www.omdbapi.com/"
                params = {
                    'apikey': omdb_key,
                    't': title,
                    'y': year if year else None
                }
                
                response = requests.get(omdb_url, params=params, timeout=10)
                omdb_data = response.json()
                
                if omdb_data.get('Response') == 'True':
                    release['imdb_rating'] = omdb_data.get('imdbRating', 'N/A')
                    release['plot'] = omdb_data.get('Plot', 'No plot available')
                    release['genre'] = omdb_data.get('Genre', 'Unknown')
                else:
                    release['imdb_rating'] = 'N/A'
                    release['plot'] = 'No plot available'
                    release['genre'] = 'Unknown'
                    
                enriched_releases.append(release)
                
            except Exception as e:
                print(f"Error enriching {title}: {e}")
                # Add release without enrichment
                release['imdb_rating'] = 'N/A'
                release['plot'] = 'No plot available'
                release['genre'] = 'Unknown'
                enriched_releases.append(release)
                
        return enriched_releases
        
    except Exception as e:
        print(f"Error in OMDb enrichment: {e}")
        return releases.get('shows', [])

def rank_releases(releases):
    """Rank releases by IMDb rating and popularity"""
    def get_rating_score(release):
        try:
            rating = release.get('imdb_rating', 'N/A')
            if rating and rating != 'N/A':
                return float(rating)
            return 0.0
        except (ValueError, TypeError):
            return 0.0
    
    # Sort by IMDb rating (descending)
    ranked = sorted(releases, key=get_rating_score, reverse=True)
    return ranked

def format_message(releases):
    """Format releases into Telegram message"""
    if not releases:
        return "🎬 **Weekly OTT Releases**\n\nNo new releases found this week."
    
    message = "🎬 **Weekly OTT Releases in India**\n"
    message += f"📅 Week of {datetime.now().strftime('%B %d, %Y')}\n\n"
    
    for i, release in enumerate(releases[:10], 1):  # Top 10 releases
        title = release.get('title', 'Unknown Title')
        year = release.get('year', '')
        rating = release.get('imdb_rating', 'N/A')
        genre = release.get('genre', 'Unknown')
        
        # Get streaming services
        services = []
        for service_info in release.get('streamingInfo', {}).values():
            if isinstance(service_info, list):
                for info in service_info:
                    service_name = info.get('service', '')
                    if service_name and service_name not in services:
                        services.append(service_name)
        
        services_text = ", ".join(services) if services else "Unknown Platform"
        
        message += f"**{i}. {title}**"
        if year:
            message += f" ({year})"
        message += f"\n📺 {services_text}"
        if rating != 'N/A':
            message += f"\n⭐ IMDb: {rating}"
        message += f"\n🎭 {genre}\n\n"
    
    message += "\n🤖 *Powered by OTT Weekly Bot*"
    return message

def send_telegram_message(message):
    """Send message to Telegram"""
    try:
        bot_token = get_env_variable('TELEGRAM_BOT_TOKEN')
        chat_id = get_env_variable('TELEGRAM_CHAT_ID')
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ok'):
            print("✅ Message sent successfully to Telegram")
            return True
        else:
            print(f"❌ Telegram API error: {result.get('description', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")
        return False

def main():
    """Main function to orchestrate the OTT notification process"""
    print("🚀 Starting OTT Weekly Releases Notification...")
    
    try:
        # Step 1: Fetch weekly releases
        print("📡 Fetching weekly releases...")
        releases_data = get_weekly_releases()
        
        if not releases_data:
            print("❌ Failed to fetch releases")
            sys.exit(1)
        
        # Step 2: Enrich with OMDb data
        print("🎭 Enriching with OMDb data...")
        enriched_releases = enrich_with_omdb(releases_data)
        
        # Step 3: Rank releases
        print("📊 Ranking releases...")
        ranked_releases = rank_releases(enriched_releases)
        
        # Step 4: Format message
        print("📝 Formatting message...")
        message = format_message(ranked_releases)
        
        # Step 5: Send to Telegram
        print("📱 Sending to Telegram...")
        success = send_telegram_message(message)
        
        if success:
            print("🎉 OTT notification sent successfully!")
            sys.exit(0)
        else:
            print("❌ Failed to send notification")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
