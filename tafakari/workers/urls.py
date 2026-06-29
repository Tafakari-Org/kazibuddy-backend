from django.urls import path
from .views import CreateWorkerProfileView, ViewWorkerProfileView, UpdateWorkerProfileView, ListWorkerProfilesView, TotalWorkersView
urlpatterns = [
    # Worker profile management endpoints
    path('profiles/', CreateWorkerProfileView.as_view(), name='create-worker-profile'),
    path('profiles/<uuid:id>/', ViewWorkerProfileView.as_view(), name='view-worker-profile'),
    path('profiles/<uuid:id>/update/', UpdateWorkerProfileView.as_view(), name='update-worker-profile'),
    path('profiles/list/', ListWorkerProfilesView.as_view(), name='list-worker-profiles'),
    path('total-workers/', TotalWorkersView.as_view(), name='total-workers'),
]