# MRIT 3.O Manufacturing Workspace

MRIT 3.O brings the machine manual assistant, visual quality inspection, and Round 3 quality incidents into one Django website.

## Start the website

From this folder, run:

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. The home page is the manual assistant. Choose **Visual Quality Inspection** in the sidebar to open the quality dashboard, or visit `/quality/` directly.

The quality area includes single and batch inspections, history, supervisor reviews, products, and model metrics. The **Incidents** section lets an Engineer create one cited quality incident from their own completed Defective inspection; a Supervisor can review it with a required comment. Both areas use the same MRIT account session.

Round 3 uses `product_sop_mapping.csv` and the two required P-PLATE01 PDFs in `SOPs/`. Retrieval is restricted to Q-PLATE-01 and Q-PLATE-02. If the mapping or either required file is unavailable, the incident is still saved with **Insufficient** evidence and **Manual review required**, without suggested actions.

Incident API routes are `GET/POST /api/incidents`, `GET /api/incidents/<incident-id>`, and `PUT /api/incidents/<incident-id>/review`. Engineers can create and read only their own incidents; Supervisors can read all incidents and review them.

## Demo sign-in

Use the seeded accounts:

- `admin` / `Admin@123`
- `engineer` / `Engineer@123`
- `supervisor` / `Supervisor@123`

## First-time setup

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_data
```

Image uploads use the included demonstration classifier. Batch jobs use Celery and Redis when available and fall back to synchronous processing if no worker is connected.

# REPUAL
