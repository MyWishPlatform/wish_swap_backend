from django.contrib import admin
from wish_swap.networks.models import GasInfo


class GasInfoAdmin(admin.ModelAdmin):
    readonly_fields = ('price',)


admin.site.register(GasInfo, GasInfoAdmin)
