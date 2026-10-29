import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from analytics.mining import sentiment_score
from audit.service import record
from catalog.models import Category, Product, Review, Wishlist
from catalog.search import search_products
from orders.models import Order, OrderItem, ShopOrderStatus
from shops.models import Shop, ShopStatus

from .context import ACCENT_KEYS, THEME_KEYS
from .models import HeroSlide, Notification
from .utils import paginate

DEFAULT_SLIDES = [
    {'kicker': 'Every shop is a star', 'title': 'Discover a galaxy of local sellers',
     'subtitle': 'Phones, fashion, home, food and more, from real shops near you.', 'cta_label': 'Start exploring',
     'cta_url': '/products/', 'art_variant': 0},
    {'kicker': 'Open your own sky', 'title': 'Launch your shop in minutes',
     'subtitle': 'Your own page, your own team, live order tracking and honest analytics.',
     'cta_label': 'Become a seller', 'cta_url': '/seller/signup/', 'art_variant': 1},
    {'kicker': 'Track every step', 'title': 'From packed to delivered, in real time',
     'subtitle': 'Follow your parcel on the map and chat with the seller any time.', 'cta_label': 'Browse shops',
     'cta_url': '/shops/', 'art_variant': 2},
    {'kicker': 'Pay your way', 'title': 'M-Pesa, cards or cash on delivery',
     'subtitle': 'Secure checkout with instant confirmation.', 'cta_label': 'See deals',
     'cta_url': '/products/?sale=1', 'art_variant': 3},
]


def _live_products():
    return (Product.objects.filter(is_active=True, shop__status=ShopStatus.ACTIVE)
            .select_related('shop', 'category'))


def home(request):
    slides = list(HeroSlide.objects.filter(active=True)) or DEFAULT_SLIDES
    base = _live_products()
    featured = base.filter(is_featured=True).order_by('-sold')[:10] or base.order_by('-sold')[:10]
    ctx = {
        'slides': slides,
        'featured': featured,
        'new_arrivals': base.order_by('-created_at')[:10],
        'deals': base.filter(compare_at_price__gt=F('price')).order_by('-sold')[:10],
        'top_shops': Shop.objects.filter(status=ShopStatus.ACTIVE).annotate(n=Count('products'))
                         .order_by('-rating_avg', '-n')[:12],
        'categories': Category.objects.filter(parent__isnull=True)[:16],
        'stat_shops': Shop.objects.filter(status=ShopStatus.ACTIVE).count(),
        'stat_products': base.count(),
        'stat_orders': Order.objects.count(),
    }
    return render(request, 'core/home.html', ctx)


SORTS = {
    'new': ('-created_at', 'Newest'), 'popular': ('-sold', 'Best selling'), 'price_asc': ('price', 'Price: low to high'),
    'price_desc': ('-price', 'Price: high to low'), 'rating': ('-rating_avg', 'Top rated'),
}


def _filtered_products(request, base):
    p = request.GET
    qs = search_products(base, p.get('q'))
    if p.get('category'):
        cat = Category.objects.filter(slug=p['category']).first()
        if cat:
            qs = qs.filter(Q(category=cat) | Q(category__parent=cat))
    if p.get('shop'):
        qs = qs.filter(shop__slug=p['shop'])
    if p.get('min'):
        qs = qs.filter(price__gte=p['min'] if p['min'].replace('.', '', 1).isdigit() else 0)
    if p.get('max') and p['max'].replace('.', '', 1).isdigit():
        qs = qs.filter(price__lte=p['max'])
    if p.get('instock'):
        qs = qs.filter(stock__gt=0)
    if p.get('sale'):
        qs = qs.filter(compare_at_price__gt=F('price'))
    sort = p.get('sort', '')
    if sort in SORTS:
        qs = qs.order_by(SORTS[sort][0])
    elif not p.get('q'):
        qs = qs.order_by('-sold', '-created_at')
    return qs


def product_list(request):
    qs = _filtered_products(request, _live_products())
    page = paginate(request, qs, 24)
    return render(request, 'core/products.html', {
        'page': page, 'products': page.object_list, 'categories': Category.objects.filter(parent__isnull=True),
        'sorts': SORTS, 'q': request.GET.get('q', ''), 'current_category': request.GET.get('category', ''),
        'current_sort': request.GET.get('sort', ''),
    })


def category_page(request, slug):
    return redirect(f'/products/?category={slug}')


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related('shop', 'category'), slug=slug)
    user = request.user
    allowed = product.is_active and product.shop.is_public
    if not allowed and not (user.is_authenticated and (user.role in ('admin', 'support') or user.shop == product.shop)):
        raise Http404
    Product.objects.filter(pk=product.pk).update(views=F('views') + 1)
    reviews = product.reviews.select_related('user')[:30]
    can_review = False
    if user.is_authenticated and user.role == 'customer':
        bought = OrderItem.objects.filter(product=product, shop_order__order__customer=user,
                                          shop_order__status=ShopOrderStatus.DELIVERED).exists()
        can_review = bought and not product.reviews.filter(user=user).exists()
    breakdown = {r['rating']: r['n'] for r in product.reviews.values('rating').annotate(n=Count('id'))}
    related = (_live_products().filter(category=product.category).exclude(pk=product.pk).order_by('-sold')[:8])
    in_wishlist = user.is_authenticated and Wishlist.objects.filter(user=user, product=product).exists()
    return render(request, 'core/product.html', {
        'product': product, 'reviews': reviews, 'can_review': can_review, 'related': related,
        'in_wishlist': in_wishlist, 'gallery': product.gallery.all(),
        'breakdown': [(i, breakdown.get(i, 0)) for i in (5, 4, 3, 2, 1)],
    })


def shop_directory(request):
    qs = Shop.objects.filter(status=ShopStatus.ACTIVE).annotate(n=Count('products', filter=Q(products__is_active=True)))
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(tagline__icontains=q) | Q(city__icontains=q) | Q(county__icontains=q))
    county = request.GET.get('county', '')
    if county:
        qs = qs.filter(county__iexact=county)
    shops = list(qs.order_by('-rating_avg', 'name'))
    points = [{'name': s.name, 'slug': s.slug, 'lat': float(s.lat), 'lng': float(s.lng), 'city': s.city,
               'tagline': s.tagline} for s in shops if s.has_location]
    counties = (Shop.objects.filter(status=ShopStatus.ACTIVE).exclude(county='')
                .values_list('county', flat=True).distinct().order_by('county'))
    return render(request, 'core/shops.html', {'shops': shops, 'points': points, 'points_json': json.dumps(points).replace('<', '\\u003c'), 'counties': counties, 'q': q,
                                               'county': county})


def shop_site(request, slug):
    shop = get_object_or_404(Shop, slug=slug)
    user = request.user
    privileged = user.is_authenticated and (user.role in ('admin', 'support', 'ceo') or user.shop == shop)
    if not shop.is_public and not privileged:
        raise Http404
    products = shop.products.filter(is_active=True).select_related('category')
    cats = (Category.objects.filter(products__shop=shop, products__is_active=True).distinct())
    cat = request.GET.get('category')
    if cat:
        products = products.filter(category__slug=cat)
    sort = request.GET.get('sort')
    products = products.order_by(SORTS[sort][0] if sort in SORTS else '-is_featured', '-sold')
    reviews = Review.objects.filter(product__shop=shop).select_related('user', 'product')[:20]
    stats = shop.products.aggregate(total=Count('id'), sold=Sum('sold'))
    return render(request, 'core/shop.html', {
        'shop': shop, 'products': products, 'shop_categories': cats, 'reviews': reviews,
        'stats': stats, 'follower_count': shop.followers.count(), 'current_category': cat or '',
        'is_following': user.is_authenticated and shop.followers.filter(pk=user.pk).exists(),
        'preview': not shop.is_public,
    })


@login_required
@require_POST
def shop_follow(request, slug):
    shop = get_object_or_404(Shop, slug=slug, status=ShopStatus.ACTIVE)
    if shop.followers.filter(pk=request.user.pk).exists():
        shop.followers.remove(request.user)
    else:
        shop.followers.add(request.user)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'following': shop.followers.filter(pk=request.user.pk).exists(),
                             'count': shop.followers.count()})
    return redirect(shop.get_absolute_url())


@login_required
@require_POST
def wishlist_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    obj, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        obj.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'saved': created})
    return redirect(request.META.get('HTTP_REFERER') or product.get_absolute_url())


@login_required
@require_POST
def review_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    delivered = OrderItem.objects.filter(product=product, shop_order__order__customer=request.user,
                                         shop_order__status=ShopOrderStatus.DELIVERED).exists()
    if not delivered:
        messages.error(request, 'You can review a product after it has been delivered to you.')
        return redirect(product.get_absolute_url())
    try:
        rating = max(1, min(5, int(request.POST.get('rating', 0))))
    except ValueError:
        rating = 0
    if not rating:
        messages.error(request, 'Please choose a star rating.')
        return redirect(product.get_absolute_url())
    body = request.POST.get('body', '').strip()[:2000]
    title = request.POST.get('title', '').strip()[:100]
    Review.objects.update_or_create(product=product, user=request.user, defaults={
        'rating': rating, 'title': title, 'body': body, 'sentiment': sentiment_score(f'{title} {body}')})
    agg = product.reviews.aggregate(a=Avg('rating'), n=Count('id'))
    Product.objects.filter(pk=product.pk).update(rating_avg=round(agg['a'] or 0, 2), rating_count=agg['n'])
    sagg = Review.objects.filter(product__shop=product.shop).aggregate(a=Avg('rating'), n=Count('id'))
    Shop.objects.filter(pk=product.shop_id).update(rating_avg=round(sagg['a'] or 0, 2), rating_count=sagg['n'])
    from .notify import notify
    notify(product.shop.owner, f'New {rating}-star review on {product.name}', body[:120], '/seller/reviews/')
    messages.success(request, 'Thank you for your review!')
    return redirect(product.get_absolute_url())


def search_suggest(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'products': [], 'shops': []})
    prods = _live_products().filter(Q(name__icontains=q) | Q(brand__icontains=q))[:6]
    shops = Shop.objects.filter(status=ShopStatus.ACTIVE).filter(Q(name__icontains=q) | Q(city__icontains=q))[:4]
    return JsonResponse({
        'products': [{'name': p.name, 'url': p.get_absolute_url(), 'price': str(p.price), 'shop': p.shop.name}
                     for p in prods],
        'shops': [{'name': s.name, 'url': s.get_absolute_url(), 'city': s.city} for s in shops],
    })


@require_POST
def save_theme(request):
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        data = {}
    theme, accent = data.get('theme'), data.get('accent')
    if request.user.is_authenticated:
        changed = []
        if theme in THEME_KEYS:
            request.user.theme = theme
            changed.append('theme')
        if accent in ACCENT_KEYS:
            request.user.accent = accent
            changed.append('accent')
        if changed:
            request.user.save(update_fields=changed)
    return JsonResponse({'ok': True})


@login_required
def notifications(request):
    qs = Notification.objects.filter(user=request.user)
    page = paginate(request, qs, 30)
    unread_ids = [n.pk for n in page.object_list if not n.is_read]
    resp = render(request, 'core/notifications.html', {'page': page})
    if unread_ids:
        Notification.objects.filter(pk__in=unread_ids).update(is_read=True)
    return resp


@login_required
@require_POST
def notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect(request.META.get('HTTP_REFERER') or 'core:notifications')


def track_lookup(request):
    """Anyone with an order number and the phone number used at checkout can see its progress."""
    order = None
    error = ''
    number = request.GET.get('number', '').strip().upper()
    phone = ''.join(c for c in request.GET.get('phone', '') if c.isdigit())
    if number and phone:
        found = Order.objects.filter(number=number).prefetch_related('shop_orders__events', 'shop_orders__shop').first()
        digits = ''.join(c for c in (found.ship_phone if found else '') if c.isdigit())
        if found and digits and (digits[-9:] == phone[-9:]):
            order = found
        else:
            error = 'We could not find an order with those details.'
    ctx = {'order': order, 'error': error, 'number': number}
    if order:
        from portals.customer import order_context
        ctx.update(order_context(order, 'public'))
    return render(request, 'core/track.html', ctx)


def about(request):
    return render(request, 'core/about.html')


def terms(request):
    return render(request, 'core/legal.html', {'kind': 'terms'})


def privacy(request):
    return render(request, 'core/legal.html', {'kind': 'privacy'})
