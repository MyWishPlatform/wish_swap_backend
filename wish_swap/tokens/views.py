from rest_framework import viewsets, mixins
from wish_swap.tokens.models import Dex
from wish_swap.tokens.serializers import DexSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly


class DexViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Dex.objects.all()
    serializer_class = DexSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
