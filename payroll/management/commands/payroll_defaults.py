"""python manage.py payroll_defaults [--shops]

Creates a sensible starting set of ranks and job categories and gives every staff member a pay profile that does
not have one yet. Everything is editable afterwards in the Payroll screens. Salaries here are placeholders."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from payroll.models import EmploymentType, JobCategory, PayGrade, PayProfile
from shops.models import Shop

User = get_user_model()
PLATFORM_GRADES = [('Intern', 1, 25000), ('Junior', 2, 45000), ('Mid-level', 3, 80000), ('Senior', 4, 130000),
                   ('Lead', 5, 200000), ('Executive', 6, 400000)]
PLATFORM_CATS = [('Management', 20, 'Leads people and the company'), ('Engineering', 15, 'Builds and runs the platform'),
                 ('Analytics', 12, 'Data and insight'), ('Operations', 8, 'Orders, sellers and finance'), ('Customer support', 5, 'Helps members')]
PLATFORM_MAP = {'ceo': ('Executive', 'Management'), 'admin': ('Senior', 'Operations'), 'analyst': ('Mid-level', 'Analytics'),
                'developer': ('Senior', 'Engineering'), 'support': ('Junior', 'Customer support')}
SHOP_GRADES = [('Assistant', 1, 20000), ('Supervisor', 2, 35000), ('Manager', 3, 55000)]
SHOP_CATS = [('Management', 10, ''), ('Sales', 5, ''), ('Inventory', 3, ''), ('Customer care', 3, ''), ('Analysis', 5, '')]
SHOP_MAP = {'manager': ('Manager', 'Management'), 'cashier': ('Assistant', 'Sales'), 'inventory': ('Supervisor', 'Inventory'),
            'support': ('Assistant', 'Customer care'), 'analyst': ('Supervisor', 'Analysis')}


def ensure(shop, grades, cats):
    g = {n: PayGrade.objects.get_or_create(shop=shop, name=n, defaults={'rank': r, 'base_salary': Decimal(s)})[0] for n, r, s in grades}
    c = {n: JobCategory.objects.get_or_create(shop=shop, name=n, defaults={'allowance_percent': Decimal(p), 'description': d})[0] for n, p, d in cats}
    return g, c


class Command(BaseCommand):
    help = 'Create default ranks, job categories and pay profiles.'

    def add_arguments(self, parser):
        parser.add_argument('--shops', action='store_true', help='also do it for every shop team')

    def handle(self, *args, **o):
        made = 0
        g, c = ensure(None, PLATFORM_GRADES, PLATFORM_CATS)
        for u in User.objects.filter(role__in=PLATFORM_MAP, is_active=True).filter(pay_profile__isnull=True):
            gn, cn = PLATFORM_MAP[u.role]
            PayProfile.objects.create(user=u, grade=g[gn], category=c[cn], employment_type=EmploymentType.FULL_TIME)
            made += 1
        if o['shops']:
            for shop in Shop.objects.all():
                g, c = ensure(shop, SHOP_GRADES, SHOP_CATS)
                for m in shop.members.select_related('user').filter(active=True, user__pay_profile__isnull=True):
                    gn, cn = SHOP_MAP.get(m.role, ('Assistant', 'Sales'))
                    PayProfile.objects.create(user=m.user, grade=g[gn], category=c[cn], apply_statutory=False)
                    made += 1
        self.stdout.write(self.style.SUCCESS(f'{made} pay profile(s) created. Adjust salaries in the Payroll screens.'))
