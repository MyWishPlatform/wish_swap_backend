from django.db import models


class Payment(models.Model):
    token = models.ForeignKey('tokens.Token')
    address = models.CharField(max_length=100)
    tx_hash = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=100, decimal_places=0)
