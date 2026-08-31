from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import Pharmacy, APIToken, MedicineCategory, Medicine, AppRelease


class MedicineAdminForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        pack_size = cleaned_data.get('pack_size')
        strips_per_box = cleaned_data.get('strips_per_box')

        if strips_per_box and pack_size:
            if pack_size <= strips_per_box:
                raise ValidationError("Pack size must be greater than strips per box. Pack size must represent TOTAL individual base units.")
            if pack_size % strips_per_box != 0:
                raise ValidationError("Pack size must be evenly divisible by strips per box.")
        return cleaned_data



from .models import Pharmacy, PharmacyControl, APIToken, MedicineCategory, Medicine, AppRelease

class PharmacyControlInline(admin.StackedInline):
    model = PharmacyControl
    can_delete = False
    verbose_name_plural = 'Pharmacy Control (Suspension)'

@admin.action(description='Convert selected pharmacies to paid (end trial)')
def convert_to_paid(modeladmin, request, queryset):
    queryset.update(is_trial=False)

@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'is_trial', 'trial_ends_at', 'license_expires_at', 'last_seen_at')
    readonly_fields = ('last_seen_at', 'trial_started_at')
    inlines = [PharmacyControlInline]
    actions = [convert_to_paid]

@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'token', 'is_active')

@admin.register(MedicineCategory)
class MedicineCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'version')

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    form = MedicineAdminForm
    list_display = ('name', 'category', 'distribution_scope', 'version', 'is_active')
    list_filter = ('distribution_scope', 'is_active')
    filter_horizontal = ('available_to_pharmacies',)
    search_fields = ('name', 'generic_name')

@admin.register(AppRelease)
class AppReleaseAdmin(admin.ModelAdmin):
    list_display = ('version', 'is_mandatory', 'created_at')
    search_fields = ('version',)
