from llm_service import parse_sms_to_event
from calendar_service import create_event, create_task, find_event, update_event, delete_event, find_task, update_task, delete_task
from logger import logger

def test_pipeline(text: str):
    logger.info(f"\n--- Testing with input: '{text}' ---")
    logger.info("1. Sending to Gemini...")
    parsed_event = parse_sms_to_event(text)
    
    if not parsed_event:
        logger.error("Failed to parse event from Gemini.")
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
    description = parsed_event.get("description")
    
    if action == "create":
        if item_type == "task":
            logger.info("2. Sending to Google Tasks...")
            success, message = create_task(title, due_date, description)
            logger.info(f"Result: {message}")
        else:
            logger.info("2. Sending to Google Calendar...")
            success, message = create_event(title, start_time, end_time, location, recurrence, attendees, description)
            logger.info(f"Result: {message}")
    elif action == "update":
        if item_type == "event":
            logger.info(f"Searching for event to update: '{search_query}' on {target_date}")
            matches = find_event(search_query, target_date)
            if len(matches) == 1:
                event_id = matches[0]['id']
                logger.info(f"Found match: {matches[0].get('summary')}. Updating...")
                success, message = update_event(event_id, title, start_time, end_time, location, recurrence, attendees, description)
                logger.info(f"Result: {message}")
            elif len(matches) == 0:
                logger.info("Result: Could not find any event matching that description to update.")
            else:
                logger.info("Result: Found multiple matching events. Please be more specific.")
        else:
            logger.info(f"Searching for task to update: '{search_query}'")
            matches = find_task(search_query)
            if len(matches) == 1:
                task_id = matches[0]['id']
                logger.info(f"Found match: {matches[0].get('title')}. Updating...")
                success, message = update_task(task_id, title, due_date, description)
                logger.info(f"Result: {message}")
            elif len(matches) == 0:
                logger.info("Result: Could not find any task matching that description to update.")
            else:
                logger.info("Result: Found multiple matching tasks. Please be more specific.")
    elif action == "cancel":
        if item_type == "event":
            logger.info(f"Searching for event to cancel: '{search_query}' on {target_date}")
            matches = find_event(search_query, target_date)
            if len(matches) == 1:
                event_id = matches[0]['id']
                logger.info(f"Found match: {matches[0].get('summary')}. Canceling...")
                success, message = delete_event(event_id)
                logger.info(f"Result: {message}")
            elif len(matches) == 0:
                logger.info("Result: Could not find any event matching that description to cancel.")
            else:
                logger.info("Result: Found multiple matching events. Please be more specific.")
        else:
            logger.info(f"Searching for task to cancel: '{search_query}'")
            matches = find_task(search_query)
            if len(matches) == 1:
                task_id = matches[0]['id']
                logger.info(f"Found match: {matches[0].get('title')}. Canceling...")
                success, message = delete_task(task_id)
                logger.info(f"Result: {message}")
            elif len(matches) == 0:
                logger.info("Result: Could not find any task matching that description to cancel.")
            else:
                logger.info("Result: Found multiple matching tasks. Please be more specific.")
    else:
        logger.warning(f"Action '{action}' is not currently implemented in this project.")

if __name__ == "__main__":
    print("Welcome to the Local Testing Sandbox!")
    print("This bypasses Twilio and the web server entirely.")
    while True:
        user_input = input("\nEnter a test SMS message (or 'q' to quit): ")
        if user_input.lower() == 'q':
            break
        test_pipeline(user_input)
