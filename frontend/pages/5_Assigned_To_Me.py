import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import ApiClientError, get_api_client  # noqa: E402

st.set_page_config(page_title="Assigned to Me", layout="wide")
st.title("Assigned to Me")

api = get_api_client()

try:
    users = api.get("/users").get("items", [])
    agents = [user for user in users if user.get("role") in {"IT_AGENT", "ADMIN"}]
except ApiClientError as exc:
    st.error(f"Unable to load agents: {exc}")
    st.stop()

agent_ids = [user["id"] for user in agents]
agent_names = {user["id"]: f"{user['full_name']} ({user['role']})" for user in agents}
selected_agent_id = st.session_state.get("selected_agent_id") or agent_ids[0] if agent_ids else 1
selected_agent_id = st.selectbox("Development IT agent", options=agent_ids, format_func=lambda value: agent_names.get(value, str(value)))
st.session_state["selected_agent_id"] = int(selected_agent_id)

try:
    response = api.get("/requests", params={"assignee_id": int(selected_agent_id), "page": 1, "limit": 100})
    rows = response.get("items", [])
except ApiClientError as exc:
    st.error(f"Unable to load assigned requests: {exc}")
    st.stop()

if not rows:
    st.info("No requests are currently assigned to the selected agent.")
    st.stop()

df = pd.DataFrame(rows)
st.dataframe(df[["request_number", "subject", "status", "priority_id", "sla_state", "created_at"]], use_container_width=True, hide_index=True)

selected_request_id = st.selectbox("Choose a request to act on", options=[row["id"] for row in rows], format_func=lambda value: f"REQ-{value}")

st.subheader("Status update")
try:
    statuses = api.get("/statuses").get("items", [])
except ApiClientError as exc:
    st.error(f"Unable to load status data: {exc}")
    st.stop()

status_names = [item["name"] for item in statuses]
new_status = st.selectbox("New status", options=status_names)
if st.button("Update status"):
    try:
        api.post(f"/requests/{selected_request_id}/status", json={"status": new_status, "reason": "Updated from Streamlit."})
        st.success("Status updated successfully.")
    except ApiClientError as exc:
        st.error(str(exc))

st.subheader("Comment")
comment_message = st.text_area("Add a comment", height=120)
if st.button("Save comment"):
    if comment_message.strip():
        try:
            api.post(f"/requests/{selected_request_id}/comments", json={"author_id": int(selected_agent_id), "message": comment_message.strip()})
            st.success("Comment added.")
        except ApiClientError as exc:
            st.error(str(exc))
    else:
        st.warning("Comment text is required.")

st.subheader("Resolution")
resolution_details = st.text_area("Resolution details", height=120, key="agent_resolution")
if st.button("Resolve request"):
    if not resolution_details.strip():
        st.warning("Resolution details are required.")
    else:
        try:
            api.post(f"/requests/{selected_request_id}/resolve", json={"resolution_details": resolution_details.strip(), "resolved_by": int(selected_agent_id)})
            st.success("Request marked resolved.")
        except ApiClientError as exc:
            st.error(str(exc))

if st.button("Open selected request details"):
    st.session_state["selected_request_id"] = selected_request_id
    st.success(f"Request {selected_request_id} selected.")
