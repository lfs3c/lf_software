# Budget Personal

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Chart.js](https://img.shields.io/badge/Charts-Chart.js-FF6384)
![License](https://img.shields.io/badge/License-Open%20Source-brightgreen)
![Status](https://img.shields.io/badge/Version-0.1-orange)

Self-hosted personal finance app to manage expenses, income, investments, goals, accounts/cards, and upcoming payments.

## About this project
- Open-source project created by [lfs3c](https://github.com/lfs3c).
- First full software project by the author.
- Feedback, constructive criticism, and suggestions are very welcome.

## Repository location
This app is located in this path:
- `https://github.com/lfs3c/lf_software/tree/main/personal_budget`

## Core features
- Multi-user authentication with admin controls.
- Profile page with initials and profile image.
- Dashboard charts:
  - Annual summary (Income, Expenses, Balance).
  - Expenses vs Income (current month).
  - Investments line chart (Acorns + Webull), month/year view.
  - `% by category` chart with editable and persistent colors.
- Goal planning:
  - Unique goal IDs (`OBJ-0001`, `OBJ-0002`, ...).
  - Auto monthly saving calculation.
  - Saved progress (%) tracking.
  - Goal deletion.
- Accounts/Cards CRUD.
- Transactions CRUD:
  - `expense`, `income`, `investment`, and `goal transfer`.
- Upcoming payments CRUD.
- Transactions history page with filters:
  - Account/Card (multi-select)
  - Type (multi-select)
  - Category
  - Exact date
  - Month
  - Date range
- Startup intro animation with branded images.

## Functional rules
- Investments are tracked separately and included in `% by category`.
- Goal transfer transactions are visual transfers to goals.
- Goal transfer transactions are not counted as normal expenses.
- Category legend is dynamically sorted from highest % to lowest %.

## Project structure
```text
lf_software/
  personal_budget/
    app/
      static/
        css/
        js/
        uploads/profiles/
      templates/
      config.py
      database.py
      main.py
      models.py
      init_db.py
    alembic/
    docker-compose.yml
    Dockerfile
    start.sh
    requirements.txt
```

## Quick start (Docker)
If you are new to Docker/Git, follow these exact steps:

1. Open terminal and go to the folder where you want to download the repo:
   - `cd /path/where/you/want/the/repo`
2. Clone the repository:
   - `git clone https://github.com/lfs3c/lf_software.git`
3. Enter the project app folder:
   - `cd lf_software/personal_budget`
4. (Recommended) create your local environment file:
   - `cp .env.example .env`
5. (Optional) if you want a port different from `3200`, set it now in `.env` before first start:
   - `APP_PORT=8080`
6. Build and start:
   - `docker compose up -d --build`
7. Check containers:
   - `docker compose ps`
8. Open in browser:
   - Default: `http://localhost:3200`
   - If you changed `APP_PORT`: `http://localhost:YOUR_PORT`

If it does not open, check logs:
- `docker compose logs -f web`

## Change default port (3200)
You can change only environment values (no source code edits required).

How it works:
- Internal app port (inside container): `3100`
- Public host port (your machine): `APP_PORT` (default `3200`)

### Temporary change (single run)
- `APP_PORT=8080 docker compose up -d --build`

### Permanent change (recommended)
1. Ensure `.env` exists:
   - `cp .env.example .env`
2. Set your preferred port:
   - `APP_PORT=8080`
3. Apply the change:
   - If first run: `docker compose up -d --build`
   - If already running:
     - `docker compose down`
     - `docker compose up -d --build`
4. Access:
   - `http://localhost:8080`

## First login and clean start
- The first registered user is automatically created as admin.
- This public version starts clean (no personal cards, transactions, goals, or investments preloaded).

## Common commands
- Start: `docker compose up -d`
- Stop: `docker compose down`
- Rebuild: `docker compose up -d --build`
- Logs: `docker compose logs -f web`

## Notes for contributors
- Main configuration files:
  - `docker-compose.yml`
  - `.env.example`
  - `app/config.py`
- YAML and startup settings include comments to simplify customization.

## License
This project is open source. Use, study, modify, and improve it.
