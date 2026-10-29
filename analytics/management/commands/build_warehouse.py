from django.core.management.base import BaseCommand

from analytics.etl import run_etl


class Command(BaseCommand):
    help = 'Rebuild the data warehouse (star schema) and run the mining jobs.'

    def handle(self, *args, **options):
        run = run_etl()
        self.stdout.write(self.style.SUCCESS(f'Warehouse built: {run.fact_rows} sales rows. {run.message}'))
