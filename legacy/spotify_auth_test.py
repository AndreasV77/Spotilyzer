import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

def main():
    load_dotenv()
    scope = "user-read-private"
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=scope,
        open_browser=True
    ))
    me = sp.me()
    print(f"Authenticated as: {me.get('display_name') or me['id']}")
    print("Scopes OK. Web API calls ready.")

if __name__ == '__main__':
    main()
