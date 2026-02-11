# Credit Approval System

Backend implementation for the internship assignment using Django REST Framework, PostgreSQL, Celery, and Redis.

## Overview

This service manages customer registration, loan eligibility checks, loan creation, and loan retrieval.

At startup, customer and loan data from `.xlsx` files are ingested through background workers.

## Tech Stack

- Python 3.11
- Django 4.2
- Django REST Framework
- PostgreSQL 15
- Celery 5
- Redis 7
- Docker + Docker Compose
- openpyxl

## Key Features

- Dockerized multi-service setup (`web`, `db`, `redis`, `celery`)
- Background Excel ingestion using Celery tasks
- Loan eligibility logic based on credit score and policy rules
- Compound-interest EMI calculation
- Assignment APIs available at root paths (`/register`, `/check-eligibility`, etc.)
- Compatibility routes also available under `/api/...`
- Root health endpoint: `GET /`

## Project Structure

```text
.
|-- credit_approval/
|   |-- settings.py
|   |-- urls.py
|   `-- celery.py
|-- loans/
|   |-- models.py
|   |-- serializers.py
|   |-- views.py
|   |-- tasks.py
|   |-- urls.py
|   `-- tests/
|-- customer_data.xlsx
|-- loan_data.xlsx
|-- docker-compose.yml
|-- Dockerfile
|-- entrypoint.sh
|-- manage.py
`-- requirements.txt
```

## Data Models

### Customer

- `customer_id` (PK)
- `first_name`
- `last_name`
- `age`
- `phone_number`
- `monthly_salary`
- `approved_limit`
- `current_debt`

### Loan

- `loan_id` (PK)
- `customer` (FK -> Customer)
- `loan_amount`
- `tenure`
- `interest_rate`
- `monthly_repayment`
- `emis_paid_on_time`
- `date_of_approval`
- `end_date`

## Startup and Ingestion Flow

When `docker compose up --build` runs:

1. PostgreSQL and Redis start.
2. Web container waits for PostgreSQL.
3. Django migrations run.
4. Celery chain is queued:
   - `ingest_customer_data`
   - `ingest_loan_data` (runs after customer ingestion)
5. Django development server starts on port `8000`.

### Notes

- Excel files are parsed by headers to support minor naming variants.
- Bulk inserts are idempotent (`ignore_conflicts=True`).
- PostgreSQL sequences are synchronized after ingestion to prevent PK collisions on future inserts.

## Running the Project

### Prerequisites

- Docker Desktop (or Docker Engine + Compose)

### Run

```bash
docker compose up --build
```

Service URL:

- `http://localhost:8000`

Health check:

```bash
curl http://localhost:8000/
```

Expected response:

```json
{"status":"ok","service":"credit-approval-system"}
```

### Stop

```bash
docker compose down
```

## API Endpoints

All endpoints are available in both forms:

- Root form: `/register`
- Prefixed form: `/api/register`

Base URL examples below use root form.

### 1) Register Customer

- Method: `POST`
- Path: `/register`

Request:

```json
{
  "first_name": "Ada",
  "last_name": "Lovelace",
  "age": 30,
  "monthly_income": 70000,
  "phone_number": 9876543210
}
```

Response (`201`):

```json
{
  "customer_id": 301,
  "name": "Ada Lovelace",
  "age": 30,
  "monthly_income": 70000,
  "approved_limit": 2500000,
  "phone_number": 9876543210
}
```

Rule:

- `approved_limit = round((36 * monthly_income) / 100000) * 100000`

### 2) Check Loan Eligibility

- Method: `POST`
- Path: `/check-eligibility`

Request:

```json
{
  "customer_id": 1,
  "loan_amount": 100000,
  "interest_rate": 10,
  "tenure": 12
}
```

Response (`200`):

```json
{
  "customer_id": 1,
  "approval": true,
  "interest_rate": 10.0,
  "corrected_interest_rate": 12.0,
  "tenure": 12,
  "monthly_installment": 8884.88
}
```

### 3) Create Loan

- Method: `POST`
- Path: `/create-loan`

Request:

```json
{
  "customer_id": 1,
  "loan_amount": 100000,
  "interest_rate": 14,
  "tenure": 12
}
```

Approved response (`201`):

```json
{
  "loan_id": 9998,
  "customer_id": 1,
  "loan_approved": true,
  "message": "Loan approved.",
  "monthly_installment": 8982.58
}
```

Rejected response (`200`):

```json
{
  "loan_id": null,
  "customer_id": 1,
  "loan_approved": false,
  "message": "Credit score too low. Loan not approved.",
  "monthly_installment": 9000.0
}
```

### 4) View Loan by Loan ID

- Method: `GET`
- Path: `/view-loan/{loan_id}`

Response (`200`):

```json
{
  "loan_id": 9998,
  "customer": {
    "id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": 9876543210,
    "age": 31
  },
  "loan_amount": 100000.0,
  "interest_rate": 14.0,
  "monthly_installment": 8982.58,
  "tenure": 12
}
```

### 5) View Current Loans by Customer ID

- Method: `GET`
- Path: `/view-loans/{customer_id}`

Response (`200`):

```json
[
  {
    "loan_id": 9998,
    "loan_amount": 100000.0,
    "interest_rate": 14.0,
    "monthly_installment": 8982.58,
    "repayments_left": 12
  }
]
```

## Credit and EMI Logic

### EMI Formula

The monthly installment uses the standard compound-interest EMI formula:

- `r = annual_interest_rate / (12 * 100)`
- `EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)`

### Credit Scoring Inputs

- Past loans paid on time
- Number of loans taken
- Loan activity in current year
- Approved loan volume
- If current loan amount sum exceeds approved limit, credit score is `0`

### Eligibility Policy

- `credit_score > 50`: approve
- `30 < credit_score <= 50`: approve with minimum interest `12%`
- `10 < credit_score <= 30`: approve with minimum interest `16%`
- `credit_score <= 10`: reject
- If sum of current EMIs is greater than `50%` of monthly salary: reject

## Testing

Run test suite inside Docker:

```bash
docker compose run --rm --entrypoint python web manage.py test -v 2 --noinput
```

Current tests cover:

- Root health endpoint
- Root route availability for `/register`
- Eligibility EMI-threshold behavior
- Excel ingestion support for `current_debt`
- Sequence synchronization after ingestion for customer and loan IDs

## Troubleshooting

- `404 /check-eligibilty`: endpoint typo. Use `/check-eligibility`.
- `405` on `/register` or `/check-eligibility` in browser: these endpoints require `POST`, not `GET`.
- `404 /`: check container is rebuilt with latest code (`docker compose up --build`).
- Port conflicts: make sure local ports `8000`, `5432`, `6379` are free.

## Submission Checklist

- Project runs with one command: `docker compose up --build`
- PostgreSQL + background worker ingestion working
- Assignment endpoints implemented
- Repository pushed to GitHub
