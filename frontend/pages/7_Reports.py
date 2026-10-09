import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import ApiClientError, get_api_client  # noqa: E402

st.set_page_config(page_title="Reports", layout="wide")
st.title("Reports")

api = get_api_client()

with st.sidebar:
    st.subheader("Report filters")
    start_date = st.date_input("Start date", value=date.today())
    end_date = st.date_input("End date", value=date.today())
    refresh = st.button("Refresh reports")

params = {}
if start_date:
    params["start_date"] = start_date.isoformat()
if end_date:
    params["end_date"] = end_date.isoformat()

try:
    summary = api.get("/reports/summary", params=params)
    priority = api.get("/reports/by-priority", params=params)
    category = api.get("/reports/by-category", params=params)
    status = api.get("/reports/by-status", params=params)
    assignee = api.get("/reports/by-assignee", params=params)
    unassigned = api.get("/reports/unassigned")
    breaches = api.get("/reports/sla-breaches")
except ApiClientError as exc:
    st.error(f"Unable to load reports: {exc}")
    st.stop()

st.metric("Total requests", summary.get("total", 0))
st.metric("SLA breaches", summary.get("sla_breaches", 0))

report_tabs = st.tabs(["Priority", "Category", "Status", "Assignee", "Unassigned", "SLA breaches"])

with report_tabs[0]:
    df = pd.DataFrame(priority.get("items", []))
    if not df.empty:
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No priority data for the selected date range.")

with report_tabs[1]:
    df = pd.DataFrame(category.get("items", []))
    if not df.empty:
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No category data for the selected date range.")

with report_tabs[2]:
    df = pd.DataFrame(status.get("items", []))
    if not df.empty:
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No status data for the selected date range.")

with report_tabs[3]:
    df = pd.DataFrame(assignee.get("items", []))
    if not df.empty:
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No assignee data for the selected date range.")

with report_tabs[4]:
    unassigned_items = unassigned.get("items", [])
    if unassigned_items:
        st.dataframe(pd.DataFrame(unassigned_items)[["request_number", "subject", "status", "created_at"]], use_container_width=True, hide_index=True)
    else:
        st.info("No unassigned requests currently require attention.")

with report_tabs[5]:
    breach_items = breaches.get("items", [])
    if breach_items:
        st.dataframe(pd.DataFrame(breach_items)[["request_number", "subject", "status", "sla_state", "sla_deadline"]], use_container_width=True, hide_index=True)
    else:
        st.info("No upcoming or missed SLA targets were found.")
