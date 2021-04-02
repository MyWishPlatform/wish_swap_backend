import rabbitmq
from django.db import models
from wish_swap.bots.api import generate_bot_message
from wish_swap.bots.models import BotSub, BotSwapMessage


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

    def send_bot_message(self):
        message = generate_bot_message(payment=self)
        subs = BotSub.objects.filter(dex=self.token.dex)
        bot = self.token.dex.bot
        for sub in subs:
            msg_id = bot.send_message(sub.chat_id, message)
            BotSwapMessage(payment=self, sub=sub, message_id=msg_id).save()


class ValidationException(Exception):
    def __init__(self, status, message=''):
        self.status = status
        self.message = message
        super().__init__(self.message)
