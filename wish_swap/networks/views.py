from rest_framework import viewsets, mixins
from wish_swap.networks.models import GasInfo
from wish_swap.networks.serializers import GasInfoSerializer
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from wish_swap.tokens.models import Token


class GasInfoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = GasInfo.objects.all()
    serializer_class = GasInfoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
