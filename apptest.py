import os
import pyaudio
import threading
from queue import Queue
from google.cloud import speech, texttospeech
from pocketsphinx import LiveSpeech, get_model_path
import requests
import datetime
import yfinance as yf
import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import dateparser
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'client_secret_303100921412-s9il8etjmsfdokq6klmb511drifr2kob.apps.googleusercontent.com.json'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = 'electric-vault-422210-v1-6c6834f08664.json'

RATE, CHUNK = 16000, 512

audio_interface = pyaudio.PyAudio()
audio_stream = None
tts_queue = Queue()

listening = threading.Event()
speaking = threading.Event()
active_listening = False

awaiting_event_date = False
awaiting_event_time = False
event_name = ''
event_date = ''
event_time = ''

speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

wake_words = [
    ("jarvis", "1e-30"),
    ("friday", "1e-30"),
    ("som", "1e-20"),
    ("hello", "1e-50")
]

api_key = 'e461f1691cee65ec9d76bbbe19782a25'
TIMEZONE = 'Asia/Kolkata'

# Spotify
os.environ["SPOTIPY_CLIENT_ID"] = "fc14267db73a4147bf273c346e4c8de1"
os.environ["SPOTIPY_CLIENT_SECRET"] = "8e01ca88d16348f595540b5431b7b0c9"
os.environ["SPOTIPY_REDIRECT_URI"] = "http://localhost:8888/callback"
scope = "user-read-playback-state,user-modify-playback-state,streaming"
sp = Spotify(auth_manager=SpotifyOAuth(scope=scope))
laptop_device_id = '1c7dfad65289ab2e1f2848ddc9e83c02695cf02a'
awaiting_song_name = False

def detect_wake_words():
    model_path = get_model_path()
    kws_list_path = os.path.join(model_path, 'wake_words.kws')
    with open(kws_list_path, 'w') as kws_file:
        for word, threshold in wake_words:
            kws_file.write(f"{word} /{threshold}/\n")
    speech = LiveSpeech(
        hmm=os.path.join(r'/Users/soumya/Desktop/Projects/ECLIPSE/eclipse/lib/python3.12/site-packages/pocketsphinx/model/en-us', 'en-us'),
        dic=os.path.join(
            r'/Users/soumya/Desktop/Projects/ECLIPSE/eclipse/lib/python3.12/site-packages/pocketsphinx/model/en-us', 'cmudict-en-us.dict'),
        kws=kws_list_path
    )
    print("Wake me")
    for phrase in speech:
        if phrase.segments(detailed=True):
            tts_queue.put("Yes sir?")
            return True
    return False

def speak_text(text):
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Standard-C"
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
    response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    def play_audio(audio_content):
        speaking.set()
        listening.clear()
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True)
        stream.write(audio_content)
        stream.stop_stream()
        stream.close()
        p.terminate()
        speaking.clear()
        listening.set()
    threading.Thread(target=play_audio, args=(response.audio_content,), daemon=True).start()

def tts_worker():
    while True:
        text = tts_queue.get()
        if text:
            print(f"Assistant: {text}")
            speak_text(text)
        tts_queue.task_done()

def market_data():
    sensex = yf.Ticker("^BSESN")
    nifty = yf.Ticker("^NSEI")
    
    live_data_sensex = sensex.history(period="1d", interval="1m")
    live_data_nifty = nifty.history(period="1d", interval="1m")
    sensex_data = sensex.history(period='1d')
    nifty_data = nifty.history(period='1d')

    if len(sensex_data) < 1 or len(live_data_sensex) == 0:
        return "Insufficient data for Sensex."
    if len(nifty_data) < 1 or len(live_data_nifty) == 0:
        return "Insufficient data for Nifty."

    sensex_previous_close = sensex_data['Close'].iloc[0]
    nifty_previous_close = nifty_data['Close'].iloc[0]

    sensex_current_price = live_data_sensex['Close'].iloc[-1]
    nifty_current_price = live_data_nifty['Close'].iloc[-1]

    sensex_trend = "up" if sensex_current_price > sensex_previous_close else "down"
    nifty_trend = "up" if nifty_current_price > nifty_previous_close else "down"

    sensex_change = abs(sensex_current_price - sensex_previous_close)
    nifty_change = abs(nifty_current_price - nifty_previous_close)

    return (
        f"Sensex is {sensex_trend} by {int(sensex_change)} points at {int(sensex_current_price)} "
        f"and Nifty is {nifty_trend} by {int(nifty_change)} points at {int(nifty_current_price)}."
    )

def get_city():
    try:
        response = requests.get('https://ipinfo.io')
        data = response.json()
        city = data.get('city', 'Unknown')
        return city
    except requests.exceptions.RequestException as e:
        print(f"Error fetching location: {e}")
        return 'Unknown'
    
def respond_to_good_morning():
    url = f"http://api.openweathermap.org/data/2.5/weather?q={get_city()}&appid={api_key}&units=metric"
    response = requests.get(url)
    data = response.json()
    now = datetime.datetime.now()
    temperature = data['main']['temp']
    time, day, date = now.strftime("%H:%M"), now.strftime("%A"), now.strftime("%d %B")
    return (f"Good morning! It's {time} on {day}. "
            f"The temperature in {get_city()} is {temperature}°C.")

def authenticate_google_calendar():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token_file:
            token_file.write(creds.to_json())
    service = build('calendar', 'v3', credentials=creds)
    return service

calendar_service = authenticate_google_calendar()
current_year = datetime.datetime.now().year

def add_event_to_calendar(service, summary, start_datetime, end_datetime):
    """Add an event to the Google Calendar."""
    TIMEZONE = 'Asia/Kolkata' 
    event = {
        'summary': summary,
        'description': "Auto-generated event.",
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': TIMEZONE
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': TIMEZONE
        }
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get("htmlLink")


def list_calendar_events(service):
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    if not events:
        return 'No upcoming events found.'
    else:
        result = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            result.append(f"{start} - {event['summary']}")
        return '\n'.join(result)

calendar_service = authenticate_google_calendar()
current_year = datetime.datetime.now().year

def play_music(song_name, device_id):
    results = sp.search(q=song_name, limit=1, type='track')
    tracks = results.get('tracks', {}).get('items', [])
    if not tracks:
        print("Could you try again sir")
        return
    track_uri = tracks[0]['uri']
    sp.start_playback(device_id=device_id, uris=[track_uri])
    print(f"Playing: {tracks[0]['name']} by {tracks[0]['artists'][0]['name']} on your laptop.")

def process_commands():
    global active_listening, awaiting_event_date, awaiting_event_time, event_name, event_datetime, awaiting_song_name
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US",
        enable_automatic_punctuation=True
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)
    
    def request_generator():
        while listening.is_set():
            try:
                data = audio_stream.read(CHUNK, exception_on_overflow=False)
                if data:
                    yield speech.StreamingRecognizeRequest(audio_content=data)
            except IOError as e:
                print(f"Error reading audio stream: {e}")

    def ask_for_date_time():
        global awaiting_event_date
        awaiting_event_date = True
        tts_queue.put("What time sir?")
        print("In format '15 October 6 pm'")

    def parse_event_date_time(date_time_str):
        parsed_datetime = dateparser.parse(date_time_str)
        if not parsed_datetime:
            raise ValueError("Invalid date or time format.")

        now = datetime.datetime.now()
        if parsed_datetime.year == now.year:
            parsed_datetime = parsed_datetime.replace(year=now.year)
        end_datetime = parsed_datetime + datetime.timedelta(hours=1)
        return parsed_datetime, end_datetime

    responses = speech_client.streaming_recognize(config=streaming_config, requests=request_generator())
    try:
        for response in responses:
            for result in response.results:
                if result.alternatives and result.is_final:
                    transcript = result.alternatives[0].transcript.lower()
                    print(f"You: {transcript}")

                    if "good morning" in transcript:
                        tts_queue.put(respond_to_good_morning())
                    elif "market" in transcript:
                        tts_queue.put(market_data())
                    elif "show my calendar" in transcript:
                        events = list_calendar_events(calendar_service)
                        tts_queue.put(events)
                    elif "stop" in transcript:
                        active_listening = False
                        return False
                    elif "exit" in transcript:
                        tts_queue.put("Goodbye!")
                        exit(0)
                    elif ("music" in transcript or "beats" in transcript) and not awaiting_song_name:
                        tts_queue.put("What song, sir?")
                        awaiting_song_name = True
                    elif awaiting_song_name:
                        song_name = transcript
                        play_music(song_name, laptop_device_id)
                        awaiting_song_name = False
                    elif "pause" in transcript:
                        sp.pause_playback(device_id=laptop_device_id)
                        tts_queue.put("Music paused.")
                    elif ("play" in transcript or "resume" in transcript):
                        sp.start_playback(device_id=laptop_device_id)
                        tts_queue.put("Resuming music.")
                    elif "add" in transcript and "to calendar" in transcript and not awaiting_event_date:
                        event_name = transcript.split("add ", 1)[1].split(" to calendar", 1)[0]
                        ask_for_date_time()
                    elif awaiting_event_date:
                        try:
                            event_datetime, end_datetime = parse_event_date_time(transcript)
                            awaiting_event_date = False
                            # Add to Google Calendar
                            event_link = add_event_to_calendar(calendar_service, event_name, event_datetime, end_datetime)
                            tts_queue.put(f"Event '{event_name}' added")
                        except ValueError:
                            tts_queue.put("Could you try that again sir?")
                            print("In format '15 October 6 pm'")
    except google.api_core.exceptions.OutOfRange:
        tts_queue.put("Audio stream timed out. Please try again.")
        print("Audio stream timed out. Please try again.")
    return True

def initialize_audio_stream():
    global audio_stream
    audio_stream = audio_interface.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    listening.set()

def main():
    initialize_audio_stream()
    threading.Thread(target=tts_worker, daemon=True).start()
    global active_listening
    active_listening = detect_wake_words()
    while True:
        if active_listening:
            active_listening = process_commands()
        else:
            active_listening = detect_wake_words()

if __name__ == '__main__':
    main()