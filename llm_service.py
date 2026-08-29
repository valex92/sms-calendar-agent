import json
import datetime
import os
import google.generativeai as genai
from config import config
from logger import logger

LOG_FILE = "agent.log"
LOG_CONTEXT_LINES = 50

if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)

# Using Gemini 3 Flash Preview as you requested!
model = genai.GenerativeModel('gemini-3-flash-preview', generation_config={"response_mime_type": "application/json"})

def get_recent_log_context(max_lines: int = LOG_CONTEXT_LINES) -> str:
    """
    Reads the last N lines of agent.log, returning only the meaningful
    conversation entries (SMS received, parsed data, action results).
    Skips noisy lines like stack traces, auth flows, and startup logs.
    """
    if not os.path.exists(LOG_FILE):
        return ""
    try:
        with open(LOG_FILE, "r") as f:
            all_lines = f.readlines()
        # Grab the tail
        tail = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
        # Filter to meaningful conversation lines
        keep_keywords = [
            "Received SMS",
            "Parsed Event Data",
            "Event created",
            "Task created",
            "Event updated",
            "Task updated",
            "Event deleted",
            "Task deleted",
            "Result:",
            "Searching for",
            "Found match",
            "--- Testing",
        ]
        filtered = []
        for line in tail:
            if any(kw in line for kw in keep_keywords):
                filtered.append(line.strip())
        return "\n".join(filtered)
    except Exception:
        return ""

def parse_sms_to_event(sms_text: str, timezone_offset: str = "-04:00") -> dict:
    """
    Parses natural language SMS text to extract calendar event details.
    """
    now = datetime.datetime.now().isoformat()
    
    # Build conversation history from recent logs
    log_context = get_recent_log_context()
    
    # Build the log context section for the prompt
    history_section = ""
    if log_context:
        history_section = f"""
    === RECENT CONVERSATION HISTORY ===
    Below are the most recent interactions with this assistant. Use this to resolve
    ambiguous references like "the last event", "that meeting", "change it to", etc.
    For update/cancel actions, use the history to identify the correct target_search_query
    and target_date when the user doesn't explicitly name the event/task.
    
{log_context}
    === END HISTORY ===
    """

    prompt = f"""
    You are an intelligent calendar assistant. 
    The current date and time is: {now}
    The user's timezone offset is: {timezone_offset}
    {history_section}
    Your task is to parse the following SMS message and extract the calendar event details.
    
    SMS Message: "{sms_text}"
    
    Respond ONLY with a valid JSON object matching this schema:
    {{
        "type": "event", // or "task"
        "action": "create", // or "update", or "cancel"
        "all_day": "Boolean, true if the event is an all-day or full-day event (e.g. 'all day', 'full day', birthdays, anniversaries, holidays, vacations/trips, school closures, or events where no specific time is mentioned). False for timed events or tasks.",
        "target_search_query": "String, if action is update/cancel, a short 1-3 word keyword to search for the original item (e.g. 'haircut'). Use conversation history to find the exact title if the user says 'the last event' or similar. Null if creating.",
        "target_date": "ISO 8601 string of the DATE ONLY (e.g. '2026-04-17') the original event/task was scheduled on. Use conversation history to find this if the user doesn't specify. Null if creating.",
        "title": "String, a short, sensible, and descriptive title for the event (e.g., 'Trip to Disney', 'Doctor Appointment'). Omit time and date information.",
        "location": "String, physical address or location if mentioned, otherwise null",
        "start_time": "String. For timed events: ISO 8601 datetime string, e.g., 2026-04-17T14:00:00{timezone_offset}. For all-day events: Date string 'YYYY-MM-DD', e.g., '2026-04-17'. Null if it's a task or cancelling.",
        "end_time": "String. For timed events: ISO 8601 datetime string, e.g., 2026-04-17T15:00:00{timezone_offset}. For all-day events: Exclusive end date string 'YYYY-MM-DD' representing the day after the event ends (e.g., '2026-04-18' for a 1-day event on '2026-04-17', or '2026-04-20' for a multi-day event spanning April 17-19). Null if it's a task or cancelling.",
        "due_date": "ISO 8601 datetime string if it's a task with a deadline, otherwise null.",
        "recurrence": "String, RFC 5545 RRULE (e.g. 'RRULE:FREQ=YEARLY', 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE') if recurring, otherwise null.",
        "attendees": "Array of strings (email addresses) to invite, otherwise null.",
        "description": "String, any additional notes, details, or description for the event or task mentioned by the user, otherwise null."
    }}
    
    Make sure to infer relative dates (tomorrow, next wednesday) properly based on the current date and time.
    CRITICAL INSTRUCTION FOR ALL-DAY EVENTS: If the user mentions 'all day', 'full day', or creates an event for a day without specifying start/end hours (e.g., 'Mom\'s Birthday', 'vacation Monday through Friday', 'school closed tomorrow', 'primrose closed on 9/7 all day'), set 'all_day' to true, 'start_time' to 'YYYY-MM-DD', and 'end_time' to the exclusive end date 'YYYY-MM-DD' (the day immediately following the last day of the event).
    CRITICAL INSTRUCTION: If the user mentions adding work calendars or inviting work emails (e.g. "add our work calendars", "invite our work emails"), you MUST include 'attendee1@example.com' and 'attendee2@example.com' in the attendees array. Also extract any other explicit email addresses mentioned.
    """
    
    response = model.generate_content(prompt)
    
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        logger.error(f"Error parsing LLM response: {response.text}")
        logger.exception(e)
        return None
