from datetime import date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum
from .models import Customer, Loan
from .serializers import (
    RegisterRequestSerializer,
    CheckEligibilityRequestSerializer,
    CreateLoanRequestSerializer,
)