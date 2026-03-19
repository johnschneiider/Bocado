from django.core.management.base import BaseCommand
from restaurants.models import Category


class Command(BaseCommand):
    help = 'Seed the database with default food categories'

    def handle(self, *args, **options):
        categories = [
            {"name": "Asiática", "slug": "asiatica", "icon": "fa-bowl-rice", "order": 1},
            {"name": "Carnes", "slug": "carnes", "icon": "fa-drumstick-bite", "order": 2},
            {"name": "Panes & Tortas", "slug": "panes-tortas", "icon": "fa-bread-slice", "order": 3},
            {"name": "Pizza", "slug": "pizza", "icon": "fa-pizza-slice", "order": 4},
            {"name": "Café", "slug": "cafe", "icon": "fa-mug-hot", "order": 5},
            {"name": "Saludable", "slug": "saludable", "icon": "fa-leaf", "order": 6},
            {"name": "Hamburguesa", "slug": "hamburguesa", "icon": "fa-burger", "order": 7},
            {"name": "Latinoamericana", "slug": "latinoamericana", "icon": "fa-earth-americas", "order": 8},
            {"name": "Mexicana", "slug": "mexicana", "icon": "fa-pepper-hot", "order": 9},
            {"name": "Colombiana", "slug": "colombiana", "icon": "fa-flag", "order": 10},
        ]

        for cat in categories:
            Category.objects.get_or_create(
                slug=cat["slug"],
                defaults={
                    "name": cat["name"],
                    "icon": cat["icon"],
                    "order": cat["order"],
                }
            )
            self.stdout.write(self.style.SUCCESS(f"Categoría creada: {cat['name']}"))

        self.stdout.write(self.style.SUCCESS("Categorías creadas exitosamente"))
