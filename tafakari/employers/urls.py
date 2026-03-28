from django.urls import path
from .views import (
    CreateEmployerProfileView,
    RetrieveEmployerProfileView,
    UpdateEmployerProfileView,
    TotalEmployersView
)

urlpatterns = [
    path('employer-profiles/create/', CreateEmployerProfileView.as_view(), name='create-employer-profile'),
    path('employer-profiles/<uuid:id>/', RetrieveEmployerProfileView.as_view(), name='retrieve-employer-profile'),
    path('employer-profiles/<uuid:id>/update/', UpdateEmployerProfileView.as_view(), name='update-employer-profile'),
    path('employer-profiles/total/', TotalEmployersView.as_view(), name='total-employers'),
    
]
