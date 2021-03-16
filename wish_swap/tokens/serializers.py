from rest_framework import serializers
from wish_swap.tokens.models import Token, Dex


class TokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = (
            'token_address',
            'swap_address',
            'fee_address',
            'fee',
            'decimals',
            'symbol',
            'network',
            'is_original',
            'token_abi',
            'swap_abi',
        )


class DexSerializer(serializers.ModelSerializer):
    tokens = TokenSerializer(many=True)

    class Meta:
        model = Dex
        fields = ('name', 'tokens', 'min_swap_amount')

    def create(self, validated_data):
        tokens_data = validated_data.pop('tokens')
        dex = Dex.objects.create(**validated_data)
        for token in tokens_data:
            dex.tokens.create(**token)
        return dex

    def update(self, instance, validated_data):
        tokens_data = validated_data.pop('tokens')
        tokens = instance.tokens.all()
        for token, token_data in zip(tokens, tokens_data):
            for attr, value in token_data.items():
                setattr(token, attr, value)
            token.save()

        for token in tokens_data[len(tokens):]:
            instance.tokens.create(**token)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
