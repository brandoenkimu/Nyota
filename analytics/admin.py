from django.contrib import admin

from .models import EtlRun, MiningResult

admin.site.register(EtlRun)
admin.site.register(MiningResult)
