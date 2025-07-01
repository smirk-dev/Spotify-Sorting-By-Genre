import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import os

# --- Spotify Authentication ---
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id='6824ba14a5ef494da520885cc0146d19',
    client_secret='28f13bc3dc114d80abd415b5f5991a38',
    redirect_uri='https://spotifysorter.streamlit.app',
    scope='playlist-read-private playlist-modify-private playlist-modify-public'
))

# --- Genre Caching ---
CACHE_FILE = "genre_cache.json"
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        genre_cache = json.load(f)
else:
    genre_cache = {}

def save_genre_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(genre_cache, f)

# --- Spotify Helper Functions ---
def get_user_playlists():
    playlists = []
    results = sp.current_user_playlists()
    playlists.extend(results['items'])
    while results['next']:
        results = sp.next(results)
        playlists.extend(results['items'])
    return playlists

def get_playlist_tracks(playlist_id):
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    tracks.extend(results['items'])
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def get_artist_genres(artist_id):
    if artist_id in genre_cache:
        return genre_cache[artist_id]
    try:
        artist = sp.artist(artist_id)
        genres = artist['genres']
        genre_cache[artist_id] = genres
        return genres
    except Exception as e:
        return []

def sort_tracks_by_genre(tracks):
    track_genre_pairs = []
    for item in tracks:
        track = item['track']
        if not track or not track.get('artists'):
            continue
        artist_id = track['artists'][0]['id']
        genres = get_artist_genres(artist_id)
        main_genre = genres[0] if genres else 'unknown'
        track_genre_pairs.append((main_genre.lower(), track))
    track_genre_pairs.sort(key=lambda x: x[0])
    return [track for _, track in track_genre_pairs]

def create_sorted_playlist(name, sorted_tracks):
    user_id = sp.current_user()['id']
    new_playlist = sp.user_playlist_create(user_id, name, public=False)
    track_uris = [track['uri'] for track in sorted_tracks if track]
    for i in range(0, len(track_uris), 100):  # Chunking
        sp.playlist_add_items(new_playlist['id'], track_uris[i:i + 100])
    return new_playlist['external_urls']['spotify']

# --- Streamlit UI ---
st.title("🎶 Spotify Playlist Genre Sorter")

playlists = get_user_playlists()
playlist_names = [p['name'] for p in playlists]
selected = st.selectbox("Select a playlist to sort by genre:", playlist_names)

if st.button("Sort and Create New Playlist"):
    with st.spinner("Fetching tracks and sorting by genre..."):
        playlist_id = playlists[playlist_names.index(selected)]['id']
        tracks = get_playlist_tracks(playlist_id)
        sorted_tracks = sort_tracks_by_genre(tracks)
        playlist_url = create_sorted_playlist(f"{selected} (Sorted by Genre)", sorted_tracks)
        save_genre_cache()
    st.success(f"🎉 Sorted playlist created! [Open on Spotify]({playlist_url})")
