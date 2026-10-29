from django.core.management.base import BaseCommand

from orders.services import PAYABLE_AFTER_MINUTES, expire_unpaid_orders


class Command(BaseCommand):
    help = 'Cancel online orders that were never paid and put their stock back.'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=PAYABLE_AFTER_MINUTES)

    def handle(self, *args, **o):
        self.stdout.write(self.style.SUCCESS(f'{expire_unpaid_orders(o["minutes"])} unpaid order(s) cancelled.'))
