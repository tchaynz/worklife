import asyncio
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from src.tools.gmail import get_unread_emails, format_emails_for_prompt

async def main():
    emails = await get_unread_emails(max_results=5)
    print(format_emails_for_prompt(emails, header="Unread emails:"))

asyncio.run(main())
