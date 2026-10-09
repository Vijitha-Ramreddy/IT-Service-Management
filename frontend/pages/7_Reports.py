import sys
from datetime import date, timedelta
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
    use_date_filter = st.toggle("Apply date filter", value=False)
    if use_date_filter:
        start_date = st.date_input("Start date", value=date.today() - timedelta(days=30))
        end_date = st.date_input("End date", value=date.today())
        if start_date > end_date:
            st.warning("Start date must be on or before end date.")
            st.stop()
    else:
        start_date = None
        end_date = None
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

priority_items = priority.get("items", [])
category_items = category.get("items", [])
status_items = status.get("items", [])
assignee_items = assignee.get("items", [])
unassigned_items = unassigned.get("items", [])
breach_items = [item for item in breaches.get("items", []) if item.get("sla_state") == "BREACHED"]

report_tabs = st.tabs([
    f"Priority ({len(priority_items)})",
    f"Category ({len(category_items)})",
    f"Status ({len(status_items)})",
    f"Assignee ({len(assignee_items)})",
    f"Unassigned ({len(unassigned_items)})",
    f"SLA crossed ({len(breach_items)})",
])

with report_tabs[0]:
    df = pd.DataFrame(priority_items)
    if not df.empty:
        st.caption(f"{len(df)} priority records")
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No priority data for the selected date range.")

with report_tabs[1]:
    df = pd.DataFrame(category_items)
    if not df.empty:
        st.caption(f"{len(df)} category records")
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No category data for the selected date range.")

with report_tabs[2]:
    df = pd.DataFrame(status_items)
    if not df.empty:
        st.caption(f"{len(df)} status records")
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No status data for the selected date range.")

with report_tabs[3]:
    df = pd.DataFrame(assignee_items)
    if not df.empty:
        st.caption(f"{len(df)} assignee records")
        st.bar_chart(df.set_index("label")["count"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No assignee data for the selected date range.")

with report_tabs[4]:
    if unassigned_items:
        st.caption(f"{len(unassigned_items)} unassigned requests")
        st.dataframe(pd.DataFrame(unassigned_items)[["request_number", "subject", "status", "created_at"]], use_container_width=True, hide_index=True)
    else:
        st.info("No unassigned requests currently require attention.")

with report_tabs[5]:
    if breach_items:
        st.caption(f"{len(breach_items)} SLA-breached tickets")
        st.dataframe(
            pd.DataFrame(breach_items)[["request_number", "subject", "status", "sla_state", "sla_deadline"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tickets have crossed their SLA target.")
