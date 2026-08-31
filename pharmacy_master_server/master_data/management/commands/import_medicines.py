import csv
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from master_data.models import Medicine, MedicineCategory

class Command(BaseCommand):
    help = 'Bulk import medicines from a CSV file. NOTE: "Pack Size" column MUST represent TOTAL individual units in the whole box (e.g. 100 for a box of 10 strips of 10). "Strips Per Box" is optional for items with a middle tier.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The absolute or relative path to the CSV file')

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        # Read allowed choices to validate against
        dosage_forms = [choice[0] for choice in Medicine.DOSAGE_FORM_CHOICES]
        medicine_types = [choice[0] for choice in Medicine.MEDICINE_TYPE_CHOICES]

        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                # Basic header validation
                expected_headers = ['Name', 'Generic', 'Category', 'Manufacturer', 'Form / Strength', 'Pack Size', 'Strips Per Box', 'Sell Price', 'Type', 'Status']
                actual_headers = reader.fieldnames
                
                if not actual_headers:
                    self.stderr.write(self.style.ERROR("The CSV file is empty or missing headers."))
                    return
                
                missing_headers = [h for h in expected_headers if h not in actual_headers]
                if missing_headers:
                    self.stderr.write(self.style.ERROR(f"CSV is missing required headers: {', '.join(missing_headers)}"))
                    return
                
                with transaction.atomic():
                    for i, row in enumerate(reader, start=2):
                        try:
                            name = row.get('Name', '').strip()
                            if not name:
                                raise ValueError("Name is required.")
                            
                            generic = row.get('Generic', '').strip()
                            manufacturer = row.get('Manufacturer', '').strip()
                            category_name = row.get('Category', '').strip()
                            
                            # Handle Category
                            category = None
                            if category_name:
                                category, _ = MedicineCategory.objects.get_or_create(name=category_name)
                                
                            # Handle Form / Strength
                            form_strength = row.get('Form / Strength', '').strip()
                            dosage_form = 'OTHER'
                            strength = form_strength
                            
                            if form_strength:
                                parts = form_strength.split(' ', 1)
                                first_word = parts[0].upper()
                                if first_word in dosage_forms:
                                    dosage_form = first_word
                                    strength = parts[1].strip() if len(parts) > 1 else ''
                                    
                            # Handle Pack and Strips
                            pack_size = 1
                            if row.get('Pack Size', '').strip():
                                pack_size = int(float(row.get('Pack Size').strip()))
                                
                            strips_per_box = None
                            if row.get('Strips Per Box', '').strip():
                                strips_per_box = int(float(row.get('Strips Per Box').strip()))
                                
                            unit = row.get('Unit', '').strip()
                            
                            # Validations for Packaging Configuration
                            if strips_per_box:
                                if pack_size <= strips_per_box:
                                    raise ValueError(f"pack_size ({pack_size}) must be greater than strips_per_box ({strips_per_box}). Pack size must represent TOTAL individual base units.")
                                if pack_size % strips_per_box != 0:
                                    raise ValueError(f"pack_size ({pack_size}) must be evenly divisible by strips_per_box ({strips_per_box}).")
                            
                                    
                            # Handle Sell Price
                            sell_price_str = row.get('Sell Price', '').strip()
                            try:
                                sell_price = Decimal(sell_price_str) if sell_price_str else Decimal('0')
                            except Exception:
                                sell_price = Decimal('0')
                                
                            # Handle Type
                            type_str = row.get('Type', '').strip().upper()
                            med_type = type_str if type_str in medicine_types else 'NORMAL'
                            is_refrigerated = (med_type == 'REFRIGERATED')
                            is_injection = (med_type == 'INJECTION')
                            
                            # Handle Status
                            is_active = (row.get('Status', '').strip().lower() == 'active')
                            
                            # Update or Create
                            medicine, created = Medicine.objects.update_or_create(
                                name=name,
                                manufacturer=manufacturer,
                                defaults={
                                    'generic_name': generic,
                                    'category': category,
                                    'dosage_form': dosage_form,
                                    'strength': strength,
                                    'pack_size': pack_size,
                                    'strips_per_box': strips_per_box,
                                    'unit': unit,
                                    'default_selling_price': sell_price,
                                    'medicine_type': med_type,
                                    'is_refrigerated': is_refrigerated,
                                    'is_injection': is_injection,
                                    'is_active': is_active,
                                    'distribution_scope': 'ALL',
                                }
                            )
                            
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                                
                        except Exception as e:
                            skipped_count += 1
                            row_name = row.get('Name', 'Unknown') if row else 'Unknown'
                            errors.append(f"Row {i} ({row_name}): {str(e)}")
                            
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {csv_path}"))
            return

        self.stdout.write(self.style.SUCCESS(f"\n--- Import Complete ---"))
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Updated: {updated_count}")
        self.stdout.write(f"Skipped/Failed: {skipped_count}")
        
        if errors:
            self.stderr.write(self.style.WARNING("\nErrors encountered (these rows were skipped):"))
            for err in errors:
                self.stderr.write(f"- {err}")
