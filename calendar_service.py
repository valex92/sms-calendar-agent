import os.path
import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from logger import logger
from config import config

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks"
]

def get_credentials():
    """Authenticates and returns the Google API credentials using a Service Account."""
    if not os.path.exists("service_account.json"):
        logger.error("Missing service_account.json! Please download it from Google Cloud Console.")
        return None
        
    try:
        creds = service_account.Credentials.from_service_account_file(
            "service_account.json", scopes=SCOPES
        )
        return creds
    except Exception as e:
        logger.error(f"Failed to load service account credentials: {e}")
        return None

def get_calendar_service():
    """Returns the Google Calendar API service."""
    creds = get_credentials()
    if not creds: return None
    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        logger.error(f"An error occurred initializing Calendar API: {error}")
        return None

def get_tasks_service():
    """Returns the Google Tasks API service."""
    creds = get_credentials()
    if not creds: return None
    try:
        service = build("tasks", "v1", credentials=creds)
        return service
    except HttpError as error:
        logger.error(f"An error occurred initializing Tasks API: {error}")
        return None

def create_event(title: str, start_time: str, end_time: str, location: str = None, recurrence: str = None):
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

    try:
        event = service.events().insert(calendarId=config.TARGET_CALENDAR_ID, body=event).execute()
        logger.info('Event created: %s' % (event.get('htmlLink')))
        return True, f"Event '{title}' scheduled successfully!"
    except HttpError as error:
        logger.error(f"An error occurred creating event: {error}")
        return False, f"Failed to schedule event. Please check the logs."

def create_task(title: str, due_date: str = None):
    service = get_tasks_service()
    if not service:
        return False, "Failed to authenticate with Google Tasks. Is credentials.json present?"

    task = {
        'title': title
    }
    if due_date:
        task['due'] = due_date

    try:
        task = service.tasks().insert(tasklist='@default', body=task).execute()
        logger.info('Task created: %s' % (task.get('title')))
        return True, f"Task '{title}' added successfully!"
    except HttpError as error:
        logger.error(f"An error occurred creating task: {error}")
        return False, f"Failed to add task. Please check the logs."

def find_event(query: str, date_str: str):
    service = get_calendar_service()
    if not service: return []
    
    try:
        if date_str:
            # Broaden the search to +/- 7 days to handle cases where the user doesn't 
            # specify the exact date in the update message, or Gemini infers it slightly wrong.
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            timeMin = (date_obj - datetime.timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
            timeMax = (date_obj + datetime.timedelta(days=7)).strftime("%Y-%m-%dT23:59:59Z")
            events_result = service.events().list(
                calendarId=config.TARGET_CALENDAR_ID, 
                q=query, 
                timeMin=timeMin, 
                timeMax=timeMax,
                singleEvents=True
            ).execute()
        else:
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId=config.TARGET_CALENDAR_ID, 
                q=query, 
                timeMin=now, 
                singleEvents=True
            ).execute()
            
        return events_result.get('items', [])
    except HttpError as error:
        logger.error(f"An error occurred finding event: {error}")
        return []

def update_event(event_id: str, new_title: str, new_start: str, new_end: str, location: str = None, recurrence: str = None):
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
        matches = [t for t in tasks if query.lower() in t.get('title', '').lower()]
        return matches
    except HttpError as error:
        logger.error(f"Error finding task: {error}")
        return []

def update_task(task_id: str, new_title: str, new_due: str):
    service = get_tasks_service()
    if not service: return False, "Auth failed."
    try:
        task = service.tasks().get(tasklist='@default', task=task_id).execute()
        if new_title: task['title'] = new_title
        if new_due: task['due'] = new_due
        
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
    logger.info("Initiating Google API authentication...")
    creds = get_credentials()
    if creds:
        logger.info("Successfully authenticated with Google APIs!")
