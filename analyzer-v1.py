from datetime import datetime
import pytz
import requests
from openai import OpenAI
from dotenv import load_dotenv
import os
import tkinter as tk
from tkinter import ttk, messagebox

load_dotenv()
default_api_key = os.getenv('API_KEY', '')
default_project_id = os.getenv('PROJECT_ID', '')

client = OpenAI()

class Session:
    def __init__(self, vf_transcript_dialog_session, vf_session_id, rating ="Exclude"):
        self.vf_transcript_dialog_session = vf_transcript_dialog_session
        self.vf_session_id = vf_session_id
        self.vf_transcript_dialog_session_markdown = ""
        self.rating = rating


    def generate_markdown(self):
        if not self.vf_transcript_dialog_session:
            print("Transcript is empty.")
            return None

        # Time zone information
        time_zone = 'America/Toronto'
        tz = pytz.timezone(time_zone)

        # Formatting the start time of the transcript
        start_time = datetime.fromisoformat(self.vf_transcript_dialog_session[0]['startTime'])
        zoned_date = start_time.astimezone(tz)
        formatted_date = zoned_date.strftime('%Y-%m-%d %H:%M:%S')

        title = ''
        markdown = f"### Date: {formatted_date}\n\n---\n\n"
        last_user_message = ''

        for entry in self.vf_transcript_dialog_session:
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

        self.vf_transcript_dialog_session_markdown = f"# {title.upper()} Report type\n\n" + markdown
        self.session_date = formatted_date
    def analyze_satisfaction(self):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Analyze the satisfaction of the following text log for the user and provide a score of 0 for (Bad Satisfaction) or 1 for (Positive Satisfaction). A neutral satisfaction should be skewed towards giving 1 for (Positive Satisfaction). Only return 0 or 1, no other characters: {self.vf_transcript_dialog_session_markdown}"}
            ]
        )
        print(response.usage)
        sentiment = response.choices[0].message.content.strip()

        if sentiment == "0":
            self.rating = "Negative"
        elif sentiment == "1":
            self.rating = "Positive"
        else:
            self.rating = "Exclude"
    

class Transcript:
    def __init__(self, vf_transcript_info):
        self.vf_transcript_info = vf_transcript_info
        self.vf_transcript_dialog = None
        self.vf_sessions = None
        

    def fetch_dialog(self, vf_api_key, vf_project_id):
        transcript_id = self.vf_transcript_info['_id']

        full_transcript_response = requests.get(
            f'https://api.voiceflow.com/v2/transcripts/{vf_project_id}/{transcript_id}',
            headers={
                'Authorization': vf_api_key,
                'Accept': 'application/json'
            }
        )

        full_transcript_response.raise_for_status()
        full_transcript = full_transcript_response.json()

        if full_transcript:
            self.vf_transcript_dialog = full_transcript
    
    def split_sessions(self, date = None):
        
        self.vf_sessions = []
        current_chunk = []
        count = 1

        for item in self.vf_transcript_dialog:
            if item["type"] == "request" and item["payload"].get("type") == "launch":

                if current_chunk:
                    self.vf_sessions.append(Session(current_chunk, self.vf_transcript_info['_id'] + str(count)))
                    count += 1

                current_chunk = [item]
            else:
                current_chunk.append(item)

        # Add the last chunk to the chunks list
        if current_chunk:
            self.vf_sessions.append(Session(current_chunk, self.vf_transcript_info['_id'] + str(count)))

class ProjectTranscripts:
    def __init__(self, vf_api_key, vf_project_id, time_range="Today", tag=None):
        self.vf_api_key = vf_api_key
        self.vf_project_id = vf_project_id
        self.time_range = time_range
        self.tag = tag

        self.transcripts = []

    def fetch_transcripts(self):
        try:
            # Building the URL with optional tag parameter
            url = f'https://api.voiceflow.com/v2/transcripts/{self.vf_project_id}?range={self.time_range}'
            if self.tag:
                url += f'&tag={self.tag}'

            # Fetching recent transcripts
            response = requests.get(
                url,
                headers={
                    'Authorization': self.vf_api_key,
                    'Accept': 'application/json'
                }
            )

            response.raise_for_status()  # Raises an exception for HTTP errors
            transcripts = response.json()

            if transcripts:
                for transcript in transcripts:
                    self.transcripts.append(Transcript(transcript))
            else:
                print('No transcripts found.')
                return None

        except requests.exceptions.RequestException as error:
            print('Error fetching recent transcript:', error)
            return None

""" # Example usage
project_transcripts = ProjectTranscripts(api_key, project_id)
project_transcripts.fetch_transcripts()
for transcript in project_transcripts.transcripts:
    #print(transcript.vf_transcript_info)
    transcript.fetch_dialog(project_transcripts.vf_api_key, project_transcripts.vf_project_id)
    #print(transcript.vf_transcript_dialog)
    transcript.split_sessions()
    print(transcript.vf_sessions)

    for session in transcript.vf_sessions:
        session.generate_markdown()
        print(session.vf_transcript_dialog_session_markdown)
        session.analyze_satisfaction()
        print(session.rating)
    print()
    print() """

class MarkdownViewer(tk.Toplevel):
    def __init__(self, parent, markdown_text):
        super().__init__(parent)
        self.title("Session Markdown")
        self.geometry("600x400")

        text_widget = tk.Text(self, wrap=tk.WORD)
        text_widget.pack(expand=1, fill=tk.BOTH)
        text_widget.insert(tk.END, markdown_text)
        text_widget.config(state=tk.DISABLED)

def fetch_and_analyze():
    api_key = api_key_entry.get()
    project_id = project_id_entry.get()
    time_range = time_range_combo.get()
    tag = tag_entry.get()

    project_transcripts = ProjectTranscripts(api_key, project_id, time_range=time_range, tag=tag)
    project_transcripts.fetch_transcripts()

    rows = []
    for transcript in project_transcripts.transcripts:
        transcript.fetch_dialog(project_transcripts.vf_api_key, project_transcripts.vf_project_id)
        transcript.split_sessions()

        for session in transcript.vf_sessions:
            session.generate_markdown()
            session.analyze_satisfaction()
            rows.append((transcript.vf_transcript_info['_id'], len(rows) + 1, session.rating, session.vf_transcript_dialog_session_markdown))

    for row in rows:
        tree.insert("", tk.END, values=row)

def on_double_click(event):
    item = tree.selection()[0]
    markdown_text = tree.item(item, 'values')[3]
    MarkdownViewer(root, markdown_text)

# GUI Setup
root = tk.Tk()
root.title("Transcript Analyzer")

mainframe = ttk.Frame(root, padding="10")
mainframe.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

# API Key
api_key_label = ttk.Label(mainframe, text="API Key:")
api_key_label.grid(row=1, column=1, sticky=tk.W)
api_key_entry = ttk.Entry(mainframe, width=50)
api_key_entry.grid(row=1, column=2, sticky=(tk.W, tk.E))
api_key_entry.insert(0, default_api_key)  # Populate with default value from .env if available

# Project ID
project_id_label = ttk.Label(mainframe, text="Project ID:")
project_id_label.grid(row=2, column=1, sticky=tk.W)
project_id_entry = ttk.Entry(mainframe, width=50)
project_id_entry.grid(row=2, column=2, sticky=(tk.W, tk.E))
project_id_entry.insert(0, default_project_id)  # Populate with default value from .env if available

# Time Range
time_range_label = ttk.Label(mainframe, text="Time Range:")
time_range_label.grid(row=3, column=1, sticky=tk.W)
time_range_combo = ttk.Combobox(mainframe, width=47)
time_range_combo['values'] = ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "All Time"]
time_range_combo.grid(row=3, column=2, sticky=(tk.W, tk.E))
time_range_combo.current(0)  # Set default to "Today"

# Tag
tag_label = ttk.Label(mainframe, text="Tag:")
tag_label.grid(row=4, column=1, sticky=tk.W)
tag_entry = ttk.Entry(mainframe, width=50)
tag_entry.grid(row=4, column=2, sticky=(tk.W, tk.E))

# Fetch and Analyze Button
analyze_button = ttk.Button(mainframe, text="Fetch and Analyze", command=fetch_and_analyze)
analyze_button.grid(row=5, column=2, sticky=tk.W)

# Table to display results
columns = ("transcript", "session", "rating", "markdown")
tree = ttk.Treeview(root, columns=columns, show='headings', selectmode="browse")
tree.heading("transcript", text="Transcript")
tree.heading("session", text="Session")
tree.heading("rating", text="Rating")
tree.heading("markdown", text="Markdown")

# Populate the rating column with dropdown
def on_rating_change(event):
    selected_item = tree.selection()[0]
    new_rating = rating_combobox.get()
    tree.item(selected_item, values=(tree.item(selected_item, 'values')[0], tree.item(selected_item, 'values')[1], new_rating, tree.item(selected_item, 'values')[3]))

rating_combobox = ttk.Combobox(root, values=["Positive", "Negative", "Exclude"])
rating_combobox.bind("<<ComboboxSelected>>", on_rating_change)

tree.bind("<Double-1>", on_double_click)
tree.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

# Adjust the main window grid to handle resizing
root.grid_rowconfigure(6, weight=1)
root.grid_columnconfigure(0, weight=1)

root.mainloop()