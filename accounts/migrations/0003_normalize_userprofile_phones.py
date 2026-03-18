from django.db import migrations


def normalize_userprofile_phones(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    for p in UserProfile.objects.exclude(phone="").only("id", "phone"):
        new_phone = (p.phone or "").strip().replace(" ", "")
        if new_phone != p.phone:
            p.phone = new_phone
            p.save(update_fields=["phone"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_phoneotp"),
    ]

    operations = [
        migrations.RunPython(normalize_userprofile_phones, migrations.RunPython.noop),
    ]

