import uuid
from decimal import Decimal
from django.db import models

class Pharmacy(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    
    is_trial = models.BooleanField(default=True)
    from django.utils import timezone
    trial_started_at = models.DateTimeField(default=timezone.now)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    
    license_expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Pharmacies'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from django.conf import settings
        import datetime
        if self.is_trial and not self.trial_ends_at:
            if not self.trial_started_at:
                from django.utils import timezone
                start = timezone.now()
            else:
                start = self.trial_started_at
            self.trial_ends_at = start + datetime.timedelta(days=getattr(settings, 'TRIAL_DAYS', 30))
        super().save(*args, **kwargs)

    def get_effective_status(self):
        # Check manual suspension
        if hasattr(self, 'pharmacycontrol') and self.pharmacycontrol.is_suspended:
            reason = self.pharmacycontrol.suspension_reason or 'Account suspended by administrator.'
            return {'status': 'blocked', 'reason': reason, 'trial_ends_in_days': None, 'license_expires_in_days': None}
        
        from django.utils import timezone
        now = timezone.now()
        
        # Check trial
        if self.is_trial:
            if self.trial_ends_at:
                if now > self.trial_ends_at:
                    return {'status': 'blocked', 'reason': 'Your trial period has expired. Please contact support to upgrade.', 'trial_ends_in_days': 0, 'license_expires_in_days': None}
                else:
                    days_left = (self.trial_ends_at - now).days
                    return {'status': 'active', 'reason': '', 'trial_ends_in_days': days_left, 'license_expires_in_days': None}
        else:
            # Check paid license expiry
            if self.license_expires_at:
                if now > self.license_expires_at:
                    return {'status': 'blocked', 'reason': 'Your license has expired. Please contact us to renew.', 'trial_ends_in_days': None, 'license_expires_in_days': 0}
                else:
                    days_left = (self.license_expires_at - now).days
                    return {'status': 'active', 'reason': '', 'trial_ends_in_days': None, 'license_expires_in_days': days_left}
                    
        return {'status': 'active', 'reason': '', 'trial_ends_in_days': None, 'license_expires_in_days': None}

class PharmacyControl(models.Model):
    pharmacy = models.OneToOneField(Pharmacy, on_delete=models.CASCADE)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True, default='')

    def __str__(self):
        return f"Control for {self.pharmacy.name}"

class APIToken(models.Model):
    pharmacy = models.OneToOneField(Pharmacy, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Token for {self.pharmacy.name}"

class MedicineCategory(models.Model):
    remote_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Medicine Categories'

    def __str__(self):
        return self.name

class Medicine(models.Model):
    MEDICINE_TYPE_CHOICES = [
        ('NORMAL', 'Normal'),
        ('REFRIGERATED', 'Refrigerated'),
        ('INJECTION', 'Injection'),
        ('OTHER', 'Other'),
    ]

    DOSAGE_FORM_CHOICES = [
        ('TABLET', 'Tablet'), ('CAPSULE', 'Capsule'), ('SYRUP', 'Syrup'),
        ('SUSPENSION', 'Suspension'), ('DROPS', 'Drops'), ('INJECTION', 'Injection'),
        ('CREAM', 'Cream'), ('OINTMENT', 'Ointment'), ('GEL', 'Gel'),
        ('SPRAY', 'Spray'), ('INHALER', 'Inhaler'), ('PATCH', 'Patch'),
        ('POWDER', 'Powder'), ('SUPPOSITORY', 'Suppository'), ('OTHER', 'Other'),
    ]

    DISTRIBUTION_CHOICES = [
        ('ALL', 'All Pharmacies'),
        ('SELECTED', 'Selected Pharmacies Only'),
    ]

    remote_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    
    name = models.CharField(max_length=255, db_index=True)
    generic_name = models.CharField(max_length=255, blank=True, default='', db_index=True)
    manufacturer = models.CharField(max_length=255, blank=True, default='', db_index=True)
    category = models.ForeignKey(MedicineCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='medicines')
    barcode = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)

    dosage_form = models.CharField(max_length=20, choices=DOSAGE_FORM_CHOICES, blank=True, default='')
    strength = models.CharField(max_length=100, blank=True, default='')

    # Generic UoM Hierarchy
    l1_unit_name = models.CharField(max_length=50, blank=True, default='')  # Base unit (e.g., Tablet, mL, Vial)
    l2_unit_name = models.CharField(max_length=50, blank=True, default='')  # e.g., Strip, Bottle
    l2_multiplier = models.PositiveIntegerField(default=1, help_text="Number of L1 units in one L2 unit")
    l3_unit_name = models.CharField(max_length=50, blank=True, default='')  # e.g., Box, Carton
    l3_multiplier = models.PositiveIntegerField(default=1, help_text="Number of L2 units in one L3 unit")

    default_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    default_selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    default_discount = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    default_profit_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))

    is_returnable = models.BooleanField(default=True)
    is_refrigerated = models.BooleanField(default=False)
    is_injection = models.BooleanField(default=False)
    medicine_type = models.CharField(max_length=20, choices=MEDICINE_TYPE_CHOICES, default='NORMAL')

    min_stock_level = models.PositiveIntegerField(default=0)
    max_stock_level = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    reorder_qty = models.PositiveIntegerField(default=0)

    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    
    distribution_scope = models.CharField(max_length=10, choices=DISTRIBUTION_CHOICES, default='ALL')
    available_to_pharmacies = models.ManyToManyField(Pharmacy, blank=True, related_name='scoped_medicines')
    
    version = models.PositiveIntegerField(default=1, db_index=True)
    is_deleted = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Always bump to the next global version when saved, unless we are specifically skipping it
        if kwargs.pop('skip_version_bump', False) is False:
            max_v = type(self).objects.aggregate(models.Max('version'))['version__max'] or 0
            self.version = max_v + 1
        super().save(*args, **kwargs)


class AppRelease(models.Model):
    version = models.CharField(max_length=50, unique=True)
    download_url = models.URLField(max_length=500)
    release_notes = models.TextField(blank=True, default='')
    is_mandatory = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"v{self.version}"
