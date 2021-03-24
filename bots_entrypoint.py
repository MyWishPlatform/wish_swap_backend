import pika, sys, os
import telebot
from time import sleep
import json
import traceback
import threading
from web3 import Web3
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wish_swap.settings')
import django
django.setup()

from wish_swap.settings_local import NETWORKS
from wish_swap.settings_local import GROUP_ID
from wish_swap.settings_local import BOT_TIMEOUT
from wish_swap.transfers.models import Transfer
from wish_swap.payments.models import Payment
from wish_swap.tokens.models import Dex, Token

class Receiver(threading.Thread):
    def __init__(self, dex_name, bot_token):
        super().__init__()
        self.dex_name = dex_name
        #self.network = network
        self.bot = telebot.TeleBot(bot_token)

    def check_balances_two(self):
        dex = Dex.objects.get(name=self.dex_name)
        tokens = Token.objects.filter(dex=dex)
        balances = []
        reply_flags = {}
        for token in tokens:
            try:
                balances.append(token.swap_owner_balance)
            except requests.exceptions.RequestException:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                sleep(15)
            reply_flags.setdefault(token.dex.name+'-'+token.network)
        flags = []
        for i in range(len(tokens)):
            flags.append(False)
        while True:
            for i in range(len(tokens)):
                try:
                    balance = tokens[i].swap_owner_balance
                except requests.exceptions.RequestException:
                    balance = balances[i]
                    continue
                if balances[i] != balance:
                    if balances[i] < balance:
                        self.bot.send_message(GROUP_ID, f'{self.dex_name} {tokens[i].network}: balance replenished')
                        balances[i] = balance
                    else:
                        balances[i] = balance
                if balance < NETWORKS[tokens[i].network]['warning_level'] and flags[i] == False:
                    msg = self.bot.send_message(GROUP_ID, f"{self.dex_name} {tokens[i].network}: WARNING! Balance is less then {NETWORKS[tokens[i].network]['warning_level']}")
                    reply_flags[self.dex_name+'-'+tokens[i].network] = msg.message_id
                    flags[i] = True
                if balance > NETWORKS[tokens[i].network]['warning_level'] and flags[i] == True:
                    self.bot.send_message(GROUP_ID, f"{self.dex_name} {tokens[i].network}: Balance is ok", reply_to_message_id=reply_flags[self.dex_name+'-'+tokens[i].network])
                    flags[i] = False
                sleep(BOT_TIMEOUT)
                
    def start_polling(self):
        while True:
            try:
                self.bot.polling(none_stop=True)
            except Exception:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                sleep(15)
                                                
    def start_checking(self):
        while True:
            try:
                self.check_balances_two()
            except Exception:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                sleep(15)

    def run(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            'rabbitmq',
            5672,
            os.getenv('RABBITMQ_DEFAULT_VHOST', 'wish_swap'),
            pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER', 'wish_swap'),
                                  os.getenv('RABBITMQ_DEFAULT_PASS', 'wish_swap')),
            heartbeat=7200,
            blocked_connection_timeout=7200
        ))
        channel = connection.channel()
        channel.queue_declare(
            queue=self.dex_name+'-bot',
            durable=True,
            auto_delete=False,
            exclusive=False
        )
        channel.basic_consume(
            queue=self.dex_name+'-bot',
            on_message_callback=self.callback
        )
        print(f'{self.dex_name}: queue was started', flush=True)
        threading.Thread(target=self.start_polling).start()
        threading.Thread(target=self.start_checking).start()
        #self.bot.send_message(GROUP_ID, f'{self.network}: queue was started')
        channel.start_consuming()

    def payment(self, message):
        payment = Payment.objects.get(id=message['paymentId'])
        amount = payment.amount / (10 ** payment.token.decimals)
        symbol = payment.token.symbol
        network = payment.token.network

        message_str = f'received {amount} {symbol} in {network} network: {payment.tx_hash}'
        msg = self.bot.send_message(GROUP_ID, message_str)
        msg_id = msg.message_id
        payment.bot_message_id = msg_id
        payment.save()

    def transfer(self, message):
        transfer = Transfer.objects.get(id=message['transferId'])
        amount = transfer.amount / (10 ** transfer.token.decimals)
        symbol = transfer.token.symbol
        network = transfer.token.network
        flag = False
        if transfer.status == Transfer.Status.PROVIDER_IS_UNREACHABLE:
            message_str = f'transfer will be executed later due to unreachable provider in {network} network'
            flag = True
        elif transfer.status == Transfer.Status.SUCCESS:
            message_str = f'successfully sent {amount} {symbol} in {network} network: {transfer.tx_hash}'
            flag = True
        elif transfer.status == Transfer.Status.HIGH_GAS_PRICE:
            message_str = f'transfer will be executed later due to high gas price in {network} network'
            flag = True
        elif transfer.status == Transfer.Status.INSUFFICIENT_TOKEN_BALANCE:
            token_balance = transfer.token.swap_contract_token_balance / (10 ** transfer.token.decimals)
            message_str = f'please top up swap contract token balance to make a transfer, current is {token_balance} {symbol}'
            flag = True
        elif transfer.status == Transfer.Status.INSUFFICIENT_BALANCE:
            decimals = NETWORKS[network]['decimals']
            balance = transfer.token.swap_owner_balance / (10 ** decimals)
            symbol = NETWORKS[network]['symbol']
            message_str = f'please top up swap contract owner balance to make a transfer, current is {balance} {symbol}'
            flag = True
        elif transfer.status == Transfer.Status.FAIL:
            message_str = f'failed to send {amount} {symbol} in {network} network: {transfer.tx_error}'
            flag = True
            
        if flag == True:
            mess_id = transfer.payment.bot_message_id
            self.bot.send_message(GROUP_ID, message_str, reply_to_message_id=mess_id)

    def callback(self, ch, method, properties, body):
        # print('RECEIVER: received', method, properties, body, flush=True)
        try:
            message = json.loads(body.decode())
            getattr(self, properties.type, self.unknown_handler)(message)
        except Exception as e:
            print('\n'.join(traceback.format_exception(*sys.exc_info())),
                  flush=True)
        else:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def unknown_handler(self, message):
        print(f'{self.network}: unknown message has been received\n', message, flush=True)
        #self.bot.send_message(GROUP_ID, f'{self.network}: unknown message has been received\n')

if __name__ == '__main__':
    dexes = Dex.objects.all()
    for dex in dexes:
        receiver = Receiver(dex.name, dex.bot_token)
        receiver.start()
