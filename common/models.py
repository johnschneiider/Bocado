import uuid

from django.db import models


class TimeStampedUUIDModel(models.Model):
    """
    Base model for Aladdin:
    - UUID primary key for easy DB migration and syncing
    - created_at / updated_at on every table
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

