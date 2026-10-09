import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import ApiClientError, get_api_client  # noqa: E402

st.set_page_config(page_title="All Requests", layout="wide")
st.title("All Requests")

api = get_api_client()

try:
    statuses = api.get("/statuses").get("items", [])
    priorities = api.get("/priorities").get("items", [])
    categories = api.get("/categories").get("items", [])
    users = api.get("/users").get("items", [])
except ApiClientError as exc:
    st.error(f"Unable to load filters: {exc}")
    st.stop()

status_options = ["All"] + [item["name"] for item in statuses]
priority_options = ["All"] + [item["name"] for item in priorities]
category_options = ["All"] + [item["name"] for item in categories]
assignee_options = ["All"] + [f"{item['id']} - {item['full_name']}" for item in users]

with st.sidebar:
    st.subheader("Filters")
    request_number_filter = st.text_input("Request number contains")
    status_filter = st.selectbox("Status", status_options)
    priority_filter = st.selectbox("Priority", priority_options)
    category_filter = st.selectbox("Category", category_options)
    assignee_filter = st.selectbox("Assignee", assignee_options)
    unassigned_only = st.checkbox("Unassigned only")
    sla_state_filter = st.selectbox("SLA state", ["All", "WITHIN_SLA", "APPROACHING_BREACH", "BREACHED"])
    start_date = st.date_input("Created from", value=date.today())
    end_date = st.date_input("Created to", value=date.today())
    limit = st.number_input("Page size", min_value=5, max_value=100, value=20, step=5)
    page = st.number_input("Page", min_value=1, value=1, step=1)

params: dict[str, str | int] = {"page": int(page), "limit": int(limit)}
if request_number_filter:
    params["request_number"] = request_number_filter
if status_filter != "All":
    params["status"] = status_filter
if priority_filter != "All":
    priority_id = next((item["id"] for item in priorities if item["name"] == priority_filter), None)
    if priority_id is not None:
        params["priority_id"] = priority_id
if category_filter != "All":
    category_id = next((item["id"] for item in categories if item["name"] == category_filter), None)
    if category_id is not None:
        params["category_id"] = category_id
if assignee_filter != "All":
    assignee_id = assignee_filter.split(" - ", 1)[0]
    params["assignee_id"] = int(assignee_id)
if sla_state_filter != "All":
    params["sla_state"] = sla_state_filter
if start_date:
    params["start_date"] = start_date.isoformat()
if end_date:
    params["end_date"] = end_date.isoformat()

try:
    response = api.get("/requests", params=params)
    rows = response.get("items", [])
    if unassigned_only:
        rows = [row for row in rows if row.get("assigned_agent_id") is None]
except ApiClientError as exc:
    st.error(f"Unable to load requests: {exc}")
    st.stop()

if rows:
    df = pd.DataFrame(rows)
    if "status" not in df.columns:
        df["status"] = "Unknown"
    df["created_at"] = df.get("created_at", "").map(lambda value: str(value)[:19] if value else "")
    df["request_url"] = df["id"].map(lambda request_id: f"/Request_Details?request_id={request_id}")
    st.dataframe(df[["request_number", "subject", "status", "priority_id", "assigned_agent_id", "created_at", "sla_state"]], use_container_width=True, hide_index=True)
else:
    st.info("No requests matched the current filters.")

if rows:
    selected_id = st.selectbox("Open request details", options=[row["id"] for row in rows], format_func=lambda request_id: f"REQ-{request_id}")
    if st.button("View selected request"):
        st.session_state["selected_request_id"] = selected_id
        st.success(f"Selected request {selected_id}.")
