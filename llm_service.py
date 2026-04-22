import json
import datetime
import google.generativeai as genai
from config import config
from logger import logger

if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)

# Using Gemini 3 Flash Preview as you requested!
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"response_mime_type": "application/json"})

def parse_sms_to_event(sms_text: str, timezone_offset: str = "-04:00") -> dict:
    """
    Parses natural language SMS text to extract calendar event details.
    """
    now = datetime.datetime.now().isoformat()
    
    prompt = f"""
    You are an intelligent calendar assistant. 
    The current date and time is: {now}
    The user's timezone offset is: {timezone_offset}
    
    Your task is to parse the following SMS message and extract the calendar event details.
    
    SMS Message: "{sms_text}"
    
    Respond ONLY with a valid JSON object matching this schema:
    {{
        "type": "event", // or "task"
        "action": "create", // or "update", or "cancel"
        "target_search_query": "String, if action is update/cancel, a short 1-3 word keyword to search for the original item (e.g. 'haircut'). Null if creating.",
        "target_date": "ISO 8601 string of the DATE ONLY (e.g. '2026-04-17') the original event was supposed to happen on. Null if creating.",
        "title": "String, a short, sensible, and descriptive title for the event (e.g., 'Trip to Disney', 'Doctor Appointment'). Omit time and date information.",
        "location": "String, physical address or location if mentioned, otherwise null",
        "start_time": "ISO 8601 datetime string, e.g., 2026-04-17T14:00:00{timezone_offset}. Null if it's a task or cancelling.",
        "end_time": "ISO 8601 datetime string, e.g., 2026-04-17T15:00:00{timezone_offset}. Null if it's a task or cancelling.",
        "due_date": "ISO 8601 datetime string if it's a task with a deadline, otherwise null.",
        "recurrence": "String, RFC 5545 RRULE (e.g. 'RRULE:FREQ=YEARLY', 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE') if recurring, otherwise null."
    }}
    
    Make sure to infer relative dates (tomorrow, next wednesday) properly based on the current date and time.
    """
    
    response = model.generate_content(prompt)
    
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        logger.error(f"Error parsing LLM response: {response.text}")
        logger.exception(e)
        return None
