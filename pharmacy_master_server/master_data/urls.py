from django.urls import path
from .views import MedicineSyncView, PharmacyStatusView

urlpatterns = [
    path('sync/medicines/', MedicineSyncView.as_view(), name='sync_medicines'),
    path('pharmacy/status/', PharmacyStatusView.as_view(), name='pharmacy_status'),
]
