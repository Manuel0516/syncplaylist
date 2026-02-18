import os
import pickle
import spotipy
import re
import unicodedata
import json
import time
from spotipy.oauth2 import SpotifyOAuth
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from typing import List

# ------------------------------
# Configuración de Credenciales
# ------------------------------

# --- Spotify Credentials ---
SPOTIPY_CLIENT_ID = 'f13ce2eda2af449fbee7ee5474aba89a'  # Reemplaza con tu Client ID
SPOTIPY_CLIENT_SECRET = 'e094f5a7a2d64b5197879cfa68523487'  # Reemplaza con tu Client Secret
SPOTIPY_REDIRECT_URI = 'http://localhost:8888/callback'
SCOPE_SPOTIFY = "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"

# --- Google Credentials ---
SCOPES_GOOGLE = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]

# Archivo para almacenar tokens de Spotify
TOKEN_SPOTIFY = 'token_spotify.pickle'

# Archivo para almacenar tokens de Google
TOKEN_GOOGLE = 'token_google.pickle'

# ------------------------------
# IDs de Playlists
# ------------------------------

# ID de la playlist de YouTube Music
#TEST YOUTUBE_PLAYLIST_ID = 'PLhT2acRf2UtE35D6KWicEISw04ZNQ7U7U'
YOUTUBE_PLAYLIST_ID = 'PLhT2acRf2UtFJiKQyYrGqkUdR_ZLATnWv'

# ID de la playlist de Spotify
#TEST SPOTIFY_PLAYLIST_ID = '3npgmEMq8rshB2EjNAANws'
SPOTIFY_PLAYLIST_ID = '4sAkilogLRaZNz887SskXZ'


# ------------------------------
# Autenticación con Spotify
# ------------------------------

def authenticate_spotify():
    """Autentica al usuario con Spotify y retorna el objeto Spotipy."""
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE_SPOTIFY,
        cache_path=TOKEN_SPOTIFY
    ))
    return sp

# ------------------------------
# Autenticación con YouTube Music
# ------------------------------

def authenticate_youtube():
    """Autentica al usuario con YouTube Data API y retorna el servicio."""
    creds = None
    if os.path.exists(TOKEN_GOOGLE):
        with open(TOKEN_GOOGLE, 'rb') as token:
            creds = pickle.load(token)
    # Si no hay credenciales válidas, el usuario necesita iniciar sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES_GOOGLE)
            creds = flow.run_local_server(port=0)
        # Guarda las credenciales para la próxima ejecución
        with open(TOKEN_GOOGLE, 'wb') as token:
            pickle.dump(creds, token)
    service = build('youtube', 'v3', credentials=creds)
    return service

# ------------------------------
# Spotify Functions
# ------------------------------
def remove_accents(text):
    """Elimina los acentos del texto."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )



def get_spotify_playlist_tracks(sp, playlist_id):
    """Obtiene todas las pistas de una playlist de Spotify."""
    results = sp.playlist_tracks(playlist_id, limit=100)
    total_songs_spotify = results['total']
    list_songs_sp = []
    for song in results['items']:
        name = song['track']['name']
        artist = song['track']['artists'][0]['name']
        song_id = song['track']['id']
        # Limpiar el nombre de la canción
        name = remove_accents(name)
        list_songs_sp.append([name, artist, song_id])
    return list_songs_sp

def search_spotify_song_id(sp, song_name, artist_name):
    """Busca una canción en Spotify y retorna su ID."""
    query = f"track:{song_name} artist:{artist_name}"
    results = sp.search(q=query, type='track', limit=1)
    
    tracks = results.get('tracks', {}).get('items', [])
    if tracks:
        return tracks[0]['id']
    else:
        return None

def add_song_to_spotify(sp, playlist_id, song_id):
    if song_id == None:
        print("Wrong ID")
    else:
        sp.playlist_add_items(playlist_id, [song_id])

def save_spotify_songs_to_json(songs, filename='spotify_songs.json'):
    """Guarda una lista de canciones de Spotify en un archivo JSON sin duplicar títulos."""
    # Load existing data if the file exists
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                spotify_data = json.load(f)
            except json.JSONDecodeError:
                spotify_data = []
    else:
        spotify_data = []

    # Create a set of existing song titles for quick lookup
    existing_titles = {song['title'] for song in spotify_data}

    # Add new songs if their title is not in the existing set
    for song in songs:
        if song[0] not in existing_titles:
            spotify_data.append({
                "title": song[0],
                "artist": song[1],
                "id": song[2]
            })

    # Save the updated list to the file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(spotify_data, f, indent=4, ensure_ascii=False)
    print(f"Spotify songs updated and saved to {filename}")
    
# ------------------------------
# YouTube Functions
# ------------------------------

# Define common patterns to remove, like '- Topic', ' - Official', etc.
PATTERNS_TO_REMOVE: List[re.Pattern] = [
    re.compile(r'\s*[-–]\s*(Topic|Official|Music|VEVO|TV|Audio|Video|Channel|Live|HD|4K|Lyrics|Remastered|Extended|Cover|Karaoke|Instrumental|Soundtrack|Mix|Version|Compilation|Single|Full Album|AURORA)$', re.IGNORECASE),
    re.compile(r'\s*\(.*?\)$'),    # Matches any text in parentheses at the end, e.g., "(Live)"
    re.compile(r'\s*\[.*?\]$'),    # Matches any text in brackets at the end, e.g., "[Official Video]"
    re.compile(r'\s*SilVio RodrigueZ$', re.IGNORECASE)  # Specific pattern
]

APOSTROPHE_MAPPING = {
    '’': "'",  # Right Single Quotation Mark
    '‘': "'",  # Left Single Quotation Mark
    '´': "'",  # Acute Accent
    '`': "'",  # Grave Accent
    '‛': "'",  # Single High-Reversed-9 Quotation Mark
    '＇': "'",  # Fullwidth Apostrophe
    'ʻ': "'",  # ʻOkina
    'ʼ': "'",  # Modifier Letter Apostrophe
    'ʽ': "'",  # Modifier Letter Turned Comma
    'ʾ': "'",  # Modifier Letter Right Half Ring
    'ʿ': "'",  # Modifier Letter Left Half Ring
    'ˈ': "'",  # Modifier Letter Vertical Line
}

def remove_accents_2(text: str) -> str:
    """
    Remove accents (diacritics) from the input string.
    
    Args:
        text (str): The text from which to remove accents.
    
    Returns:
        str: The text without accents.
    """
    # Normalize the text to decompose characters into base characters and diacritics
    normalized_text = unicodedata.normalize('NFKD', text)
    # Filter out diacritic characters
    return ''.join([c for c in normalized_text if not unicodedata.combining(c)])

def normalize_apostrophes(text: str) -> str:
    """
    Replace various apostrophe-like characters with a standard apostrophe.
    
    Args:
        text (str): The text to normalize.
    
    Returns:
        str: The text with normalized apostrophes.
    """
    for original, replacement in APOSTROPHE_MAPPING.items():
        text = text.replace(original, replacement)
    return text

def clean_song_name(name, artist):
    """Limpia el nombre de la canción eliminando el nombre del artista y patrones innecesarios."""
    # Remove artist name from song title (case-insensitive)
    # Using word boundaries to avoid partial matches
    artist_pattern = re.compile(re.escape(artist), re.IGNORECASE)
    name = artist_pattern.sub('', name)

    # Remove unwanted patterns from song name
    for pattern in PATTERNS_TO_REMOVE:
        name = pattern.sub('', name)

    # Remove leading/trailing whitespace and dashes
    name = name.strip(" - ").strip()
    name = name.replace(name.split(" - ", 1)[0] + " - ", "")

    return name

def get_youtube_playlist_songs(youtube, playlist_id):
    list_songs_yt = []

    request = youtube.playlistItems().list(
        part="snippet",
        playlistId=playlist_id
    )
    while request:
        response = request.execute()
        for song in response.get('items'):
            name = song['snippet']['title']
            artist = song['snippet']['videoOwnerChannelTitle']
            song_id = song['snippet']['resourceId']['videoId']
            # Remove artist name from song title
            name = re.sub(re.escape(artist), '', name, flags=re.IGNORECASE)
            
            # Remove unwanted patterns from song name
            for pattern in PATTERNS_TO_REMOVE:
                name = re.sub(pattern, '', name)
                artist = re.sub(pattern, '', artist)

            name = name.strip()
            artist = artist.strip()
            name = remove_accents(name)
            name = clean_song_name(name, artist)
            name = normalize_apostrophes(name)
            name = remove_accents_2(name)

            list_songs_yt.append([name, artist, song_id])
            
        request = youtube.playlistItems().list_next(request, response)
    return list_songs_yt

def search_youtube_song_id(youtube, song_name, artist_name):
    """Busca una canción en YouTube Music y retorna su ID."""
    query = f"{song_name} {artist_name}"
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=1
    )
    response = request.execute()
    
    items = response.get('items', [])
    if items:
        return items[0]['id']['videoId']
    else:
        return "No se encontró la canción."

def add_song_to_youtube(youtube, playlist_id, song_id):
    """Agrega una canción a una playlist de YouTube Music."""
    request = youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": song_id
                }
            }
        }
    )
    response = request.execute()

def save_youtube_songs_to_json(songs, filename='youtube_songs.json'):
    """Guarda una lista de canciones de YouTube en un archivo JSON sin duplicar títulos."""
    # Load existing data if the file exists
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                youtube_data = json.load(f)
            except json.JSONDecodeError:
                youtube_data = []
    else:
        youtube_data = []

    # Create a set of existing song titles for quick lookup
    existing_titles = {song['title'] for song in youtube_data}

    # Add new songs if their title is not in the existing set
    for song in songs:
        if song[0] not in existing_titles:
            youtube_data.append({
                "title": song[0],
                "artist": song[1],
                "id": song[2]
            })

    # Save the updated list to the file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(youtube_data, f, indent=4, ensure_ascii=False)
    print(f"YouTube songs updated and saved to {filename}")

# ------------------------------
# General Functions
# ------------------------------



def is_song_in_playlist(songs, song_name, artist_name):
    """Verifica si una canción está en una playlist."""
    song_name_lower = song_name.lower()
    artist_name_lower = artist_name.lower()
    
    return any(song_name_lower in song[0].lower() for song in songs)

def is_song_id_in_json(song_id, filename):
    """Verifica si un ID de canción está presente en el archivo JSON."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            songs = json.load(f)
            for song in songs:
                if song['id'] == song_id:
                    return True
            return False
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return False
    except json.JSONDecodeError:
        print(f"Error decoding JSON in {filename}.")
        return False
    
# ------------------------------
# Blacklist de Canciones
# ------------------------------
BLACKLIST_FILE = 'blacklist_songs.json'

def load_blacklist():
    """Carga la lista de canciones prohibidas desde un archivo JSON."""
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
            try:
                return {song['title'] for song in json.load(f)}
            except json.JSONDecodeError:
                return set()
    return set()

BLACKLIST = load_blacklist()


# ------------------------------
# Función Principal
# ------------------------------

def main():
    # Autenticación
    sp = authenticate_spotify()
    youtube = authenticate_youtube()

    # IDs de las playlists proporcionadas
    youtube_playlist_id = YOUTUBE_PLAYLIST_ID
    spotify_playlist_id = SPOTIFY_PLAYLIST_ID

    youtube_songs_list = get_youtube_playlist_songs(youtube, youtube_playlist_id)
    save_youtube_songs_to_json(youtube_songs_list)
    spotify_songs_list = get_spotify_playlist_tracks(sp, spotify_playlist_id)
    save_spotify_songs_to_json(spotify_songs_list)

    #First sync youtube with Spotify: 
    for i in range(len(youtube_songs_list)):
        #is in the spotify list this youtube song?
        if youtube_songs_list[i][0] in BLACKLIST:
            print(f"Skipping blacklisted song: {youtube_songs_list[i][0]}")
            continue
        if not(is_song_in_playlist(spotify_songs_list, youtube_songs_list[i][0], youtube_songs_list[i][1])):
            song_to_add_id = search_spotify_song_id(sp, youtube_songs_list[i][0], youtube_songs_list[i][1])
            if not(is_song_id_in_json(song_to_add_id, 'spotify_songs.json')):
                add_song_to_spotify(sp, spotify_playlist_id, song_to_add_id)
            print(f"YouTube song: {youtube_songs_list[i][0]}, added to Spotify")
    else:
        print("Spotify playlist synced with Youtube :) ")

    
    for i in range(len(spotify_songs_list)):
        #is in the youtube list this spotify song?
        if youtube_songs_list[i][0] in BLACKLIST:
            print(f"Skipping blacklisted song: {youtube_songs_list[i][0]}")
            continue
        if not(is_song_in_playlist(youtube_songs_list, spotify_songs_list[i][0], spotify_songs_list[i][1])):
            song_to_add_id = search_youtube_song_id(youtube, spotify_songs_list[i][0], spotify_songs_list[i][1])
            print(spotify_songs_list[i][0])
            if not(is_song_id_in_json(song_to_add_id, 'youtube_songs.json')):
                add_song_to_youtube(youtube, youtube_playlist_id, song_to_add_id)
            print(f"Spotify song: {spotify_songs_list[i][0]}, added to YouTube")
    else:
        print("YouTube playlist synced with Spotify :) ")

# ------------------------------
# Loop para ejecutar la sincronización diariamente
# ------------------------------
if __name__ == "__main__":
    while True:
        try: 
            main()
            print("Waiting 24 hours for the next sync...")
            time.sleep(86400)
            
        except Exception as e:
            print(f"Error encountered: {e}. Stopping sync.")
            break