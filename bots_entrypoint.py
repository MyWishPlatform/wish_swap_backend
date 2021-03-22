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
            balances.append(token.swap_owner_balance)
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
                if balance < tokens[i].network['warning_level'] and flags[i] == False:
                    msg = self.bot.send_message(GROUP_ID, f"{self.dex_name} {tokens[i].network}: WARNING! Balance is less then {tokens[i].nework['warning_level']}")
                    reply_flags[self.dex_name+'-'+tokens[i].network] = msg.message_id
                    flags[i] = True
                if balance > tokens[i].network['warning_level'] and flags[i] == True:
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
        threading.Thread(target=self.check_balances_two).start()
        #self.bot.send_message(GROUP_ID, f'{self.network}: queue was started')
        channel.start_consuming()

    def payment(self, message):
        paym = Payment.objects.get(id=message['paymentId'])
        from_network = paym.token.network
        #print(f'{self.network}: payment message has been received\n', flush=True)
        message_string = f'Payment message\namount: {paym.amount / (10 ** paym.token.decimals)} {paym.token.symbol}\nnetwork: {from_network}\ntx hash: {paym.tx_hash}'
        msg = self.bot.send_message(GROUP_ID, f'{message_string}')
        msg_id = msg.message_id
        paym.bot_message_id = msg_id
        paym.save()

    def transfer(self, message):
        #print(f'{self.network}: execute transfer message has been received\n', flush=True)
        trans = Transfer.objects.get(id=message['transferId'])
        flag = False
        #if trans.status != 'PENDING':
        if trans.status == Transfer.Status.PROVIDER_IS_DOWN:
            mess_string = f'Transfer message\namount: {trans.amount / (10 ** trans.token.decimals)} {trans.token.symbol}\ntx hash: {trans.tx_hash}\ntx error: {trans.tx_error}\ntx status: provider is down'
            flag = True
        elif trans.status == Transfer.Status.SUCCESS:
            mess_string = f'Transfer message\namount: {trans.amount / (10 ** trans.token.decimals)} {trans.token.symbol}\ntx hash: {trans.tx_hash}\ntx error: {trans.tx_error}\ntx status: success'
            flag = True
        elif trans.status == Transfer.Status.HIGH_GAS_PRICE:
            mess_string = f'Transfer message\namount: {trans.amount / (10 ** trans.token.decimals)} {trans.token.symbol}\ntx hash: {trans.tx_hash}\ntx error: {trans.tx_error}\ntx status: high gas price'
            flag = True
        elif trans.status == Transfer.Status.INSUFFICIENT_TOKEN_BALANCE:
            mess_string = f'Transfer message\namount: {trans.amount / (10 ** trans.token.decimals)} {trans.token.symbol}\ntx hash: {trans.tx_hash}\ntx error: {trans.tx_error}\ntx status: insufficient token balance'
            flag = True
        elif trans.status == Transfer.Status.INSUFFICIENT_BALANCE:
            mess_string = f'Transfer message\namount: {trans.amount / (10 ** trans.token.decimals)} {trans.token.symbol}\ntx hash: {trans.tx_hash}\ntx error: {trans.tx_error}\ntx status: insufficient balance'
            flag = True
        elif trans.status == Transfer.Status.FAIL:
            mess_string = f'Transfer message\namount: {trans.amount / (10 ** trans.token.decimals)} {trans.token.symbol}\ntx hash: {trans.tx_hash}\ntx error: {trans.tx_error}\ntx status: fail'
            flag = True
            
        if flag == True:
            mess_id = trans.payment.bot_message_id
            self.bot.send_message(GROUP_ID, f'Transfer message\n{mess_string}', reply_to_message_id=mess_id)

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
