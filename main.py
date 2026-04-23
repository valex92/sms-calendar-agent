from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import uvicorn

from config import config
from logger import logger
from llm_service import parse_sms_to_event
from calendar_service import create_event, create_task, find_event, update_event, delete_event, find_task, update_task, delete_task

app = FastAPI(title="SMS Calendar Agent")

def send_outbound_sms(to_number: str, message: str):
    try:
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        
        # If the destination is whatsapp, the sender must also be whatsapp
        from_number = config.TWILIO_PHONE_NUMBER
        if to_number.startswith("whatsapp:") and not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"
            
        message = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        logger.info(f"Outbound SMS sent with SID: {message.sid}")
    except Exception as e:
        logger.error(f"Failed to send outbound SMS: {e}")

def process_sms_background(body: str, from_number: str):
    try:
        # 1. Parse SMS using Gemini
        logger.info("1. Sending to Gemini...")
        parsed_event = parse_sms_to_event(body)
        
        if not parsed_event:
            send_outbound_sms(from_number, "Sorry, I couldn't understand the event details. Please try again.")
            return
            
        logger.info(f"Parsed Event Data: {parsed_event}")
            
        item_type = parsed_event.get("type", "event")
        action = parsed_event.get("action", "create")
        title = parsed_event.get("title")
        location = parsed_event.get("location")
        start_time = parsed_event.get("start_time")
        end_time = parsed_event.get("end_time")
        due_date = parsed_event.get("due_date")
        search_query = parsed_event.get("target_search_query")
        target_date = parsed_event.get("target_date")
        recurrence = parsed_event.get("recurrence")
        attendees = parsed_event.get("attendees")
        
        if action == "create":
            if item_type == "task":
                if not title:
                    send_outbound_sms(from_number, "I didn't get a title for the task. Please try again.")
                    return
                success, message = create_task(title, due_date)
                send_outbound_sms(from_number, message)
                return
            else:
                if not title or not start_time or not end_time:
                    send_outbound_sms(from_number, "I didn't get all the necessary details (title, start time). Please try again.")
                    return
                    
                success, message = create_event(title, start_time, end_time, location, recurrence, attendees)
                send_outbound_sms(from_number, message)
                return
                
        elif action == "update":
            if item_type == "event":
                logger.info(f"Searching for event to update: '{search_query}' on {target_date}")
                matches = find_event(search_query, target_date)
                if len(matches) == 1:
                    logger.info(f"Found match: {matches[0].get('summary')}. Updating...")
                    success, message = update_event(matches[0]['id'], title, start_time, end_time, location, recurrence, attendees)
                    logger.info(f"Result: {message}")
                    send_outbound_sms(from_number, message)
                    return
                elif len(matches) == 0:
                    logger.info("Result: Could not find any event matching that description to update.")
                    send_outbound_sms(from_number, "Could not find any event matching that description to update.")
                    return
                else:
                    logger.info("Result: Found multiple matching events. Please be more specific.")
                    send_outbound_sms(from_number, "Found multiple matching events. Please be more specific.")
                    return
            else:
                logger.info(f"Searching for task to update: '{search_query}'")
                matches = find_task(search_query)
                if len(matches) == 1:
                    logger.info(f"Found match: {matches[0].get('title')}. Updating...")
                    success, message = update_task(matches[0]['id'], title, due_date)
                    logger.info(f"Result: {message}")
                    send_outbound_sms(from_number, message)
                    return
                elif len(matches) == 0:
                    logger.info("Result: Could not find any task matching that description to update.")
                    send_outbound_sms(from_number, "Could not find any task matching that description to update.")
                    return
                else:
                    logger.info("Result: Found multiple matching tasks. Please be more specific.")
                    send_outbound_sms(from_number, "Found multiple matching tasks. Please be more specific.")
                    return
                    
        elif action == "cancel":
            if item_type == "event":
                logger.info(f"Searching for event to cancel: '{search_query}' on {target_date}")
                matches = find_event(search_query, target_date)
                if len(matches) == 1:
                    logger.info(f"Found match: {matches[0].get('summary')}. Canceling...")
                    success, message = delete_event(matches[0]['id'])
                    logger.info(f"Result: {message}")
                    send_outbound_sms(from_number, message)
                    return
                elif len(matches) == 0:
                    logger.info("Result: Could not find any event matching that description to cancel.")
                    send_outbound_sms(from_number, "Could not find any event matching that description to cancel.")
                    return
                else:
                    logger.info("Result: Found multiple matching events. Please be more specific.")
                    send_outbound_sms(from_number, "Found multiple matching events. Please be more specific.")
                    return
            else:
                logger.info(f"Searching for task to cancel: '{search_query}'")
                matches = find_task(search_query)
                if len(matches) == 1:
                    logger.info(f"Found match: {matches[0].get('title')}. Canceling...")
                    success, message = delete_task(matches[0]['id'])
                    logger.info(f"Result: {message}")
                    send_outbound_sms(from_number, message)
                    return
                elif len(matches) == 0:
                    logger.info("Result: Could not find any task matching that description to cancel.")
                    send_outbound_sms(from_number, "Could not find any task matching that description to cancel.")
                    return
                else:
                    logger.info("Result: Found multiple matching tasks. Please be more specific.")
                    send_outbound_sms(from_number, "Found multiple matching tasks. Please be more specific.")
                    return
                    
        send_outbound_sms(from_number, "I'm not sure what you want me to do.")
        return
    
    except Exception as e:
        logger.exception(f"Unhandled error processing SMS: {e}")
        send_outbound_sms(from_number, "Oops! An internal error occurred while processing your request. Please check the logs.")

@app.post("/webhook")
async def twilio_webhook(request: Request, background_tasks: BackgroundTasks, Body: str = Form(...), From: str = Form(...)):
    logger.info(f"Received SMS from {From}: {Body}")
    
    # SECURITY: Verify the sender is your phone number
    # Twilio prepends 'whatsapp:' if using their WhatsApp sandbox
    normalized_from = From.replace("whatsapp:", "")
    if config.ALLOWED_PHONE_NUMBERS and normalized_from not in config.ALLOWED_PHONE_NUMBERS:
        logger.warning(f"Blocked unauthorized request from {From}")
        # Return a generic response or ignore it entirely to not give away that the bot exists
        return respond_with_sms("Unauthorized sender.")
    
    background_tasks.add_task(process_sms_background, Body, From)
    return PlainTextResponse(content="<Response></Response>", media_type="application/xml")

def respond_with_sms(message: str) -> PlainTextResponse:
    resp = MessagingResponse()
    resp.message(message)
    return PlainTextResponse(content=str(resp), media_type="application/xml")

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
