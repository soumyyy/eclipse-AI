# import requests
# import json

# # Load credentials from the saved file
# with open('credentials.json', 'r') as token_file:
#     credentials_dict = json.load(token_file)

# access_token = credentials_dict['token']

# headers = {
#     'Authorization': f'Bearer {access_token}',
# }

# response = requests.get('https://photoslibrary.googleapis.com/v1/mediaItems?pageSize=10', headers=headers)

# if response.status_code == 200:
#     items = response.json().get('mediaItems', [])
#     photos = [item['baseUrl'] for item in items]
#     print("Photos:", photos)
# else:
#     print(f"An error occurred: {response.status_code} - {response.text}")
    
# import logging
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build
# import json

# # Enable logging
# logging.basicConfig(level=logging.DEBUG)

# # Load credentials from the saved file
# with open('credentials.json', 'r') as token_file:
#     credentials_dict = json.load(token_file)

# credentials = Credentials(**credentials_dict)
# print("Credentials loaded:", credentials_dict)

# try:
#     # Attempt to build the service
#     service = build('photoslibrary', 'v1', credentials=credentials)
#     print("Service built successfully")
#     # Make an API call
#     results = service.mediaItems().list(pageSize=10).execute()
#     items = results.get('mediaItems', [])
#     print("API Response:", items)

#     photos = [item['baseUrl'] for item in items]
#     print(photos)
# except Exception as e:
#     print(f"An error occurred: {e}")

#     curl -H "Authorization: Bearer ya29.a0AXooCgudOnxvveSih1vvynF7meV_o5JJe4FPiqIaqcYkKxXTWyR7bniGXJOpHI6q2t3qgYAJXTq2cPQL96WNc0_kHpGzD2ZrR1AXn9IHskBq1lycPi3qtyMpEgf6wsUR2sdJQdp-ujDi8d6GFgXPb9r2itGRwYDafgaCgYKATsSARMSFQHGX2Mi9jOj64x8SZP4MMsRL4_NGg0169" \
#      "https://photoslibrary.googleapis.com/v1/mediaItems?pageSize=10"

from flask import Flask, redirect, request
from google_auth_oauthlib.flow import Flow
import os
import json

app = Flask(__name__)

CLIENT_SECRETS_FILE = 'client_secret_303100921412-om16i2c8j2t4ug1lm8s15hms8adbhl3n.apps.googleusercontent.com.json'  # Update this path if needed
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
REDIRECT_URI = 'http://localhost:5001/oauth2callback'

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)

@app.route('/')
def index():
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    # Save the credentials to a file
    credentials_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    with open('credentials.json', 'w') as token_file:
        json.dump(credentials_data, token_file)

    return 'Authorization complete. You can close this tab.'

if __name__ == '__main__':
    app.run('localhost', 5001, debug=True)