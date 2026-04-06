from fastapi import APIRouter, Request, Response
from twilio.twiml.messaging_response import MessagingResponse

from src.agents.chief_of_staff import chief_of_staff
from src.gateway.message_parser import parse_whatsapp_message
from src.memory.store import get_or_create_conversation, save_message
from src.utils.logger import log

router = APIRouter(prefix="/webhook")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> Response:
    msg = await parse_whatsapp_message(request)
    log.info(
        "whatsapp_message_received",
        from_number=msg.from_number,
        message_sid=msg.message_sid,
        body_length=len(msg.body),
    )

    try:
        conversation_id = await get_or_create_conversation(msg.from_number)
        await save_message(conversation_id, role="user", content=msg.body)

        reply = await chief_of_staff.handle(msg.body, conversation_id)

        await save_message(conversation_id, role="assistant", content=reply, agent_name="chief_of_staff")
    except Exception as exc:
        log.error("whatsapp_handler_error", error=str(exc))
        reply = "Sorry, I'm having trouble right now. Try again in a moment."

    resp = MessagingResponse()
    resp.message(reply)
    return Response(content=str(resp), media_type="application/xml")
