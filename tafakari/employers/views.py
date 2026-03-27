from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import EmployerProfile
from .serializers import EmployerProfileSerializer
from utils.custom_error import error_response
from utils.custom_pagination import CustomPagination
from django.db import transaction


class CreateEmployerProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Check if an employer profile already exists for the user
        if EmployerProfile.objects.filter(user=request.user).exists():
            return error_response(
                message="Employer profile already exists for this user",
                errors={"error": "Duplicate profile found"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = EmployerProfileSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                # Upgrade user_type if they are already a worker
                if request.user.user_type == 'worker':
                    request.user.user_type = 'both'
                    request.user.save()
                
                serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return error_response(
            message="Invalid data",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )

class RetrieveEmployerProfileView(APIView):
    def get(self, request, id):
        try:
            employer = EmployerProfile.objects.get(user=id)
            serializer = EmployerProfileSerializer(employer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except EmployerProfile.DoesNotExist:
            return error_response(
                message="Employer profile not found",
                errors={"error": "No profile matches the given ID"},
                status_code=status.HTTP_404_NOT_FOUND
            )
        

class UpdateEmployerProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, id):
        try:
            employer = EmployerProfile.objects.get(id=id)
            if employer.user != request.user:
                return error_response(
                    message="You do not have permission to update this profile",
                    errors={"error": "Permission denied"},
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            serializer = EmployerProfileSerializer(employer, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return error_response(
                message="Invalid data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        except EmployerProfile.DoesNotExist:
            return error_response(
                message="Employer profile not found",
                errors={"error": "No profile matches the given ID"},
                status_code=status.HTTP_404_NOT_FOUND
            )  
        
#Total employers
class TotalEmployersView(APIView):
    def get(self, request):
        try:
            total_employers = EmployerProfile.objects.count()
            return Response({
                "message": "Total employers fetched successfully",
                "data": total_employers
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return error_response(
                message="Error fetching total employers",
                errors={"error": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
