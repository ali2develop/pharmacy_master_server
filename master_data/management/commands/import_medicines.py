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
                
                expected_headers = [
                    'Name', 'Generic Name', 'Category', 'Manufacturer', 
                    'Dosage Form', 'Strength', 'Pack Size', 'Strips Per Box', 
                    'Default Purchase Price', 'Default Selling Price', 'Tax Percent', 'Medicine Type'
                ]
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
                            
                            generic = row.get('Generic Name', '').strip()
                            manufacturer = row.get('Manufacturer', '').strip()
                            category_name = row.get('Category', '').strip()
                            
                            category = None
                            if category_name:
                                category, _ = MedicineCategory.objects.get_or_create(name=category_name)
                                
                            dosage_form_raw = row.get('Dosage Form', '').strip()
                            dosage_form = 'OTHER'
                            if dosage_form_raw.upper() in dosage_forms:
                                dosage_form = dosage_form_raw.upper()
                                
                            strength = row.get('Strength', '').strip()
                            
                            # Parse Pack Size (e.g. "20 tablets")
                            pack_size_str = row.get('Pack Size', '').strip()
                            total_l1 = 1
                            l1_unit_name = 'Unit'
                            if pack_size_str:
                                # extract number and text
                                match = re.match(r'^([\d.]+)\s*(.*)$', pack_size_str)
                                if match:
                                    total_l1_f = float(match.group(1))
                                    total_l1 = int(total_l1_f) if total_l1_f.is_integer() else total_l1_f
                                    parsed_unit = match.group(2).strip()
                                    if parsed_unit:
                                        # strip trailing 's' for singular name
                                        if parsed_unit.lower().endswith('s') and len(parsed_unit) > 1:
                                            l1_unit_name = parsed_unit[:-1].capitalize()
                                        else:
                                            l1_unit_name = parsed_unit.capitalize()
                            
                            strips_per_box_str = row.get('Strips Per Box', '').strip()
                            strips_per_box = None
                            if strips_per_box_str:
                                strips_per_box = int(float(strips_per_box_str))
                                
                            l2_multiplier = 1
                            l3_multiplier = 1
                            l2_unit_name = ''
                            l3_unit_name = ''
                            
                            if strips_per_box and strips_per_box > 0 and total_l1 > 1:
                                if total_l1 % strips_per_box != 0:
                                    # Data anomaly (e.g., 28 tablets in 3 strips). Fall back to Box -> Tablet directly.
                                    l3_unit_name = 'Box'
                                    l3_multiplier = 1
                                    l2_unit_name = ''
                                    l2_multiplier = int(total_l1)
                                else:
                                    l3_unit_name = 'Box'
                                    l3_multiplier = strips_per_box
                                    l2_unit_name = 'Strip'
                                    l2_multiplier = int(total_l1 / strips_per_box)
                            else:
                                if total_l1 > 1:
                                    l3_unit_name = 'Pack'
                                    l3_multiplier = 1
                                    l2_unit_name = ''
                                    l2_multiplier = int(total_l1)
                            
                            # Handle Prices
                            def parse_decimal(val_str):
                                val_str = val_str.strip()
                                if not val_str:
                                    return Decimal('0')
                                try:
                                    return Decimal(val_str)
                                except Exception:
                                    return Decimal('0')
                                    
                            purchase_price = parse_decimal(row.get('Default Purchase Price', ''))
                            selling_price = parse_decimal(row.get('Default Selling Price', ''))
                            tax_percent = parse_decimal(row.get('Tax Percent', ''))
                            
                            # Handle Type
                            type_str = row.get('Medicine Type', '').strip().upper()
                            med_type = type_str if type_str in medicine_types else 'NORMAL'
                            is_refrigerated = (med_type == 'REFRIGERATED')
                            is_injection = (med_type == 'INJECTION')
                            
                            medicine, created = Medicine.objects.update_or_create(
                                name=name,
                                manufacturer=manufacturer,
                                defaults={
                                    'generic_name': generic,
                                    'category': category,
                                    'dosage_form': dosage_form,
                                    'strength': strength,
                                    
                                    'l1_unit_name': l1_unit_name,
                                    'l2_unit_name': l2_unit_name,
                                    'l2_multiplier': l2_multiplier,
                                    'l3_unit_name': l3_unit_name,
                                    'l3_multiplier': l3_multiplier,
                                    
                                    'default_purchase_price': purchase_price,
                                    'default_selling_price': selling_price,
                                    'tax_percent': tax_percent,
                                    
                                    'medicine_type': med_type,
                                    'is_refrigerated': is_refrigerated,
                                    'is_injection': is_injection,
                                    'is_active': True,
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
