import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import ApiClientError, get_api_client  # noqa: E402

st.set_page_config(page_title="My Requests", layout="wide")
st.title("My Requests")

api = get_api_client()

try:
    users = api.get("/users").get("items", [])
except ApiClientError as exc:
    st.error(f"Unable to load user list: {exc}")
    st.stop()

user_options = {user["id"]: f"{user['full_name']} ({user['role']})" for user in users}
selected_requester_id = st.session_state.get("selected_requester_id") or next(iter(user_options), 1)
selected_requester_id = st.selectbox("Requester", list(user_options.keys()), format_func=lambda value: user_options[value], index=list(user_options.keys()).index(selected_requester_id) if selected_requester_id in user_options else 0)

st.session_state["selected_requester_id"] = int(selected_requester_id)

try:
    response = api.get("/requests", params={"requester_id": int(selected_requester_id), "page": 1, "limit": 100})
    rows = response.get("items", [])
except ApiClientError as exc:
    st.error(f"Unable to load requests for requester {selected_requester_id}: {exc}")
    st.stop()

if rows:
    df = pd.DataFrame(rows)
    display = df[["request_number", "subject", "priority_id", "status", "assigned_agent_id", "created_at", "sla_state"]].copy()
    st.dataframe(display, use_container_width=True, hide_index=True)
    request_id = st.selectbox("Open a request for details", options=[row["id"] for row in rows], format_func=lambda value: f"REQ-{value}")
    if st.button("View details"):
        st.session_state["selected_request_id"] = request_id
        st.success(f"Selected request {request_id}.")
else:
    st.info("No requests have been created for the selected requester yet.")
