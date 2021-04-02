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

    def send_bot_message(self):
        message = self.generate_bot_message()
        subs = BotSub.objects.filter(dex=self.token.dex)
        bot = self.token.dex.bot
        for sub in subs:
            try:
                msg_id = bot.send_message(sub.chat_id,
                                          message,
                                          parse_mode='html',
                                          disable_web_page_preview=True).message_id
            except Exception:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                return

            BotSwapMessage(payment=self, sub=sub, message_id=msg_id).save()

    def generate_bot_message(self):
        p_amount = self.amount / (10 ** self.token.decimals)
        p_symbol = self.token.symbol
        p_network = self.token.network
        p_message = f'Received <a href="{NETWORKS[p_network]["explorer_url"] + self.tx_hash}">{p_amount} {p_symbol}</a>'
        try:
            transfer = Transfer.objects.get(payment=self)
        except Transfer.DoesNotExist:
            return p_message

        t_amount = transfer.amount / (10 ** transfer.token.decimals)
        t_symbol = transfer.token.symbol
        t_network = transfer.token.network

        if transfer.status in (Transfer.Status.CREATED, Transfer.Status.VALIDATION):
            return p_message
        elif transfer.status == Transfer.Status.PROVIDER_IS_UNREACHABLE:
            return f'{p_message}. swap will be executed later due to unreachable provider in {t_network} network'
        elif transfer.status == Transfer.Status.SUCCESS:
            return f'successful swap: {p_amount} {p_symbol} -> {t_amount} {t_symbol}'
        elif transfer.status == Transfer.Status.HIGH_GAS_PRICE:
            return f'{p_message}. swap will be executed later due to high gas price in {t_network} network'
        elif transfer.status == Transfer.Status.INSUFFICIENT_TOKEN_BALANCE:
            token_balance = transfer.token.swap_contract_token_balance / (10 ** transfer.token.decimals)
            return f'{p_message}. please top up swap contract token balance to make a transfer, current is {token_balance} {t_symbol}'
        elif transfer.status == Transfer.Status.INSUFFICIENT_BALANCE:
            decimals = NETWORKS[t_network]['decimals']
            balance = transfer.token.swap_owner_balance / (10 ** decimals)
            symbol = NETWORKS[t_network]['symbol']
            return f'{p_message}. please top up swap contract owner balance to make a transfer, current is {balance} {symbol}'
        elif transfer.status == Transfer.Status.FAIL:
            return f'failed swap: {p_amount} {p_symbol} -> {t_amount} {t_symbol} ({transfer.tx_error})'


class ValidationException(Exception):
    def __init__(self, status, message=''):
        self.status = status
        self.message = message
        super().__init__(self.message)
