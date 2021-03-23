import pika, sys, os
import telebot
from time import sleep
import json
import traceback
import threading
from web3 import Web3

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wish_swap.settings')
import django
django.setup()

from wish_swap.settings_local import NETWORKS, SCANNER_BOT_TOKEN, SCANNER_BOT_GROUP_ID, BOT_TIMEOUT


class Receiver(threading.Thread):
    def __init__(self, binance_flag, bot_token):
        super().__init__()
        self.binance_flag = binance_flag
        self.bot = telebot.TeleBot(bot_token)

    def check_chains(self):
        w3_eth = Web3(Web3.HTTPProvider(NETWORKS['Ethereum']['node']))
        w3_bsc = Web3(Web3.HTTPProvider(NETWORKS['Binance-Smart-Chain']['node']))
        chain_flag_eth = False
        chain_flag_bsc = False
        while True:
            f_eth = open('scanner/settings/Ethereum', 'r')
            data_eth = f_eth.read()
            #print(f'ETH: block from file <{data_eth}>')
            try:
                eth_block = w3_eth.eth.blockNumber
                bsc_block = w3_bsc.eth.blockNumber
                print(f'ethereum block: {eth_block}; binance-chain-bot: {bsc_block}')
            except Exception:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                sleep(15)
            f_bsc = open('scanner/settings/Binance-Smart-Chain', 'r')
            data_bsc = f_bsc.read()
            print(f'ethereum file block: {data_eth}; BSC file block: {data_bsc}')
            '''try:
                bsc_block = w3_bsc.eth.blockNumber
            except Exception:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                sleep(15)'''
            if abs(eth_block - int(data_eth)) > 50 and chain_flag_eth == False:
                print(f'ETH BIG ABS: {abs(eth_block - int(data_eth))}')
                chain_flag_eth = True
                msg_eth = self.bot.send_message(SCANNER_BOT_GROUP_ID, 'Ethereum-bot: scanner crashed')
            if abs(eth_block - int(data_eth)) <= 50 and chain_flag_eth == True:
                print(f'ETH SMALL ABS: {abs(eth_block - int(data_eth))}')
                chain_flag_eth = False
                self.bot.send_message(SCANNER_BOT_GROUP_ID, 'Ethereum-bot: scanner is alive', reply_to_message_id=msg_eth.message_id)
            if abs(int(data_bsc) - bsc_block) > 50 and chain_flag_bsc == False:
                print(f'BSC BIG ABS: {abs(int(data_bsc) - bsc_block)}')
                chain_flag_bsc = True
                msg_bsc = self.bot.send_message(SCANNER_BOT_GROUP_ID, 'Binance-Smart-Chain-bot: scanner crashed')
            if abs(int(data_bsc) - bsc_block) <= 50 and chain_flag_bsc == True:
                print(f'BSC SMALL ABS: {abs(int(data_bsc) - bsc_block)}')
                chain_flag_bsc = False
                self.bot.send_message(SCANNER_BOT_GROUP_ID, 'Binance-Smart-Chain-bot: scanner is alive', reply_to_message_id=msg_bsc.message_id)
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
            queue='scanner-bot',
            durable=True,
            auto_delete=False,
            exclusive=False
        )
        channel.basic_consume(
            queue='scanner-bot',
            on_message_callback=self.callback
        )
        print('scanner-bot: queue was started', flush=True)
        threading.Thread(target=self.start_polling).start()
        threading.Thread(target=self.check_chains).start()
        #self.bot.send_message(SCANNER_BOT_GROUP_ID, f'{self.network}: queue was started')
        channel.start_consuming()

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
        if self.binance_flag == False:
            self.bot.send_message(SCANNER_BOT_GROUP_ID, 'Binance-bot: scanner crashed\n')
        self.binance_flag = True

    def scanner_up(self, message):
        if self.binance_flag == True:
            self.bot.send_message(SCANNER_BOT_GROUP_ID, 'Binance-bot: scanner is alive\n')
        self.binance_flag = False

    def unknown_handler(self, message):
        print('Binance-bot: unknown message has been received\n', message, flush=True)

if __name__ == '__main__':
    receiver = Receiver(False, SCANNER_BOT_TOKEN)
    receiver.start()
