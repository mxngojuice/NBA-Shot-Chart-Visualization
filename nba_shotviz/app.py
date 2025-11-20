"""
Streamlit app wrapper for the 3D NBA shot visualization.
- Player/Season are gated by a submit button to avoid extra API calls.
- All other controls auto-update the visualization using loaded data.
"""

import streamlit as st
import pandas as pd
from src.viz_3d import render_3d_trajectories
from src.filters import default_filter_state, filter_df
from src.data_io import get_available_players, get_available_seasons, load_shotlog, load_shotlog_multi, get_name_to_id

st.set_page_config(page_title="Player Development — 3D Shot Viz", layout="wide")

# Tab Headers

st.markdown(
    """
    <style>
    /* Make tab label text bigger and bolder */
    button[data-baseweb="tab"] div[data-testid="stMarkdownContainer"] p {
        font-size: 1.2rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("Filters")

available_players = get_available_players()
available_seasons = get_available_seasons()

# Session state to hold the last loaded dataset
if "loaded_key" not in st.session_state:
    st.session_state.loaded_key = None
    st.session_state.player_df = None
    st.session_state.league_df = None

    # initialize season range to latest season
    latest_idx = len(available_seasons) - 1
    default_season = available_seasons[latest_idx]
    st.session_state.season_min = default_season
    st.session_state.season_max = default_season


# ---- FORM: gate ONLY the expensive fetch inputs ----
with st.sidebar.form("dataset_picker"):
    sel_player = st.selectbox("Player", available_players, index=0)

    latest_idx = len(available_seasons) - 1
    default_season = available_seasons[latest_idx]

    season_min = st.selectbox(
        "Season (min)",
        available_seasons,
        index=available_seasons.index(st.session_state.season_min),
    )
    season_max = st.selectbox(
        "Season (max)",
        available_seasons,
        index=available_seasons.index(st.session_state.season_max),
    )

    submitted = st.form_submit_button("Update Visualization")

min_i = available_seasons.index(season_min)
max_i = available_seasons.index(season_max)
if min_i > max_i:
    st.error("🚫 Invalid season range: Season (min) must be earlier than Season (max).")
    st.stop()

selected_seasons = available_seasons[min_i : max_i + 1]

st.session_state.season_min = season_min
st.session_state.season_max = season_max

# ---- Auto-update controls (outside the form) ----
# quarters mxngo

sample  = st.sidebar.slider("Max shots to display", 100, 3000, 1000, step=100)

show_heatmap = st.sidebar.checkbox("Show Hot/Cold Zones (vs league)", value=False)
vlim = st.sidebar.slider("Heatmap scale (±FG% points)", 5, 25, 15, step=1) / 100.0

mm = st.sidebar.radio("Result", ["All", "Makes", "Misses"], index=0, horizontal=True) #mxngo

rg = st.sidebar.checkbox("Color arcs red/green", value=True)

ha = st.sidebar.radio("Venue", ["All", "Home", "Away"], index=0, horizontal=True,) #mxngo

st.sidebar.markdown("Quarters")

q1 = st.sidebar.checkbox("Q1", value=True)
q2 = st.sidebar.checkbox("Q2", value=True)
q3 = st.sidebar.checkbox("Q3", value=True)
q4 = st.sidebar.checkbox("Q4", value=True)
ot = st.sidebar.checkbox("OT", value=True)
periods = []
if q1: periods.append(1)
if q2: periods.append(2)
if q3: periods.append(3)
if q4: periods.append(4)
if ot: periods.append(5)

# clutch = st.sidebar.checkbox("Clutch shots only", value=False)


# ----------------------------
# Fetch data ONLY when the form is submitted with a new key
# ----------------------------
requested_key = (sel_player, season_min, season_max)

if submitted and requested_key != st.session_state.loaded_key:
    with st.spinner(f"Loading shot data for {sel_player} — {season_min} to {season_max}…"):
        if len(selected_seasons) > 1:
            player_df, league_df = load_shotlog_multi(sel_player, selected_seasons)
        else:
            player_df, league_df = load_shotlog(sel_player, selected_seasons[0])
        st.session_state.player_df = player_df
        st.session_state.league_df = league_df
        st.session_state.loaded_key = requested_key

# ----------------------------
# Create tabs (ALWAYS)
# ----------------------------
tabs = st.tabs(["Visualizer", "About", "Filters"])

# If no dataset has been loaded yet: show placeholder in Visualizer tab and stop
if st.session_state.player_df is None:
    with tabs[0]:
        st.title("Interactive NBA Shot Visualization Tool")
        st.info("Pick a player and season on the left, then click **Update Visualization** to see the chart.")
    with tabs[1]:
        st.header("About")
        st.write("Describe why we built this, UNC / 760, etc.")
    with tabs[2]:
        st.header("Filters")
        st.markdown(
            """
            Use the filters in the left sidebar to customize the visualization:
    
            **Max shots to display**  
            - Limits how many shots are drawn as 3D arcs.  
            - Helpful for speeding up rendering or focusing on a smaller sample.
    
            **Result (All / Makes / Misses)**  
            - **All**: shows every shot in the dataset.  
            - **Makes**: only made shots are included.  
            - **Misses**: only missed shots are included.
    
            **Venue (All / Home / Away)**  
            - Filter shots by where the game was played.  
            - *Home*: games where the selected player's team is listed as the home team.  
            - *Away*: games where they are listed as the road team.
    
            **Quarters (Q1, Q2, Q3, Q4, OT)**  
            - Toggle which periods to include.  
            - For example, turning on only **Q4** lets you focus on late-game shooting.
    
            **Shot Distance**  
            - Bucketed ranges in feet from the basket (e.g., 0–4 ft, 24–29 ft).  
            - Use this to isolate rim attacks, mid-range, or three-point shots.
    
            **Shot Type**  
            - Based on the `ACTION_TYPE` from the NBA play data  
              (e.g., *Jump Shot*, *Layup*, *Driving Dunk*).  
            - Choose **All** to combine every shot type.
    
            **Opponent**  
            - Filter shots by the opposing team.  
            - Use this to see how a player performs against a specific matchup.
    
            **Show Hot/Cold Zones (vs league)**  
            - When enabled, overlays a floor heatmap comparing the player's FG% to
              league-average FG% by zone.  
            - **Blue areas**: player is colder than league average.  
            - **Red areas**: player is hotter than league average.  
    
            **Heatmap scale (±FG% points)**  
            - Controls how “sensitive” the color scale is.  
            - Smaller values highlight subtle differences; larger values emphasize only
              big gaps from league average.
    
            **Color arcs red/green**  
            - When on, made shots are shown in green and misses in red.  
            - When off, all arcs are rendered in a neutral color (especially useful
              when a heatmap is displayed underneath).
            """
        )

    st.stop()

# ----------------------------
# At this point, we KNOW data is loaded
# ----------------------------
loaded_player, loaded_min, loaded_max = st.session_state.loaded_key
player_df = st.session_state.player_df
league_df = st.session_state.league_df

# Shot Distance mxngo
shot_dist_presets = {
    "All": (0, 100),
    "0–4 ft": (0, 4),
    "5–10 ft": (5, 10),
    "11–16 ft": (11, 16),
    "17–23 ft": (17, 23),
    "24–29 ft": (24, 29),
    "30+ ft": (30, 100),
}
sdist = st.sidebar.selectbox("Shot Distance", list(shot_dist_presets.keys()), index=0)

# Player headshot URL
pid = get_name_to_id().get(loaded_player)
headshot_url = None
if pid is not None:
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{pid}.png"

# Action Type dropdown
if "ACTION_TYPE" in player_df.columns:
    action_types = ["All"] + sorted(player_df["ACTION_TYPE"].dropna().unique().tolist())
else:
    action_types = ["All"]
stype = st.sidebar.selectbox("Shot Type", action_types, index=0)

# Opponent dropdown
if "OPPONENT" in player_df.columns:
    opponents = ["All"] + sorted(player_df["OPPONENT"].dropna().unique().tolist())
else:
    opponents = ["All"]
opp = st.sidebar.selectbox("Opponent", opponents, index=0)

# Build the filter state using the loaded dataset + live controls
state = default_filter_state()
state["player"]        = loaded_player
state["season"]        = (loaded_min, loaded_max)
state["periods"]       = periods
state["sample"]        = sample
state["result"]        = mm
state["venue"]         = ha
state["opponent"]      = opp
state["shot_distance"] = shot_dist_presets[sdist]
state["action_type"]   = stype

if show_heatmap and state["result"] != "All":
    st.error(
        "Hot/Cold Zones can only be computed when **Result = 'All'**.\n\n"
        "Switch Result back to **All**, or turn off **Show Hot/Cold Zones**."
    )
    st.stop()

df_filtered = filter_df(player_df, state)

# ----------------------------
# Tabs content
# ----------------------------
with tabs[0]:
    st.title("Interactive NBA Shot Visualization Tool")
    range_label = loaded_min if loaded_min == loaded_max else f"{loaded_min} — {loaded_max}"
    st.caption(f"{loaded_player} — {range_label}")

    col1, col2 = st.columns([0.75, 0.25])

    with col2:
        if headshot_url:
            st.image(headshot_url, width=130)

    with col1:
        if df_filtered.empty:
            st.info("No shots to display. Try different filters.")
        else:
            render_3d_trajectories(
                df_filtered,
                league_df=league_df,
                sample=state["sample"],
                overlay_heatmap=show_heatmap,
                vlim=vlim,
                force_make_miss_colors=rg,
            )

with tabs[1]:
    st.header("About")
    st.markdown("about text here.")

with tabs[2]:
    st.header("Filters")
    st.markdown("Explain what the filters mean and how to use them.")

with tabs[3]:
    st.header("Meet the Creators")
    st.markdown("Mxngo Juice and Dfulk wit it")
