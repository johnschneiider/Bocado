from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("credits", "0003_normalize_customer_phones_digits"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="address",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]

