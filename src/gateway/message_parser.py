from dataclasses import dataclass

from fastapi import Request


@dataclass
class IncomingMessage:
    from_number: str
    body: str
    message_sid: str


async def parse_whatsapp_message(request: Request) -> IncomingMessage:
    form = await request.form()
    return IncomingMessage(
        from_number=form.get("From", ""),
        body=form.get("Body", ""),
        message_sid=form.get("MessageSid", ""),
    )
