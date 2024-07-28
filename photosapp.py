from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import os
import json
import requests
from collections import defaultdict
from dateutil import parser
from config import SECRET_KEY, CLIENT_SECRETS_FILE

app = Flask(__name__)
app.secret_key = SECRET_KEY
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = CLIENT_SECRETS_FILE
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
REDIRECT_URI = 'http://localhost:5001/oauth2callback'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=REDIRECT_URI)
    
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    return redirect(url_for('photos'))

@app.route('/photos')
def photos():
    if 'credentials' not in session:
        return redirect('authorize')

    credentials = Credentials(**session['credentials'])
    headers = {
        'Authorization': f'Bearer {credentials.token}',
    }

    response = requests.get('https://photoslibrary.googleapis.com/v1/mediaItems?pageSize=100', headers=headers)

    if response.status_code == 200:
        items = response.json().get('mediaItems', [])
        grouped_photos = group_photos_by_date(items)
        session['credentials'] = credentials_to_dict(credentials)
        return render_template('photos.html', grouped_photos=grouped_photos)
    else:
        return f"An error occurred: {response.status_code} - {response.text}"

def group_photos_by_date(items):
    grouped = defaultdict(list)
    for item in items:
        date = parser.isoparse(item['mediaMetadata']['creationTime']).date()
        grouped[date].append(item)
    return dict(grouped)

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

@app.route('/load_more_photos', methods=['POST'])
def load_more_photos():
    if 'credentials' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    credentials = Credentials(**session['credentials'])
    headers = {
        'Authorization': f'Bearer {credentials.token}',
    }

    page_token = request.json.get('pageToken', '')
    url = f'https://photoslibrary.googleapis.com/v1/mediaItems?pageSize=100&pageToken={page_token}'
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        items = response.json().get('mediaItems', [])
        next_page_token = response.json().get('nextPageToken', '')
        return jsonify({'items': items, 'nextPageToken': next_page_token})
    else:
        return jsonify({'error': f"An error occurred: {response.status_code} - {response.text}"}), response.status_code

if __name__ == '__main__':
    app.run('localhost', 5001, debug=True)