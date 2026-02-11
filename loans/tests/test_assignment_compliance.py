from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from loans.models import Customer, Loan
from loans.tasks import ingest_customer_data, ingest_loan_data
from loans.views import check_loan_eligibility


class AssignmentComplianceTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_root_health_endpoint_is_available(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["service"], "credit-approval-system")

    def test_register_is_available_at_root_path(self):
        payload = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "age": 30,
            "monthly_income": 70000,
            "phone_number": 9999999999,
        }

        response = self.client.post("/register", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertIn("customer_id", response.data)

    def test_eligibility_uses_current_emi_threshold(self):
        customer = Customer.objects.create(
            first_name="John",
            last_name="Doe",
            age=31,
            phone_number=1234567890,
            monthly_salary=100000,
            approved_limit=1500000,
        )

        Loan.objects.create(
            customer=customer,
            loan_amount=10000,
            tenure=12,
            interest_rate=12,
            monthly_repayment=49000,
            emis_paid_on_time=12,
            date_of_approval=date.today() - timedelta(days=60),
            end_date=date.today() + timedelta(days=300),
        )

        result = check_loan_eligibility(
            customer=customer,
            loan_amount=100000,
            interest_rate=16,
            tenure=24,
        )

        self.assertTrue(result["approval"])

    @patch("loans.tasks.load_workbook")
    def test_customer_ingest_supports_current_debt_column(self, mock_load_workbook):
        class FakeSheet:
            def iter_rows(self, values_only=True):
                return iter(
                    [
                        (
                            "Customer ID",
                            "First Name",
                            "Last Name",
                            "Age",
                            "Phone Number",
                            "Monthly Salary",
                            "Approved Limit",
                            "Current Debt",
                        ),
                        (501, "Jane", "Roe", 28, 9876543210, 50000, 1800000, 450000),
                    ]
                )

        class FakeWorkbook:
            active = FakeSheet()

        mock_load_workbook.return_value = FakeWorkbook()

        ingest_customer_data()

        customer = Customer.objects.get(customer_id=501)
        self.assertEqual(customer.current_debt, 450000)

    @patch("loans.tasks.load_workbook")
    def test_customer_ingest_syncs_customer_sequence(self, mock_load_workbook):
        class FakeSheet:
            def iter_rows(self, values_only=True):
                return iter(
                    [
                        (
                            "Customer ID",
                            "First Name",
                            "Last Name",
                            "Age",
                            "Phone Number",
                            "Monthly Salary",
                            "Approved Limit",
                        ),
                        (800, "Seed", "User", 25, 9999999998, 60000, 2200000),
                    ]
                )

        class FakeWorkbook:
            active = FakeSheet()

        mock_load_workbook.return_value = FakeWorkbook()

        ingest_customer_data()

        customer = Customer.objects.create(
            first_name="New",
            last_name="User",
            age=26,
            phone_number=9999999997,
            monthly_salary=61000,
            approved_limit=2200000,
        )
        self.assertGreater(customer.customer_id, 800)

    @patch("loans.tasks.load_workbook")
    def test_loan_ingest_syncs_loan_sequence(self, mock_load_workbook):
        customer = Customer.objects.create(
            customer_id=901,
            first_name="Cust",
            last_name="Seed",
            age=27,
            phone_number=9999999996,
            monthly_salary=75000,
            approved_limit=2500000,
        )

        class FakeSheet:
            def iter_rows(self, values_only=True):
                return iter(
                    [
                        (
                            "Customer ID",
                            "Loan ID",
                            "Loan Amount",
                            "Tenure",
                            "Interest Rate",
                            "Monthly payment",
                            "EMIs paid on Time",
                            "Date of Approval",
                            "End Date",
                        ),
                        (
                            901,
                            1700,
                            300000,
                            12,
                            12.5,
                            26715,
                            0,
                            date.today() - timedelta(days=1),
                            date.today() + timedelta(days=365),
                        ),
                    ]
                )

        class FakeWorkbook:
            active = FakeSheet()

        mock_load_workbook.return_value = FakeWorkbook()

        ingest_loan_data()

        loan = Loan.objects.create(
            customer=customer,
            loan_amount=50000,
            tenure=6,
            interest_rate=13.0,
            monthly_repayment=8600,
            emis_paid_on_time=0,
            date_of_approval=date.today(),
            end_date=date.today() + timedelta(days=180),
        )
        self.assertGreater(loan.loan_id, 1700)
