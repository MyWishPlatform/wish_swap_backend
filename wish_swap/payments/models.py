import sys
import traceback
import rabbitmq
from django.db import models
from wish_swap.bots.models import BotSub, BotSwapMessage
from wish_swap.transfers.models import Transfer
from wish_swap.settings import NETWORKS


class Payment(models.Model):
    class Validation(models.TextChoices):
        WAITING_FOR = 'waiting for'
        INVALID_NETWORK_ID = 'invalid network id'
        INVALID_NETWORK = 'invalid network'
        INSUFFICIENT_AMOUNT = 'insufficient amount'
        PROVIDER_IS_UNREACHABLE = 'provider is unreachable'
        SUCCESS = 'success'

    token = models.ForeignKey('tokens.Token', on_delete=models.CASCADE)
    address = models.CharField(max_length=100)
    tx_hash = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=100, decimal_places=0)
    transfer_address = models.CharField(max_length=100)
    transfer_network_number = models.IntegerField()
    validation = models.CharField(max_length=100,
                                  choices=Validation.choices,
                                  default=Validation.WAITING_FOR)

    def __str__(self):
        symbol = self.token.symbol
        return (f'\ttx hash: {self.tx_hash}\n'
                f'\taddress: {self.address}\n'
                f'\tamount: {self.amount / (10 ** self.token.decimals)} {symbol}\n'
                f'\tnetwork: {self.token.network}\n'
                f'\ttransfer address: {self.transfer_address}\n'
                f'\ttransfer network number: {self.transfer_network_number}\n'
                f'\tvalidation: {self.validation}')

    def send_to_validation_queue(self):
        message = {'paymentId': self.id, 'status': 'COMMITTED'}
        rabbitmq.publish_message(f'payments-validation', 'validate_payment', message)

    def send_to_bot_queue(self):
        message = {'paymentId': self.id, 'status': 'COMMITTED'}
        rabbitmq.publish_message(f'swap-status-bots', 'change_swap_status_bot', message)


class ValidationException(Exception):
    def __init__(self, status, message=''):
        self.status = status
        self.message = message
        super().__init__(self.message)
