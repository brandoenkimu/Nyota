from celery import shared_task

from .etl import run_etl


@shared_task
def run_etl_task():
    run = run_etl()
    return {'ok': run.ok, 'rows': run.fact_rows}
