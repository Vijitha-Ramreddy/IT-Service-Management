import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import ApiClientError, get_api_client  # noqa: E402

st.set_page_config(page_title="Create Request", layout="wide")
st.title("Create Request")

api = get_api_client()

try:
    users = api.get("/users").get("items", [])
    categories = api.get("/categories").get("items", [])
    priorities = api.get("/priorities").get("items", [])
except ApiClientError as exc:
    st.error(f"Unable to load request metadata: {exc}")
    st.stop()

user_options = {user["id"]: f"{user['full_name']} ({user['role']})" for user in users}
category_options = {category["id"]: category["name"] for category in categories}
priority_options = {priority["id"]: f"{priority['name']} ({priority['sla_hours']}h SLA)" for priority in priorities}

with st.form("create_request_form"):
    st.caption("Development-only requester identity: this selector is used because the backend does not implement authentication in this local setup.")
    requester_id = st.selectbox("Requester", options=list(user_options.keys()), format_func=lambda value: user_options[value])
    subject = st.text_input("Subject", key="create_subject")
    description = st.text_area("Description", height=150, key="create_description")
    category_id = st.selectbox("Category", options=list(category_options.keys()), format_func=lambda value: category_options[value])
    priority_id = st.selectbox("Priority", options=list(priority_options.keys()), format_func=lambda value: priority_options[value])
    submitted = st.form_submit_button("Create request")

if submitted:
    if not subject.strip() or not description.strip():
        st.warning("Subject and description are required.")
    else:
        payload = {
            "requester_id": int(requester_id),
            "category_id": int(category_id),
            "priority_id": int(priority_id),
            "sla_policy_id": 1,
            "subject": subject.strip(),
            "description": description.strip(),
        }
        try:
            response = api.post("/requests", json=payload)
            st.success(f"Request created successfully: {response.get('request_number')}")
            st.session_state["create_subject"] = ""
            st.session_state["create_description"] = ""
            st.session_state["selected_request_id"] = response.get("id")
        except ApiClientError as exc:
            st.error(str(exc))
