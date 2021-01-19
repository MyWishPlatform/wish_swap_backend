from django.db import models


class SwapContract(models.Model):
    address = models.CharField(max_length=100)
    owner_address = models.CharField(max_length=100)
    owner_private = models.CharField(max_length=100)


class SwapAddress(models.Model):
    bnbcli_key = models.CharField(max_length=100)
    bnbcli_password = models.CharField(max_length=100)
    address = models.CharField(max_length=100)
    mnemonic = models.CharField(max_length=100)


class Token(models.Model):
    dex = models.ForeignKey('tokens.Dex', on_delete=models.CASCADE)
    token_address = models.CharField(max_length=100)
    swap_address = models.OneToOneField('tokens.SwapAddress', on_delete=models.SET_NULL, null=True)
    swap_contract = models.OneToOneField('tokens.SwapContract', on_delete=models.SET_NULL, null=True)
    fee_address = models.CharField(max_length=100)
    fee = models.IntegerField()
    decimals = models.IntegerField()
    symbol = models.CharField(max_length=50)
    network = models.CharField(max_length=100)
    is_original = models.BooleanField()


class Dex(models.Model):
    def __getitem__(self, network):
        return Token.objects.get(dex=self, network=network)
