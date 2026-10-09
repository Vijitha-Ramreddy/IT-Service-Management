import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import ApiClientError, get_api_client  # noqa: E402

st.set_page_config(page_title="Dashboard", layout="wide")

st.title("Dashboard")
api = get_api_client()

try:
    summary = api.get("/reports/summary")
    priority_report = api.get("/reports/by-priority")
    category_report = api.get("/reports/by-category")
    status_report = api.get("/reports/by-status")
    assignee_report = api.get("/reports/by-assignee")
    sla_breaches = api.get("/reports/sla-breaches")
    new_requests = api.get("/requests", params={"status": "New", "page": 1, "limit": 1})
    in_progress_requests = api.get("/requests", params={"status": "In Progress", "page": 1, "limit": 1})
except ApiClientError as exc:
    st.error(f"Unable to load dashboard data: {exc}")
    st.stop()

col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
with col1:
    st.metric("Open requests", summary.get("open", 0))
with col2:
    st.metric("New requests", new_requests.get("total", 0))
with col3:
    st.metric("In progress", in_progress_requests.get("total", 0))
with col4:
    st.metric("Resolved", summary.get("resolved", 0))
with col5:
    st.metric("Closed", summary.get("closed", 0))
with col6:
    st.metric("Unassigned", summary.get("unassigned", 0))
with col7:
    st.metric("SLA breached", summary.get("sla_breaches", 0))

priority_df = pd.DataFrame(priority_report.get("items", []))
category_df = pd.DataFrame(category_report.get("items", []))
status_df = pd.DataFrame(status_report.get("items", []))
assignee_df = pd.DataFrame(assignee_report.get("items", []))

left, right = st.columns(2)
with left:
    if not priority_df.empty:
        st.subheader("Requests by priority")
        st.bar_chart(priority_df.set_index("label")["count"])
    else:
        st.info("No priority data available.")

with right:
    if not category_df.empty:
        st.subheader("Requests by category")
        st.bar_chart(category_df.set_index("label")["count"])
    else:
        st.info("No category data available.")

left2, right2 = st.columns(2)
with left2:
    if not status_df.empty:
        st.subheader("Requests by status")
        st.bar_chart(status_df.set_index("label")["count"])
    else:
        st.info("No status data available.")

with right2:
    if not assignee_df.empty:
        st.subheader("Requests by assignee")
        st.bar_chart(assignee_df.set_index("label")["count"])
    else:
        st.info("No assignee data available.")

st.subheader("Critical and overdue requests")
critical = sla_breaches.get("items", [])
if critical:
    critical_df = pd.DataFrame(critical)
    display = critical_df[["id", "request_number", "subject", "status", "sla_state", "sla_deadline"]].copy()
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.info("No request is currently approaching or breaching an SLA target.")
