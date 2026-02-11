from datetime import date

from django.db.models import Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Customer, Loan
from .serializers import (
    CheckEligibilityRequestSerializer,
    CreateLoanRequestSerializer,
    RegisterRequestSerializer,
)


def calculate_monthly_installment(principal, annual_rate, tenure_months):
    """Calculate EMI using compound interest formula."""
    if annual_rate == 0:
        return round(principal / tenure_months, 2)
    monthly_rate = annual_rate / (12 * 100)
    emi = (
        principal
        * monthly_rate
        * ((1 + monthly_rate) ** tenure_months)
        / (((1 + monthly_rate) ** tenure_months) - 1)
    )
    return round(emi, 2)


def calculate_credit_score(customer):
    """Calculate credit score (0-100) based on historical loan data."""
    loans = Loan.objects.filter(customer=customer)

    if not loans.exists():
        return 50

    # Component 1: Past loans paid on time (weight: 30)
    total_emis = sum(l.tenure for l in loans)
    emis_on_time = sum(l.emis_paid_on_time for l in loans)
    if total_emis > 0:
        on_time_score = (emis_on_time / total_emis) * 30
    else:
        on_time_score = 0

    # Component 2: Number of loans taken (weight: 20)
    num_loans = loans.count()
    if num_loans <= 3:
        num_loans_score = 20
    elif num_loans <= 6:
        num_loans_score = 15
    elif num_loans <= 10:
        num_loans_score = 10
    else:
        num_loans_score = 5

    # Component 3: Loan activity in current year (weight: 20)
    current_year = date.today().year
    current_year_loans = loans.filter(date_of_approval__year=current_year).count()
    if current_year_loans == 0:
        activity_score = 20
    elif current_year_loans <= 2:
        activity_score = 15
    elif current_year_loans <= 4:
        activity_score = 10
    else:
        activity_score = 5

    # Component 4: Loan approved volume (weight: 30)
    total_volume = loans.aggregate(total=Sum("loan_amount"))["total"] or 0
    if total_volume <= customer.approved_limit * 0.5:
        volume_score = 30
    elif total_volume <= customer.approved_limit:
        volume_score = 20
    elif total_volume <= customer.approved_limit * 1.5:
        volume_score = 10
    else:
        volume_score = 0

    # Component 5: If sum of current loans > approved limit, score = 0
    current_loans_sum = (
        loans.filter(end_date__gte=date.today()).aggregate(total=Sum("loan_amount"))[
            "total"
        ]
        or 0
    )

    if current_loans_sum > customer.approved_limit:
        return 0

    credit_score = on_time_score + num_loans_score + activity_score + volume_score
    return min(round(credit_score), 100)


def check_loan_eligibility(customer, loan_amount, interest_rate, tenure):
    """Check loan eligibility and return approval details."""
    credit_score = calculate_credit_score(customer)

    # Check if sum of current EMIs > 50% of monthly salary
    current_emis = (
        Loan.objects.filter(customer=customer, end_date__gte=date.today()).aggregate(
            total=Sum("monthly_repayment")
        )["total"]
        or 0
    )

    new_emi = calculate_monthly_installment(loan_amount, interest_rate, tenure)

    if current_emis > (customer.monthly_salary * 0.5):
        return {
            "approval": False,
            "interest_rate": interest_rate,
            "corrected_interest_rate": interest_rate,
            "monthly_installment": new_emi,
            "message": "Sum of current EMIs exceeds 50% of monthly salary.",
        }

    corrected_interest_rate = interest_rate
    approval = True

    if credit_score > 50:
        corrected_interest_rate = interest_rate
    elif 30 < credit_score <= 50:
        corrected_interest_rate = max(interest_rate, 12)
    elif 10 < credit_score <= 30:
        corrected_interest_rate = max(interest_rate, 16)
    else:
        approval = False

    if not approval:
        return {
            "approval": False,
            "interest_rate": interest_rate,
            "corrected_interest_rate": corrected_interest_rate,
            "monthly_installment": new_emi,
            "message": "Credit score too low. Loan not approved.",
        }

    # Recalculate EMI with corrected interest rate
    corrected_emi = calculate_monthly_installment(
        loan_amount, corrected_interest_rate, tenure
    )

    return {
        "approval": True,
        "interest_rate": interest_rate,
        "corrected_interest_rate": corrected_interest_rate,
        "monthly_installment": corrected_emi,
        "message": "Loan approved.",
    }


class RootHealthView(APIView):
    def get(self, request):
        return Response(
            {"status": "ok", "service": "credit-approval-system"},
            status=status.HTTP_200_OK,
        )


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        monthly_income = data["monthly_income"]
        approved_limit = 36 * monthly_income
        # Round to nearest lakh
        approved_limit = round(approved_limit / 100000) * 100000

        customer = Customer.objects.create(
            first_name=data["first_name"],
            last_name=data["last_name"],
            age=data["age"],
            phone_number=data["phone_number"],
            monthly_salary=monthly_income,
            approved_limit=approved_limit,
        )

        return Response(
            {
                "customer_id": customer.customer_id,
                "name": f"{customer.first_name} {customer.last_name}",
                "age": customer.age,
                "monthly_income": customer.monthly_salary,
                "approved_limit": customer.approved_limit,
                "phone_number": customer.phone_number,
            },
            status=status.HTTP_201_CREATED,
        )


class CheckEligibilityView(APIView):
    def post(self, request):
        serializer = CheckEligibilityRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            customer = Customer.objects.get(customer_id=data["customer_id"])
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer not found."}, status=status.HTTP_404_NOT_FOUND
            )

        result = check_loan_eligibility(
            customer, data["loan_amount"], data["interest_rate"], data["tenure"]
        )

        return Response(
            {
                "customer_id": data["customer_id"],
                "approval": result["approval"],
                "interest_rate": result["interest_rate"],
                "corrected_interest_rate": result["corrected_interest_rate"],
                "tenure": data["tenure"],
                "monthly_installment": result["monthly_installment"],
            },
            status=status.HTTP_200_OK,
        )


class CreateLoanView(APIView):
    def post(self, request):
        serializer = CreateLoanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            customer = Customer.objects.get(customer_id=data["customer_id"])
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer not found."}, status=status.HTTP_404_NOT_FOUND
            )

        result = check_loan_eligibility(
            customer, data["loan_amount"], data["interest_rate"], data["tenure"]
        )

        if not result["approval"]:
            return Response(
                {
                    "loan_id": None,
                    "customer_id": data["customer_id"],
                    "loan_approved": False,
                    "message": result["message"],
                    "monthly_installment": result["monthly_installment"],
                },
                status=status.HTTP_200_OK,
            )

        final_rate = result["corrected_interest_rate"]
        monthly_installment = calculate_monthly_installment(
            data["loan_amount"], final_rate, data["tenure"]
        )

        # Calculate end date
        today = date.today()
        end_month = today.month + data["tenure"]
        end_year = today.year + (end_month - 1) // 12
        end_month = (end_month - 1) % 12 + 1
        end_day = min(today.day, 28)

        loan = Loan.objects.create(
            customer=customer,
            loan_amount=data["loan_amount"],
            tenure=data["tenure"],
            interest_rate=final_rate,
            monthly_repayment=monthly_installment,
            emis_paid_on_time=0,
            date_of_approval=today,
            end_date=date(end_year, end_month, end_day),
        )

        current_debt = (
            Loan.objects.filter(
                customer=customer, end_date__gte=date.today()
            ).aggregate(total=Sum("loan_amount"))["total"]
            or 0
        )
        Customer.objects.filter(customer_id=customer.customer_id).update(
            current_debt=current_debt
        )

        return Response(
            {
                "loan_id": loan.loan_id,
                "customer_id": data["customer_id"],
                "loan_approved": True,
                "message": "Loan approved.",
                "monthly_installment": monthly_installment,
            },
            status=status.HTTP_201_CREATED,
        )


class ViewLoanView(APIView):
    def get(self, request, loan_id):
        try:
            loan = Loan.objects.select_related("customer").get(loan_id=loan_id)
        except Loan.DoesNotExist:
            return Response(
                {"error": "Loan not found."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "loan_id": loan.loan_id,
                "customer": {
                    "id": loan.customer.customer_id,
                    "first_name": loan.customer.first_name,
                    "last_name": loan.customer.last_name,
                    "phone_number": loan.customer.phone_number,
                    "age": loan.customer.age,
                },
                "loan_amount": loan.loan_amount,
                "interest_rate": loan.interest_rate,
                "monthly_installment": loan.monthly_repayment,
                "tenure": loan.tenure,
            },
            status=status.HTTP_200_OK,
        )


class ViewLoansView(APIView):
    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(customer_id=customer_id)
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer not found."}, status=status.HTTP_404_NOT_FOUND
            )

        loans = Loan.objects.filter(customer=customer, end_date__gte=date.today())

        response_data = []
        for loan in loans:
            emis_left = max(loan.tenure - loan.emis_paid_on_time, 0)
            response_data.append(
                {
                    "loan_id": loan.loan_id,
                    "loan_amount": loan.loan_amount,
                    "interest_rate": loan.interest_rate,
                    "monthly_installment": loan.monthly_repayment,
                    "repayments_left": emis_left,
                }
            )

        return Response(response_data, status=status.HTTP_200_OK)
