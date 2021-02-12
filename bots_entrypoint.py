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
from wish_swap.tokens.models import Dex

class Receiver(threading.Thread):
    def __init__(self, network, bot_token):
        super().__init__()
        self.network = network
        self.bot = telebot.TeleBot(bot_token)

    def check_chains(self):
        if self.network == 'Ethereum-bot':
            w3 = Web3(Web3.HTTPProvider(NETWORKS['Ethereum']['bot']['node']))
            while True:
                f_eth = open('scanner/settings/Ethereum', 'r')
                data_eth = f_eth.read()
                print(f'{self.network}: block from file <{data_eth}>')
                eth_block = w3.eth.blockNumber
                if abs(eth_block - int(data_eth)) > 50:
                    msg = self.bot.send_message(GROUP_ID, f'{self.network}: scanner crashed')
                    while abs(eth_block - int(data_eth)) > 50:
                        eth_block = w3.eth.blockNumber
                        print(f'{self.network} : web3 block {eth_block}')
                        f_eth = open('scanner/settings/Ethereum', 'r')
                        data_eth = f_eth.read()
                        f_eth.close()
                        print(f'{self.network} : block from file {data_eth}')
                        sleep(BOT_TIMEOUT)
                    self.bot.send_message(GROUP_ID, f'{self.network}: scanner is alive', reply_to_message_id=msg.message_id)
                sleep(BOT_TIMEOUT)
        elif self.network == 'Binance-Smart-Chain-bot':
            w3 = Web3(Web3.HTTPProvider(NETWORKS['Binance-Smart-Chain']['bot']['node']))
            while True:
                f_bsc = open('scanner/settings/Binance-Smart-Chain', 'r')
                data_bsc = f_bsc.read()
                bsc_block = w3.eth.blockNumber
                if abs(int(data_bsc) - bsc_block) > 50:
                    msg = self.bot.send_message(GROUP_ID, f'{self.network}: scanner crashed')
                    while abs(bsc_block - int(data_bsc)) > 50:
                        f_bsc = open('scanner/settings/Binance-Smart-Chain', 'r')
                        data_bsc = f_bsc.read()
                        f_bsc.close()
                        print(f'{self.network} : block from file {data_bsc}')
                        bsc_block = w3.eth.blockNumber
                        print(f'{self.network} : web3 block {bsc_block}')
                        sleep(BOT_TIMEOUT)
                    self.bot.send_message(GROUP_ID, f'{self.network}: scanner is alive', reply_to_message_id=msg.message_id)
                sleep(BOT_TIMEOUT)
            
    def check_balances(self):
        w3_eth = Web3(Web3.HTTPProvider(NETWORKS['Ethereum']['bot']['node']))
        w3_bsc = Web3(Web3.HTTPProvider(NETWORKS['Binance-Smart-Chain']['bot']['node']))
        eth_address = Dex.objects.get(name='Wish')['Ethereum'].swap_owner
        bsc_address = Dex.objects.get(name='Wish')['Binance-Smart-Chain'].swap_owner
        bin_address = Dex.objects.get(name='Wish')['Binance-Chain'].swap_address
        eth_balance = w3_eth.eth.getBalance(eth_address)/NETWORKS['Ethereum']['decimals']
        bsc_balance = w3_bsc.eth.getBalance(bsc_address)/NETWORKS['Binance-Smart-Chain']['decimals']
        bin_balance = get_binance_balance(bin_address)
        if self.network == 'Ethereum-bot':
            print(f'{self.network} balance = {eth_balance}')
        elif self.network == 'Binance-Smart-Chain-bot':
            print(f'{self.network} balance = {bsc_balance}')
        elif self.network == 'Binance-Chain-bot':
            print(f'{self.network} balance = {bin_balance}')
        flag_eth = False
        flag_bsc = False
        flag_bin = False
        while True:
            if self.network == 'Ethereum-bot' and eth_balance != w3_eth.eth.getBalance(eth_address)/NETWORKS['Ethereum']['decimals']:
                if eth_balance < w3_eth.eth.getBalance(eth_address)/NETWORKS['Ethereum']['decimals']:
                    self.bot.send_message(GROUP_ID, f'{self.network}: balance replenished')
                    eth_balance = w3_eth.eth.getBalance(eth_address)/NETWORKS['Ethereum']['decimals']
                else:
                    eth_balance = w3_eth.eth.getBalance(eth_address)/NETWORKS['Ethereum']['decimals']
            if self.network == 'Ethereum-bot' and w3_eth.eth.getBalance(eth_address)/NETWORKS['Ethereum']['decimals'] < NETWORKS['Ethereum']['warning_level'] and flag_eth == False:
                msg_eth = self.bot.send_message(GROUP_ID, f"{self.network}: WARNING! Balance is less then {NETWORKS['Ethereum']['warning_level']}")
                flag_eth = True
            if self.network == 'Ethereum-bot' and w3_eth.eth.getBalance(eth_address)/NETWORKS['Ethereum']['decimals'] > NETWORKS['Ethereum']['warning_level'] and flag_eth == True:
                self.bot.send_message(GROUP_ID, f"{self.network}: Balance is ok", reply_to_message_id=msg_eth.message_id)
                flag_eth = False
            if self.network == 'Binance-Smart-Chain-bot' and bsc_balance != w3_bsc.eth.getBalance(bsc_address)/NETWORKS['Binance-Smart-Chain']['decimals']:
                if bsc_balance < w3_bsc.eth.getBalance(bsc_address)/NETWORKS['Binance-Smart-Chain']['decimals']:
                    self.bot.send_message(GROUP_ID, f'{self.network}: balance replenished')
                    bsc_balance = w3_bsc.eth.getBalance(bsc_address)/NETWORKS['Binance-Smart-Chain']['decimals']
                else:
                    bsc_balance = w3_bsc.eth.getBalance(bsc_address)/NETWORKS['Binance-Smart-Chain']['decimals']
            if self.network == 'Binance-Smart-Chain-bot' and w3_bsc.eth.getBalance(bsc_address)/NETWORKS['Binance-Smart-Chain']['decimals'] < NETWORKS['Binance-Smart-Chain']['warning_level'] and flag_bsc == False:
                msg_bsc = self.bot.send_message(GROUP_ID, f"{self.network}: WARNING! Balance is less then {NETWORKS['Binance-Smart-Chain']['warning_level']}")
                flag_bsc = True
            if self.network == 'Binance-Smart-Chain-bot' and w3_bsc.eth.getBalance(bsc_address)/NETWORKS['Binance-Smart-Chain']['decimals'] > NETWORKS['Binance-Smart-Chain']['warning_level'] and flag_bsc == True:
                self.bot.send_message(GROUP_ID, f"{self.network}: Balance is ok", reply_to_message_id=msg_bsc.message_id)
                flag_bsc = False
            if self.network == 'Binance-Chain-bot' and bin_balance != get_binance_balance(bin_address):
                if bin_balance < get_binance_balance(bin_address):
                    self.bot.send_message(GROUP_ID, f'{self.network}: balance replenished')
                    bin_balance = get_binance_balance(bin_address)
                else:
                    bin_balance = get_binance_balance(bin_address)
            if self.network == 'Binance-Chain-bot' and get_binance_balance(bin_address) < NETWORKS['Binance-Chain']['warning_level'] and flag_bin == False:
                msg_bin = self.bot.send_message(GROUP_ID, f"{self.network}: WARNING! Balance is less then {NETWORKS['Binance-Chain']['warning_level']}")
                flag_bin = True
            if self.network == 'Binance-Chain-bot' and get_binance_balance(bin_address) > NETWORKS['Binance-Chain']['warning_level'] and flag_bin == True:
                self.bot.send_message(GROUP_ID, f"{self.network}: Balance is ok", reply_to_message_id=msg_bin.message_id)
                flag_bin = False
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
            queue=self.network,
            durable=True,
            auto_delete=False,
            exclusive=False
        )
        channel.basic_consume(
            queue=self.network,
            on_message_callback=self.callback
        )
        print(f'{self.network}: queue was started', flush=True)
        threading.Thread(target=self.start_polling).start()
        threading.Thread(target=self.check_chains).start()
        threading.Thread(target=self.check_balances).start()
        #self.bot.send_message(GROUP_ID, f'{self.network}: queue was started')
        channel.start_consuming()

    def payment(self, message):
        paym = Payment.objects.get(id=message['paymentId'])
        from_network = paym.token.network
        #print(f'{self.network}: payment message has been received\n', flush=True)
        msg = self.bot.send_message(GROUP_ID, f'Payment message\n{str(paym)}')
        msg_id = msg.message_id
        paym.bot_message_id = msg_id
        paym.save()

    def transfer(self, message):
        #print(f'{self.network}: execute transfer message has been received\n', flush=True)
        trans = Transfer.objects.get(id=message['transferId'])
        #mess_string = str(trans.payment)
        mess_id = trans.payment.bot_message_id
        self.bot.send_message(GROUP_ID, f'Transfer message\n{str(trans.payment)}', reply_to_message_id=mess_id)

    def callback(self, ch, method, properties, body):
        # print('RECEIVER: received', method, properties, body, flush=True)
        try:
            message = json.loads(body.decode())
            getattr(self, properties.type, self.unknown_handler)(message)
            '''if message.get('status', '') == 'COMMITTED':
                getattr(self, properties.type, self.unknown_handler)(message)'''
        except Exception as e:
            print('\n'.join(traceback.format_exception(*sys.exc_info())),
                  flush=True)
        else:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def scanner_crash(self, message):
        #print(f'{self.network}: scanner crashed\n')
        self.bot.send_message(GROUP_ID, f'{self.network}: scanner crashed\n')

    def scanner_up(self, message):
        #print(f'{self.network}: scanner is alive\n')
        self.bot.send_message(GROUP_ID, f'{self.network}: scanner is alive\n')

    def unknown_handler(self, message):
        print(f'{self.network}: unknown message has been received\n', message, flush=True)
        #self.bot.send_message(GROUP_ID, f'{self.network}: unknown message has been received\n')
        
def get_binance_balance(address):
    url = f'{NETWORKS["Binance-Chain"]["api-url"]}account/{address}?format=json'
    response = requests.get(url)
    result = json.loads(response.text)
    balance = 0
    for row in result['balances']:
        if row['symbol'] == 'BNB':
            balance = row['free']
    if balance != 0 :
        return float(balance)
    else:
        return None

if __name__ == '__main__':
    for network, params in NETWORKS.items():
        receiver = Receiver(network+'-bot', params['bot']['token'])
        receiver.start()
