import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import get_api_client  # noqa: E402

st.set_page_config(page_title="IT Service Management", layout="wide")

st.title("IT Service Management")
st.caption("Internal service desk dashboard")

api = get_api_client()

with st.sidebar:
    st.header("Development identity")
    users = []
    try:
        users = api.get("/users").get("items", [])
    except Exception:  # pragma: no cover - error path handled below
        users = []
    if users:
        user_map = {str(user["id"]): user["full_name"] for user in users}
        user_ids = [int(user["id"]) for user in users]
        selected_uid = st.session_state.get("selected_requester_id")
        if selected_uid not in user_ids:
            selected_uid = user_ids[0] if user_ids else 1
        selected_uid = st.selectbox(
            "Requester / operator",
            options=user_ids,
            index=user_ids.index(selected_uid) if selected_uid in user_ids else 0,
            format_func=lambda uid: f"{uid} - {user_map.get(str(uid), 'Unknown')}",
            key="selected_requester_id",
        )
        st.caption("Development-only identity selector for local testing.")
    else:
        st.warning("Unable to load users from the backend.")

    st.markdown("---")
    st.header("Navigation")

st.subheader("Overview")
st.info(
    "Use the sidebar to move between the dashboard, request management, workflow actions, and reporting pages. "
    "The backend remains the source of truth for all workflow rules."
)

st.write(
    "This app connects to the FastAPI API at the configured base URL and uses the existing SQLite-backed request model "
    "without duplicating any server-side business logic."
)
