from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.db.models import Max, Q

from .models import Medicine, APIToken, AppRelease
from django.utils import timezone
from .serializers import MedicineSerializer

class PharmacyTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Token '):
            return None
            
        token_key = auth_header.split(' ')[1]
        try:
            token = APIToken.objects.get(token=token_key, is_active=True)
            # DRF expects (user, auth) tuple. We can use token.pharmacy as the "user"
            # or just return (None, token) and skip permission_classes.
            return (None, token)
        except APIToken.DoesNotExist:
            raise AuthenticationFailed('Invalid or inactive API token')

class MedicineSyncView(APIView):
    authentication_classes = [PharmacyTokenAuthentication]

    def get(self, request):
        try:
            pharmacy = request.auth.pharmacy
            pharmacy.last_seen_at = timezone.now()
            pharmacy.save(update_fields=['last_seen_at'])
        except AttributeError:
            return Response({"error": "Invalid token or no pharmacy linked."}, status=403)
            
        since_version = int(request.GET.get('since_version', 0))

        medicines = Medicine.objects.filter(
            Q(distribution_scope='ALL') |
            Q(distribution_scope='SELECTED', available_to_pharmacies=pharmacy),
            version__gt=since_version,
        ).distinct()

        serializer = MedicineSerializer(medicines, many=True)
        max_version = medicines.aggregate(Max('version'))['version__max']
        
        return Response({
            'medicines': serializer.data,
            'server_version': max_version if max_version is not None else since_version,
        })

class PharmacyStatusView(APIView):
    authentication_classes = [PharmacyTokenAuthentication]

    def get(self, request):
        try:
            pharmacy = request.auth.pharmacy
            # Goal 2: Pharmacy visibility - Update last_seen_at
            pharmacy.last_seen_at = timezone.now()
            pharmacy.save(update_fields=['last_seen_at'])
        except AttributeError:
            return Response({"error": "Invalid token or no pharmacy linked."}, status=403)
            
        latest_release = AppRelease.objects.first()
        release_data = None
        if latest_release:
            release_data = {
                'version': latest_release.version,
                'download_url': latest_release.download_url,
                'release_notes': latest_release.release_notes,
                'is_mandatory': latest_release.is_mandatory,
            }
            
        status_info = pharmacy.get_effective_status()
            
        return Response({
            'status': status_info['status'],
            'block_reason': status_info['reason'],
            'trial_ends_in_days': status_info['trial_ends_in_days'],
            'license_expires_in_days': status_info['license_expires_in_days'],
            'pharmacy_name': pharmacy.name,
            'latest_release': release_data,
        })
