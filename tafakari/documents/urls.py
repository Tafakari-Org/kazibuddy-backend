from django.urls import path
from .views import MyDocumentsView, MyDocumentDetailView

urlpatterns = [
    path('mine/', MyDocumentsView.as_view(), name='my-documents'),
    path('mine/<uuid:document_id>/', MyDocumentDetailView.as_view(), name='my-document-detail'),
]
