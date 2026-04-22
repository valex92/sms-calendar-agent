import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PORT = int(os.getenv("PORT", "8000"))
    HOST = os.getenv("HOST", "0.0.0.0")
    
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
    
    allowed_numbers_str = os.getenv("ALLOWED_PHONE_NUMBERS", os.getenv("ALLOWED_PHONE_NUMBER", ""))
    ALLOWED_PHONE_NUMBERS = [num.strip() for num in allowed_numbers_str.split(",") if num.strip()]
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    TARGET_CALENDAR_ID = os.getenv("TARGET_CALENDAR_ID", "primary")

config = Config()
