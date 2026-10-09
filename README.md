# IT-Service-Management

This project implements a FastAPI-backed service request management API using the existing SQLite database schema in the repository. The application is designed to support a ticket lifecycle from request creation through assignment, workflow updates, resolution, closure, comments, history tracking, SLA reporting, and management summaries.

## Runtime and database

- Backend: Python + FastAPI
- Database: SQLite
- Schema source: `schema.sql` (logical design reused by the runtime application)
- Startup bootstrap: `app.py`

The runtime application does not recreate the schema in a separate migration system. It creates the SQLite tables on startup when needed and reuses the same data model for all endpoints.

## API overview

### Service requests

- `POST /api/v1/requests`
- `GET /api/v1/requests`
- `GET /api/v1/requests/{id}`
- `PATCH /api/v1/requests/{id}`

### Assignment and staffing

- `POST /api/v1/requests/{id}/assign`
- `GET /api/v1/users/agents`
- `GET /api/v1/reports/unassigned`

### Workflow lifecycle

- `POST /api/v1/requests/{id}/status`
- `POST /api/v1/requests/{id}/resolve`
- `POST /api/v1/requests/{id}/close`

### Comments and history

- `POST /api/v1/requests/{id}/comments`
- `GET /api/v1/requests/{id}/comments`
- `GET /api/v1/requests/{id}/history`
- `GET /api/v1/requests/{id}/status-history`
- `GET /api/v1/requests/{id}/assignment-history`

### Reference data

- `GET /api/v1/users`
- `GET /api/v1/categories`
- `GET /api/v1/priorities`
- `GET /api/v1/statuses`
- `GET /api/v1/sla-policies`

### SLA and reports

- `GET /api/v1/requests/{id}/sla`
- `GET /api/v1/reports/sla-breaches`
- `GET /api/v1/reports/summary`
- `GET /api/v1/reports/by-priority`
- `GET /api/v1/reports/by-category`
- `GET /api/v1/reports/by-status`
- `GET /api/v1/reports/by-assignee`

## Example request

Create a request:

```json
{
  "requester_id": 1,
  "category_id": 1,
  "priority_id": 2,
  "sla_policy_id": 1,
  "subject": "Laptop not charging",
  "description": "The business laptop is not charging after the docking station update.",
  "assigned_agent_id": 2
}
```

Status update:

```json
{
  "status": "In Progress",
  "reason": "Starting diagnosis"
}
```

Resolution:

```json
{
  "resolution_details": "Replaced the battery and verified charging works.",
  "resolved_by": 2
}
```

Close:

```json
{
  "closed_by": 2,
  "reason": "Ticket completed"
}
```

## Validation and workflow rules

- Requests must include subject, description, category, priority, and requester.
- Assignees must reference active IT agents or administrators.
- Closed requests cannot be modified in the ordinary update path.
- Resolution details are mandatory before a request can be marked resolved.
- Only resolved requests can be closed.
- Invalid status transitions are rejected with a 400 response.
- Concurrency checks use row-count validation so overlapping updates are not silently overwritten.
- SLA calculations are performed from the request creation timestamp and exclude on-hold periods if applicable.

## Running the app

Backend:

```bash
cd "/Users/ramireddyvishnuvardhanreddy/Desktop/IT Service Management"
./venv/bin/python app.py
```

Then open the FastAPI docs at:

- http://localhost:8000/docs

Frontend:

```bash
cd "/Users/ramireddyvishnuvardhanreddy/Desktop/IT Service Management"
./venv/bin/streamlit run frontend/app.py --server.port 8501
```

The frontend reads the API base URL from the `API_BASE_URL` environment variable or defaults to `http://127.0.0.1:8000/api/v1`.

## Testing

```bash
cd "/Users/ramireddyvishnuvardhanreddy/Desktop/IT Service Management"
./venv/bin/python -m pytest -q
```

The automated suite covers request lifecycle, status validation, invalid transitions, SLA behavior, assignment rules, reporting, and history tracking.

## Notes

- The project intentionally reuses the existing schema and database rather than creating duplicate tables.
- The application uses the SQLite database configured through `DATABASE_URL` or the default file-based database under the project directory.
- Manager-only reporting is guarded by request headers such as `X-User-Role` when present; the default test setup keeps the API open for local internal use without a token layer.
# IT-Service-Management
