# Assignment for Internship - Backend

## Credit Approval System

In this assignment you will be working on creating a credit approval system based on past data as well as future transactions. The goal of this assignment is to assess proficiency with the Python/Django stack, using background tasks as well as handling operations on databases.

---

## 1. Setup and Initialization

### a) Setup

- For this assignment please use **Django 4+** with **Django Rest Framework**.
- There is no requirement to make a frontend for the application.
- You need to build appropriate data models for the application.
- The entire application and all its dependencies should be dockerized.
- The application should use a **PostgreSQL DB**.

---

### b) Initialization

You are provided with a `customer_data.xlsx` which is a table of existing customers with the following attributes:

- customer_id
- first_name
- last_name
- phone_number
- monthly_salary
- approved_limit
- current_debt

You are also provided with `loan_data.xlsx` which is a table of past and existing loans by customers with the following attributes:

- customer_id
- loan_id
- loan_amount
- tenure
- interest_rate
- monthly_repayment (emi)
- EMIs_paid_on_time
- start_date
- end_date

Ingest the provided data into the initial system using background workers.

---

## 2. API

You need to build the following API endpoints with appropriate error handling and status codes.

Use **compound interest scheme** for calculation of monthly interest.

---

### `/register`

Add a new customer to the customer table with approved limit based on salary using the following relation:

approved_limit = 36 * monthly_salary


(Rounded to nearest lakh)

#### a) Request Body

| Field | Value |
|---|---|
| first_name | First Name of customer (string) |
| last_name | Last Name of customer (string) |
| age | Age of customer (int) |
| monthly_income | Monthly income of individual (int) |
| phone_number | Phone number (int) |

#### b) Response Body

| Field | Value |
|---|---|
| customer_id | Id of customer (int) |
| name | Name of customer (string) |
| age | Age of customer (int) |
| monthly_income | Monthly income of individual (int) |
| approved_limit | Approved credit limit (int) |
| phone_number | Phone number (int) |

---

### `/check-eligibility`

Check loan eligibility based on credit score of customer (out of 100) based on historical loan data from `loan_data.xlsx`.

Consider the following components while assigning a credit score:

1. Past loans paid on time  
2. Number of loans taken in past  
3. Loan activity in current year  
4. Loan approved volume  
5. If sum of current loans of customer > approved limit of customer → credit score = 0  

#### Loan Approval Rules

- If `credit_rating > 50` → approve loan
- If `50 > credit_rating > 30` → approve loans with interest rate > 12%
- If `30 > credit_rating > 10` → approve loans with interest rate > 16%
- If `credit_rating < 10` → do not approve loans
- If sum of all current EMIs > 50% of monthly salary → do not approve loans
- If the interest rate does not match the credit slab, return a corrected interest rate in response.

Example:
If credit slab requires 16% but request contains 8%, response should include:

corrected_interest_rate = 16%


#### a) Request Body

| Field | Value |
|---|---|
| customer_id | Id of customer (int) |
| loan_amount | Requested loan amount (float) |
| interest_rate | Interest rate on loan (float) |
| tenure | Tenure of loan (int) |

#### b) Response Body

| Field | Value |
|---|---|
| customer_id | Id of customer (int) |
| approval | Can loan be approved (bool) |
| interest_rate | Interest rate on loan (float) |
| corrected_interest_rate | Corrected interest rate based on credit rating (float) |
| tenure | Tenure of loan (int) |
| monthly_installment | Monthly installment to be paid as repayment (float) |

---

### `/create-loan`

Process a new loan based on eligibility.

#### a) Request Body

| Field | Value |
|---|---|
| customer_id | Id of customer (int) |
| loan_amount | Requested loan amount (float) |
| interest_rate | Interest rate on loan (float) |
| tenure | Tenure of loan (int) |

#### b) Response Body

| Field | Value |
|---|---|
| loan_id | Id of approved loan, null otherwise (int) |
| customer_id | Id of customer (int) |
| loan_approved | Is the loan approved (bool) |
| message | Appropriate message if loan is not approved (string) |
| monthly_installment | Monthly installment to be paid as repayment (float) |

---

### `/view-loan/{loan_id}`

View loan details and customer details.

#### Response Body

| Field | Value |
|---|---|
| loan_id | Id of approved loan (int) |
| customer | JSON containing id, first_name, last_name, phone_number, age (JSON) |
| loan_amount | Loan amount (float) |
| interest_rate | Interest rate of the approved loan (float) |
| monthly_installment | Monthly installment to be paid as repayment (float) |
| tenure | Tenure of loan (int) |

---

### `/view-loans/{customer_id}`

View all current loan details by customer id.

#### Response Body

(List of loan items. Each loan item contains:)

| Field | Value |
|---|---|
| loan_id | Id of approved loan (int) |
| loan_amount | Loan amount (float) |
| interest_rate | Interest rate of the approved loan (float) |
| monthly_installment | Monthly installment to be paid as repayment (float) |
| repayments_left | Number of EMIs left (int) |

---

## 3. General Guidelines

- Ensure code quality, organisation and segregation of responsibilities.
- Adding unit tests is not necessary but will be considered for bonus points.
- The assignment should be submitted within 36 hours.
- The entire application and all dependencies like DB should be dockerized and run from a single docker compose command.
- Submit the GitHub repository link.
