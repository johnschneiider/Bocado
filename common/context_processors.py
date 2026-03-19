from restaurants.models import Category


def categories_processor(request):
    """
    Context processor para incluir categorías en todas las páginas.
    """
    return {
        'categories': Category.objects.all().order_by('order')
    }
