import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from bot.client import CatieBot


def main():
    settings = get_settings()
    
    if not settings.discord_bot_token:
        print("Error: DISCORD_BOT_TOKEN not set")
        sys.exit(1)
    
    bot = CatieBot()
    
    try:
        bot.run(settings.discord_bot_token)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
