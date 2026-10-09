import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import ApiClientError, get_api_client  # noqa: E402

st.set_page_config(page_title="Request Details", layout="wide")
st.title("Request Details")

api = get_api_client()

request_id = st.session_state.get("selected_request_id")
if request_id is None:
    request_id = st.number_input("Request ID", min_value=1, step=1)

if request_id is None:
    st.warning("Select a request from another page first.")
    st.stop()

try:
    request = api.get(f"/requests/{request_id}")
    history = api.get(f"/requests/{request_id}/history")
    comments = api.get(f"/requests/{request_id}/comments")
    agents = api.get("/users/agents").get("items", [])
    statuses = api.get("/statuses").get("items", [])
except ApiClientError as exc:
    st.error(f"Unable to load request details: {exc}")
    st.stop()

st.subheader(f"{request.get('request_number')} - {request.get('subject')}")

col1, col2, col3 = st.columns(3)
with col1:
    st.write(f"Requester: {request.get('requester_id')}")
    st.write(f"Category: {request.get('category_id')}")
    st.write(f"Priority: {request.get('priority_id')}")
    st.write(f"Status: {request.get('status')}")
with col2:
    st.write(f"Assigned agent: {request.get('assigned_agent_id')}")
    st.write(f"Created: {request.get('created_at')}")
    st.write(f"Updated: {request.get('updated_at')}")
    st.write(f"SLA state: {request.get('sla_state')}")
with col3:
    st.write(f"SLA deadline: {request.get('sla_deadline')}")
    st.write(f"Resolved at: {request.get('resolved_at') or 'Not resolved'}")
    st.write(f"Closed at: {request.get('closed_at') or 'Open'}")
    st.write(f"Within SLA: {request.get('within_sla')}")

st.write("Description")
st.write(request.get("description", ""))
if request.get("resolution_details"):
    st.write("Resolution details")
    st.write(request.get("resolution_details"))

st.markdown("---")
st.subheader("Assignment")
agent_names = {agent["id"]: f"{agent['full_name']} ({agent['role']})" for agent in agents}
selected_agent = st.selectbox("Assign or reassign", options=list(agent_names.keys()), format_func=lambda value: agent_names.get(value, str(value)))
if st.button("Assign"):
    try:
        response = api.post(f"/requests/{request_id}/assign", json={"assignee_id": int(selected_agent), "reason": "Assigned from Streamlit"})
        st.success(f"Assigned successfully: {response.get('assigned_agent_id')}")
        st.session_state["selected_request_id"] = request_id
    except ApiClientError as exc:
        st.error(str(exc))

st.markdown("---")
st.subheader("Status")
status_name = st.selectbox("Status", options=[item["name"] for item in statuses])
if st.button("Change status"):
    try:
        api.post(f"/requests/{request_id}/status", json={"status": status_name, "reason": "Status updated from Streamlit."})
        st.success("Status updated successfully.")
    except ApiClientError as exc:
        st.error(str(exc))

st.markdown("---")
st.subheader("Comments")
comment_text = st.text_area("Add comment", height=100, key=f"comment_{request_id}")
if st.button("Add comment"):
    try:
        api.post(f"/requests/{request_id}/comments", json={"author_id": int(st.session_state.get("selected_requester_id", 1)), "message": comment_text.strip()})
        st.success("Comment saved.")
    except ApiClientError as exc:
        st.error(str(exc))

comments_items = comments.get("items", [])
if comments_items:
    comments_df = pd.DataFrame(comments_items)
    st.dataframe(comments_df[["author_id", "message", "created_at"]], use_container_width=True, hide_index=True)
else:
    st.info("No comments for this request yet.")

st.markdown("---")
st.subheader("Resolution and closure")
resolution_text = st.text_area("Resolution details", height=100, key=f"resolve_{request_id}")
if st.button("Resolve request"):
    try:
        api.post(f"/requests/{request_id}/resolve", json={"resolution_details": resolution_text.strip(), "resolved_by": int(st.session_state.get("selected_requester_id", 1))})
        st.success("Request marked resolved.")
    except ApiClientError as exc:
        st.error(str(exc))

if st.button("Close request"):
    try:
        api.post(f"/requests/{request_id}/close", json={"closed_by": int(st.session_state.get("selected_requester_id", 1)), "reason": "Closed from Streamlit."})
        st.success("Request closed.")
    except ApiClientError as exc:
        st.error(str(exc))

st.markdown("---")
st.subheader("History")
history_items = history.get("items", [])
if history_items:
    st.dataframe(pd.DataFrame(history_items), use_container_width=True, hide_index=True)
else:
    st.info("No history has been recorded for this request yet.")
