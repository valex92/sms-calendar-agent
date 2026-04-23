import os.path
import datetime
from difflib import SequenceMatcher

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from logger import logger
from config import config

# If modifying these scopes, delete the file token.json.
USER_SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar.events"
]

def get_user_credentials():
    """Authenticates using OAuth (token.json) for Tasks."""
    creds = None
    
    # 1. Try to load existing user credentials from token.json
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", USER_SCOPES)
        
    # 2. If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                creds = None
                
        if not creds:
            if os.path.exists("credentials.json"):
                logger.info("Found credentials.json. Starting OAuth flow for Tasks...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", USER_SCOPES
                )
                # This will open a browser to authenticate
                creds = flow.run_local_server(port=0)
            else:
                logger.error("Missing credentials.json for Tasks!")
                return None
                
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
    return creds

def get_calendar_service():
    """Returns the Google Calendar API service."""
    creds = get_user_credentials()
    if not creds: return None
    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        logger.error(f"An error occurred initializing Calendar API: {error}")
        return None

def get_tasks_service():
    """Returns the Google Tasks API service."""
    creds = get_user_credentials()
    if not creds: return None
    try:
        service = build("tasks", "v1", credentials=creds)
        return service
    except HttpError as error:
        logger.error(f"An error occurred initializing Tasks API: {error}")
        return None

def create_event(title: str, start_time: str, end_time: str, location: str = None, recurrence: str = None, attendees: list = None, description: str = None):
    service = get_calendar_service()
    if not service:
        return False, "Failed to authenticate with Google Calendar. Is credentials.json present?"

    event = {
        'summary': title,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/New_York',
        },
    }
    
    if location:
        event['location'] = location
        
    if recurrence:
        event['recurrence'] = [recurrence]
        
    if attendees:
        event['attendees'] = [{'email': email} for email in attendees]

    if description:
        event['description'] = description

    try:
        event = service.events().insert(calendarId=config.TARGET_CALENDAR_ID, body=event).execute()
        logger.info('Event created: %s' % (event.get('htmlLink')))
        return True, f"Event '{title}' scheduled successfully!"
    except HttpError as error:
        logger.error(f"An error occurred creating event: {error}")
        return False, f"Failed to schedule event. Please check the logs."

def create_task(title: str, due_date: str = None, notes: str = None):
    service = get_tasks_service()
    if not service:
        return False, "Failed to authenticate with Google Tasks. Is credentials.json present?"

    task = {
        'title': title
    }
    if due_date:
        task['due'] = due_date
    if notes:
        task['notes'] = notes

    try:
        task = service.tasks().insert(tasklist='@default', body=task).execute()
        logger.info('Task created: %s' % (task.get('title')))
        return True, f"Task '{title}' added successfully!"
    except HttpError as error:
        logger.error(f"An error occurred creating task: {error}")
        return False, f"Failed to add task. Please check the logs."

FUZZY_MATCH_THRESHOLD = 0.4

def _fuzzy_score(query: str, text: str) -> float:
    """Returns a similarity score (0-1) between the query and text."""
    return SequenceMatcher(None, query.lower(), text.lower()).ratio()

def _get_time_window(date_str: str = None):
    """
    Returns (timeMin, timeMax) strings for the Calendar API.
    - If date_str is provided: +/- 7 days around that date.
    - If not: from now to 30 days in the future.
    """
    if date_str:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        timeMin = (date_obj - datetime.timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
        timeMax = (date_obj + datetime.timedelta(days=7)).strftime("%Y-%m-%dT23:59:59Z")
    else:
        now = datetime.datetime.utcnow()
        timeMin = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        timeMax = (now + datetime.timedelta(days=30)).strftime("%Y-%m-%dT23:59:59Z")
    return timeMin, timeMax

def _fuzzy_filter_events(events: list, query: str) -> list:
    """
    Scores events against the query using fuzzy matching and returns
    those above the threshold, sorted by best match first.
    """
    scored = []
    for event in events:
        summary = event.get('summary', '')
        score = _fuzzy_score(query, summary)
        if score >= FUZZY_MATCH_THRESHOLD:
            scored.append((score, event))
    # Sort by best match first
    scored.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in scored]

def find_event(query: str, date_str: str):
    service = get_calendar_service()
    if not service: return []
    
    timeMin, timeMax = _get_time_window(date_str)
    
    try:
        # Pass 1: Use Google Calendar's built-in q search
        events_result = service.events().list(
            calendarId=config.TARGET_CALENDAR_ID, 
            q=query, 
            timeMin=timeMin, 
            timeMax=timeMax,
            singleEvents=True
        ).execute()
        matches = events_result.get('items', [])
        
        if matches:
            logger.info(f"Found {len(matches)} event(s) via q-search for '{query}'")
            return matches
        
        # Pass 2: Fetch all events in the window and fuzzy-match locally
        logger.info(f"q-search returned 0 results for '{query}', trying fuzzy match...")
        all_events_result = service.events().list(
            calendarId=config.TARGET_CALENDAR_ID, 
            timeMin=timeMin, 
            timeMax=timeMax,
            singleEvents=True
        ).execute()
        all_events = all_events_result.get('items', [])
        fuzzy_matches = _fuzzy_filter_events(all_events, query)
        
        if fuzzy_matches:
            logger.info(f"Fuzzy match found {len(fuzzy_matches)} event(s) for '{query}': {[e.get('summary') for e in fuzzy_matches]}")
        else:
            logger.info(f"Fuzzy match also returned 0 results for '{query}' across {len(all_events)} events in window")
        
        return fuzzy_matches
    except HttpError as error:
        logger.error(f"An error occurred finding event: {error}")
        return []


def update_event(event_id: str, new_title: str, new_start: str, new_end: str, location: str = None, recurrence: str = None, attendees: list = None, description: str = None):
    service = get_calendar_service()
    if not service: return False, "Auth failed."
    
    try:
        event = service.events().get(calendarId=config.TARGET_CALENDAR_ID, eventId=event_id).execute()
        if new_title: event['summary'] = new_title
        if new_start: 
            event['start']['dateTime'] = new_start
            event['start']['timeZone'] = 'America/New_York'
        if new_end: 
            event['end']['dateTime'] = new_end
            event['end']['timeZone'] = 'America/New_York'
        if location: event['location'] = location
        if recurrence: event['recurrence'] = [recurrence]
        if attendees: event['attendees'] = [{'email': email} for email in attendees]
        if description: event['description'] = description
            
        updated_event = service.events().patch(calendarId=config.TARGET_CALENDAR_ID, eventId=event_id, body=event).execute()
        logger.info(f"Event updated: {updated_event.get('htmlLink')}")
        return True, "Event updated successfully!"
    except HttpError as error:
        logger.error(f"Error updating event: {error}")
        return False, "Failed to update event."

def delete_event(event_id: str):
    service = get_calendar_service()
    if not service: return False, "Auth failed."
    try:
        service.events().delete(calendarId=config.TARGET_CALENDAR_ID, eventId=event_id).execute()
        logger.info(f"Event deleted: {event_id}")
        return True, "Event cancelled successfully!"
    except HttpError as error:
        logger.error(f"Error deleting event: {error}")
        return False, "Failed to cancel event."

def find_task(query: str):
    service = get_tasks_service()
    if not service: return []
    try:
        tasks_result = service.tasks().list(tasklist='@default').execute()
        tasks = tasks_result.get('items', [])
        
        # Score all tasks using fuzzy matching
        scored = []
        for t in tasks:
            title = t.get('title', '')
            score = _fuzzy_score(query, title)
            if score >= FUZZY_MATCH_THRESHOLD:
                scored.append((score, t))
        
        # Sort by best match first
        scored.sort(key=lambda x: x[0], reverse=True)
        matches = [t for _, t in scored]
        
        if matches:
            logger.info(f"Found {len(matches)} task(s) for '{query}': {[t.get('title') for t in matches]}")
        else:
            logger.info(f"No tasks matched '{query}' (checked {len(tasks)} tasks)")
        
        return matches
    except HttpError as error:
        logger.error(f"Error finding task: {error}")
        return []

def update_task(task_id: str, new_title: str, new_due: str, new_notes: str = None):
    service = get_tasks_service()
    if not service: return False, "Auth failed."
    try:
        task = service.tasks().get(tasklist='@default', task=task_id).execute()
        if new_title: task['title'] = new_title
        if new_due: task['due'] = new_due
        if new_notes: task['notes'] = new_notes
        
        updated_task = service.tasks().patch(tasklist='@default', task=task_id, body=task).execute()
        logger.info(f"Task updated: {updated_task.get('title')}")
        return True, "Task updated successfully!"
    except HttpError as error:
        logger.error(f"Error updating task: {error}")
        return False, "Failed to update task."

def delete_task(task_id: str):
    service = get_tasks_service()
    if not service: return False, "Auth failed."
    try:
        service.tasks().delete(tasklist='@default', task=task_id).execute()
        logger.info(f"Task deleted: {task_id}")
        return True, "Task deleted successfully!"
    except HttpError as error:
        logger.error(f"Error deleting task: {error}")
        return False, "Failed to delete task."

if __name__ == '__main__':
    # Run this file directly to trigger the initial OAuth flow and generate token.json
    logger.info("Initiating Google Tasks API authentication...")
    creds = get_user_credentials()
    if creds:
        logger.info("Successfully authenticated with Google Tasks and Calendar APIs!")
