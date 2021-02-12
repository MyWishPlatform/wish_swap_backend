"""wish_swap URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from wish_swap.rates.views import wish_fee_view
from rest_framework.routers import DefaultRouter
from wish_swap.networks.views import GasInfoViewSet
from wish_swap.tokens.views import DexViewSet
from wish_swap.transfers.views import swap_status_view


schema_view = get_schema_view(
    openapi.Info(
        title="Wish Swap API",
        default_version='v1',
        description="API for Wish DEX backend",
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

router = DefaultRouter(trailing_slash=True)
router.register('gas', GasInfoViewSet)
router.register('dex', DexViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api/v1/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/v1/swap_status/<str:payment_hash>/', swap_status_view),
]
