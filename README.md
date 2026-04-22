# SMS to Google Calendar Agent

An AI agent designed to be deployed on a Raspberry Pi that listens for incoming SMS via Twilio, uses Google Gemini to parse the natural language text into event details, and automatically schedules the event on your Google Calendar.

## Setup Instructions

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration:**
   - Copy `.env.example` to `.env` and fill in your API keys:
     - `TWILIO_ACCOUNT_SID` & `TWILIO_AUTH_TOKEN` (from Twilio console)
     - `TWILIO_PHONE_NUMBER` (your Twilio phone number)
     - `GEMINI_API_KEY` (from Google AI Studio)
   - Place your Google Calendar OAuth `credentials.json` file in the root of this project.

3. **First Run (Google Auth):**
   - Run the calendar service locally first to authenticate with Google:
     ```bash
     python calendar_service.py
     ```
   - A browser window will open asking you to log into your Google Account and grant permission.
   - Once granted, a `token.json` file will be generated. You can now run this headless on your Raspberry Pi!

4. **Running the Server:**
   ```bash
   python main.py
   ```
   The server will start on port 8000 by default.

5. **Exposing Webhook:**
   - Use `ngrok` or Cloudflare Tunnels to expose port 8000 to the internet.
   - Example with ngrok: `ngrok http 8000`
   - Copy the HTTPS URL provided by ngrok.

6. **Configure Twilio:**
   - Go to your Twilio Phone Number settings.
   - Under "Messaging", set "A MESSAGE COMES IN" to Webhook and paste your ngrok URL followed by `/webhook` (e.g., `https://your-ngrok-url.ngrok-free.app/webhook`).
   - Ensure the method is set to `HTTP POST`.

## Usage
Text your Twilio number:
- *"Schedule a meeting with the marketing team tomorrow at 2pm for an hour"*
- *"Haircut next Wednesday at 10am"*
