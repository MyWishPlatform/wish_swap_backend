from django.contrib import admin
from django.forms import BaseInlineFormSet
from wish_swap.tokens.models import Token, Dex


class TokenFormset(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(TokenFormset, self).__init__(*args, **kwargs)


class TokenInline(admin.TabularInline):
    model = Token
    formset = TokenFormset
    extra = 0


class DexAdmin(admin.ModelAdmin):
    inlines = [TokenInline, ]


admin.site.register(Dex, DexAdmin)
