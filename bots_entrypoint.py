import pika, sys, os
import telebot
from time import sleep
import json
import traceback
import threading
from web3 import Web3
import requests
from bs4 import BeautifulSoup

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wish_swap.settings')
import django
django.setup()

from wish_swap.settings_local import NETWORKS
from wish_swap.settings_local import GROUP_ID
#from wish_swap.payments.api import parse_payment
from wish_swap.transfers.models import Transfer
from wish_swap.payments.models import Payment
from wish_swap.transfers.api import parse_execute_transfer_message

class Receiver(threading.Thread):
    def __init__(self, network, bot_token):
        super().__init__()
        self.network = network
        self.bot = telebot.TeleBot(bot_token)

    def check_chains(self):
        w3 = Web3(Web3.HTTPProvider(NETWORKS['Ethereum']['node']))
        while True:
            if self.network == 'Ethereum-bot':
                f_eth = open('scanner/settings/Ethereum', 'r')
                data_eth = int(f_eth.read())
                f_eth.close()
                eth_block = w3.eth.blockNumber
                if abs(eth_block - data_eth) > 50:
                    self.bot.send_message(GROUP_ID, f'{self.network}: scanner crashed')
                    while abs(eth_block - data_eth) > 50:
                        sleep(15)
                    self.bot.send_message(GROUP_ID, f'{self.network}: scanner is alive')
            elif self.network == 'Binance-Smart-Chain-Bot':
                f_bsc = open('scanner/settings/Binance-Smart-Chain', 'r')
                data_bsc = int(f_bsc.read())
                f_bsc.close()
                req = requests.get('https://bscscan.com/blocks')
                content = BeautifulSoup(req.text, 'html.parser')
                assets = content.select('tbody tr td a')
                bsc_block = int(assets[0].text)
                if abs(data_bsc - bsc_block) > 50:
                    self.bot.send_message(GROUP_ID, f'{self.network}: scanner crashed')
                    while abs(bsc_block - data_bsc) > 50:
                        sleep(15)
                    self.bot.send_message(GROUP_ID, f'{self.network}: scanner is alive')
            sleep(15)


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
            queue=self.network+'-bot',
            durable=True,
            auto_delete=False,
            exclusive=False
        )
        channel.basic_consume(
            queue=self.network+'-bot',
            on_message_callback=self.callback
        )
        print(f'{self.network}: queue was started', flush=True)
        threading.Thread(target=self.start_polling).start()
        threading.Thread(target=self.check_chains).start()
        #self.bot.send_message(GROUP_ID, f'{self.network}: queue was started')
        channel.start_consuming()

    def payment(self, message):
        paym = Payment.objects.get(id=message['PaymentID'])
        #print(f'{self.network}: payment message has been received\n', flush=True)
        mess_string = paym.__str__
        msg = self.bot.send_message(GROUP_ID, f'{self.network}: payment message has been received\n'
                                              f'{mess_string}')
        msg_id = msg.message_id
        paym.bot_message_id = msg_id
        paym.save()
        #parse_payment(message, self.network)

    def transfer(self, message):
        #print(f'{self.network}: execute transfer message has been received\n', flush=True)
        trans = Transfer.objects.get(id=message['TransferID'])
        mess_string = trans.__str__
        mess_id = trans.payment.bot_message_id
        self.bot.send_message(GROUP_ID, f'{self.network}: transfer message has been received\n{mess_string}',
                              reply_to_message_id=mess_id)
        parse_execute_transfer_message(message, self.network)

    def callback(self, ch, method, properties, body):
        # print('RECEIVER: received', method, properties, body, flush=True)
        try:
            message = json.loads(body.decode())
            if message.get('status', '') == 'COMMITTED':
                getattr(self, properties.type, self.unknown_handler)(message)
        except Exception as e:
            print('\n'.join(traceback.format_exception(*sys.exc_info())),
                  flush=True)
        else:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def scanner_crash(self, message):
        self.bot.send_message(GROUP_ID, f'{self.network}: scanner crashed\n')

    def scanner_up(self, message):
        self.bot.send_message(GROUP_ID, f'{self.network}: scanner is alive\n')

    def unknown_handler(self, message):
        print(f'{self.network}: unknown message has been received\n', message, flush=True)
        #self.bot.send_message(GROUP_ID, f'{self.network}: unknown message has been received\n')

if __name__ == '__main__':
    for network, params in NETWORKS.items():
        receiver = Receiver(network+'-bot', params['bot']['token'])
        receiver.start()
