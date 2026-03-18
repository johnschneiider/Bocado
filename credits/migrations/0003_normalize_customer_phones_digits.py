from django.db import migrations


def normalize_customer_phones_digits(apps, schema_editor):
    Customer = apps.get_model("credits", "Customer")
    for c in Customer.objects.exclude(phone="").only("id", "phone"):
        new_phone = "".join(ch for ch in (c.phone or "").strip() if ch.isdigit())
        if new_phone != c.phone:
            c.phone = new_phone
            c.save(update_fields=["phone"])


class Migration(migrations.Migration):
    dependencies = [
        ("credits", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_customer_phones_digits, migrations.RunPython.noop),
    ]

