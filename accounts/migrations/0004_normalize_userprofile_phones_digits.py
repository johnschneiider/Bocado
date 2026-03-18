from django.db import migrations


def normalize_userprofile_phones_digits(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    for p in UserProfile.objects.exclude(phone="").only("id", "phone"):
        new_phone = "".join(ch for ch in (p.phone or "").strip() if ch.isdigit())
        if new_phone != p.phone:
            p.phone = new_phone
            p.save(update_fields=["phone"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_normalize_userprofile_phones"),
    ]

    operations = [
        migrations.RunPython(normalize_userprofile_phones_digits, migrations.RunPython.noop),
    ]

