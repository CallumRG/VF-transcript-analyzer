from datetime import datetime
import pytz
import requests
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Fetch the environment variables
api_key = os.getenv('API_KEY')
project_id = os.getenv('PROJECT_ID')
version_id = os.getenv('VERSION_ID')

client = OpenAI()

def fetch_transcripts(api_key, project_id, time_range="All%20time", tag=None):
    try:
        # Building the URL with optional tag parameter
        url = f'https://api.voiceflow.com/v2/transcripts/{project_id}?range={time_range}'
        if tag:
            url += f'&tag={tag}'
        
        # Fetching recent transcripts
        response = requests.get(
            url,
            headers={
                'Authorization': api_key,
                'Accept': 'application/json'
            }
        )
        
        response.raise_for_status()  # Raises an exception for HTTP errors
        transcripts = response.json()
        transcripts_dialog = []
        if transcripts:
            for transcript in transcripts:
                transcript_id = transcript['_id']
                
                # Fetching full transcript
                full_transcript_response = requests.get(
                    f'https://api.voiceflow.com/v2/transcripts/{project_id}/{transcript_id}',
                    headers={
                        'Authorization': api_key,
                        'Accept': 'application/json'
                    }
                )
                
                full_transcript_response.raise_for_status()
                full_transcript = full_transcript_response.json()
                if full_transcript:
                    transcripts_dialog.append(full_transcript)
            
            return transcripts_dialog
        else:
            print('No transcripts found.')
            return None
    
    except requests.exceptions.RequestException as error:
        print('Error fetching recent transcript:', error)
        return None
    
def generate_markdown(transcript):
    if not transcript:
        print("Transcript is empty.")
        return None
    
    # Time zone information
    time_zone = 'America/Toronto'
    tz = pytz.timezone(time_zone)

    # Formatting the start time of the transcript
    start_time = datetime.fromisoformat(transcript[0]['startTime'])
    zoned_date = start_time.astimezone(tz)
    formatted_date = zoned_date.strftime('%Y-%m-%d %H:%M:%S')

    title = ''
    markdown = f"### Date: {formatted_date}\n\n---\n\n"
    last_user_message = ''

    for entry in transcript:
        if entry['type'] == 'text':
            message = entry['payload']['payload']['message']
            markdown += f"*Chatbot:* {message}\n\n\n"

        if entry['type'] == 'request' and (entry['payload']['type'].startswith('path-') or entry['payload']['type'] == 'intent'):
            user_message = (
                entry['payload']['payload'].get('label') or
                entry['payload']['payload'].get('query') or
                entry['payload']['payload']['intent'].get('name')
            )
            if not title:
                title = user_message
            if user_message != last_user_message and user_message != 'End':
                markdown += f"*User:* {user_message}\n\n\n"
                last_user_message = user_message

    markdown = f"# {title.upper()} Report type\n\n" + markdown
    return {'markdown': markdown, 'title': title, 'formatted_date': formatted_date}

def analyze_satisfaction(text):
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Analyze the satisfaction of the following text log for the user and provide a score of 0 for (Bad Satisfaction) or 1 for (Positive Satisfaction). A neutral satisfaction should skewed towards giving 1 for (Positive Satisfaction) Only return 0 or 1, no other characters: {text}"}
        ]
    )
    print(response.usage)
    sentiment = response.choices[0].message.content.strip()

    if sentiment == "0":
        return "Negative"
    elif sentiment == "1":
        return "Positive"
    else:
        return "Exclude"

for transcript in fetch_transcripts(api_key, project_id):
    print(transcript)
    markdown = generate_markdown(transcript)['markdown']
    #print(markdown)
    #print(analyze_satisfaction(markdown))

