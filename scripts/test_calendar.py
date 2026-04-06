import asyncio
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from src.tools.calendar import get_todays_events, format_events_for_prompt

async def main():
    events = await get_todays_events()
    print(format_events_for_prompt(events, header="Today's events:"))

asyncio.run(main())
