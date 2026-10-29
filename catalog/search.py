from django.conf import settings
from django.db.models import Q


def search_products(queryset, q):
    """PostgreSQL full-text search (ranked, typo-tolerant substring fallback); plain contains on SQLite."""
    q = (q or '').strip()
    if not q:
        return queryset
    plain = (Q(name__icontains=q) | Q(brand__icontains=q) | Q(tags__icontains=q) | Q(description__icontains=q)
             | Q(category__name__icontains=q) | Q(shop__name__icontains=q))
    if settings.IS_POSTGRES:
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
        vector = (SearchVector('name', weight='A') + SearchVector('brand', 'tags', weight='B')
                  + SearchVector('description', weight='C'))
        query = SearchQuery(q, search_type='websearch')
        return (queryset.annotate(rank=SearchRank(vector, query))
                .filter(Q(rank__gt=0.01) | plain).order_by('-rank', '-sold'))
    return queryset.filter(plain)
