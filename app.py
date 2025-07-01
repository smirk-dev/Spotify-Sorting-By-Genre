import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import os
from dotenv import load_dotenv
import time
from collections import defaultdict

# Load environment variables
load_dotenv()

# --- App Configuration ---
st.set_page_config(
    page_title="Spotify Genre Sorter",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        background-color: #1DB954;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        border: none;
        font-weight: 500;
    }
    .stButton>button:hover {
        background-color: #1ed760;
        color: white;
    }
    .stSelectbox>div>div>select {
        padding: 0.5rem;
        border-radius: 8px;
    }
    .progress-bar {
        height: 10px;
        background-color: #e0e0e0;
        border-radius: 5px;
        margin: 10px 0;
    }
    .progress-fill {
        height: 100%;
        background-color: #1DB954;
        border-radius: 5px;
        transition: width 0.5s;
    }
    .track-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .genre-tag {
        display: inline-block;
        background-color: #1DB954;
        color: white;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 12px;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    .sidebar .sidebar-content {
        background-color: #f0f2f6;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Spotify Authentication ---
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
    st.error("Missing Spotify API credentials. Please check your environment variables.")
    st.stop()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope='playlist-read-private playlist-modify-private playlist-modify-public user-library-read',
    show_dialog=True
))

# Insert authentication check here
try:
    current_user = sp.current_user()
    st.success(f"Authenticated as: {current_user['display_name']}")
except Exception as e:
    st.error(f"Authentication failed: {e}")
    st.stop()

# --- Genre Caching ---
CACHE_FILE = "genre_cache.json"
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r") as f:
            genre_cache = json.load(f)
    except (json.JSONDecodeError, IOError):
        genre_cache = {}
else:
    genre_cache = {}

def save_genre_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(genre_cache, f)
    except IOError as e:
        st.warning(f"Couldn't save genre cache: {e}")

# --- Spotify Helper Functions ---
def get_user_playlists():
    try:
        playlists = []
        results = sp.current_user_playlists()
        playlists.extend(results['items'])
        while results['next']:
            results = sp.next(results)
            playlists.extend(results['items'])
        return sorted(playlists, key=lambda x: x['name'].lower())
    except Exception as e:
        st.error(f"Error fetching playlists: {e}")
        return []

def get_playlist_tracks(playlist_id):
    try:
        tracks = []
        results = sp.playlist_tracks(playlist_id)
        tracks.extend(results['items'])
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        return tracks
    except Exception as e:
        st.error(f"Error fetching tracks: {e}")
        return []

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

def analyze_playlist_genres(tracks):
    genre_distribution = defaultdict(int)
    genre_tracks = defaultdict(list)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, item in enumerate(tracks):
        if not item or not item.get('track'):
            continue
        track = item['track']
        if not track or not track.get('artists'):
            continue
        
        try:
            artist_id = track['artists'][0]['id']
            genres = get_artist_genres(artist_id)
            
            progress = (i + 1) / len(tracks)
            progress_bar.progress(progress)
            status_text.text(f"Analyzing track {i+1}/{len(tracks)}: {track.get('name', 'Unknown')}")
            
            if not genres:
                genres = ['unknown']
            
            for genre in genres:
                genre_distribution[genre] += 1
                genre_tracks[genre].append(track)
                
        except Exception as e:
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    return dict(genre_distribution), genre_tracks

def create_sorted_playlist(name, sorted_tracks):
    try:
        user_id = sp.current_user()['id']
        new_playlist = sp.user_playlist_create(
            user_id, 
            name, 
            public=False,
            description="Created with Spotify Genre Sorter"
        )
        
        track_uris = [track['uri'] for track in sorted_tracks if track and track.get('uri')]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Add tracks in batches of 100 (Spotify API limit)
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i + 100]
            sp.playlist_add_items(new_playlist['id'], batch)
            
            progress = min((i + 100) / len(track_uris), 1.0)
            progress_bar.progress(progress)
            status_text.text(f"Adding tracks {i+1}-{min(i+100, len(track_uris))}/{len(track_uris)}")
        
        progress_bar.empty()
        status_text.empty()
        
        return new_playlist['external_urls']['spotify']
    except Exception as e:
        st.error(f"Error creating playlist: {e}")
        return None

# --- Streamlit UI ---
st.title("🎵 Spotify Playlist Genre Sorter")
st.markdown("Organize your playlists by genre with just one click!")

# Sidebar for additional options
with st.sidebar:
    st.header("Settings")
    sort_option = st.radio(
        "Sort order:",
        ["A-Z", "Most common first"],
        index=0
    )
    show_details = st.checkbox("Show detailed genre analysis", True)
    st.markdown("---")
    st.markdown("### About")
    st.markdown("This app sorts your Spotify playlists by genre, creating a new playlist with tracks organized by their primary genre.")
    st.markdown("It uses Spotify's artist genre data to categorize each track.")

# Main content
try:
    playlists = get_user_playlists()
    if not playlists:
        st.warning("No playlists found or couldn't access your playlists.")
        st.stop()
        
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_playlist = st.selectbox(
            "Select a playlist to analyze:",
            playlists,
            format_func=lambda x: x['name'],
            help="Choose the playlist you want to sort by genre"
        )
        
    with col2:
        st.markdown("")
        st.markdown("")
        sort_button = st.button("✨ Sort by Genre")
    
    if selected_playlist and sort_button:
        st.markdown(f"## Analyzing: {selected_playlist['name']}")
        
        with st.expander("Playlist Info", expanded=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("Tracks", selected_playlist['tracks']['total'])
            col2.metric("Owner", selected_playlist['owner']['display_name'])
            col3.metric("Public", "Yes" if selected_playlist['public'] else "No")
            
            if selected_playlist['images']:
                st.image(selected_playlist['images'][0]['url'], width=200)
        
        tracks = get_playlist_tracks(selected_playlist['id'])
        
        if not tracks:
            st.error("No tracks found in this playlist.")
            st.stop()
        
        with st.spinner("Analyzing genres..."):
            genre_distribution, genre_tracks = analyze_playlist_genres(tracks)
        
        if show_details:
            st.markdown("## Genre Distribution")
            
            # Sort genres based on user preference
            if sort_option == "Most common first":
                sorted_genres = sorted(genre_distribution.items(), key=lambda x: x[1], reverse=True)
            else:
                sorted_genres = sorted(genre_distribution.items(), key=lambda x: x[0].lower())
            
            # Show genre distribution
            for genre, count in sorted_genres:
                with st.expander(f"{genre.title()} ({count} tracks)"):
                    for track in genre_tracks[genre]:
                        artists = ", ".join([artist['name'] for artist in track['artists']])
                        st.markdown(f"""
                        <div class="track-card">
                            <strong>{track['name']}</strong><br>
                            <small>{artists}</small>
                        </div>
                        """, unsafe_allow_html=True)
        
        # Create sorted playlist
        st.markdown("## Create Sorted Playlist")
        new_playlist_name = st.text_input(
            "New playlist name:", 
            value=f"{selected_playlist['name']} (Genre Sorted)",
            max_chars=100
        )
        
        if st.button("Create Sorted Playlist"):
            # Flatten tracks in genre order
            if sort_option == "Most common first":
                sorted_genres = sorted(genre_distribution.items(), key=lambda x: x[1], reverse=True)
            else:
                sorted_genres = sorted(genre_distribution.items(), key=lambda x: x[0].lower())
            
            sorted_tracks = []
            for genre, _ in sorted_genres:
                sorted_tracks.extend(genre_tracks[genre])
            
            with st.spinner(f"Creating playlist '{new_playlist_name}'..."):
                playlist_url = create_sorted_playlist(new_playlist_name, sorted_tracks)
                save_genre_cache()
                
                if playlist_url:
                    st.success("### Playlist created successfully!")
                    st.markdown(f"[Open in Spotify]({playlist_url})")
                    st.balloons()
                else:
                    st.error("Failed to create playlist.")
                
except Exception as e:
    st.error(f"An unexpected error occurred: {e}")
