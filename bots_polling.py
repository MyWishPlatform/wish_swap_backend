import time
import telebot
import os
import threading
import traceback
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wish_swap.settings')
import django
django.setup()

from wish_swap.bots.models import BotSub
from wish_swap.tokens.models import Dex, Token
from wish_swap.settings import NETWORKS
from django.db import IntegrityError


class Bot(threading.Thread):
    def __init__(self, dex):
        super().__init__()
        self.dex = dex
        self.bot = telebot.TeleBot(dex.bot_token)

        @self.bot.message_handler(commands=['start'])
        def start_handler(message):
            try:
                BotSub(dex=self.dex, chat_id=message.chat.id).save()
                self.bot.reply_to(message, 'Hello!')
            except IntegrityError:
                pass

        @self.bot.message_handler(commands=['stop'])
        def stop_handler(message):
            try:
                BotSub.objects.get(dex=self.dex, chat_id=message.chat.id).delete()
                self.bot.reply_to(message, 'Bye!')
            except BotSub.DoesNotExist:
                pass

        @self.bot.message_handler(commands=['balances'])
        def balances_handler(message):
            tokens = Token.objects.filter(dex=self.dex)
            balances = ''
            for token in tokens:
                network = token.network
                decimals = NETWORKS[network]['decimals']
                symbol = NETWORKS[network]['symbol']
                balance = token.swap_owner_balance / (10 ** decimals)
                balances += f'{network}: {balance} {symbol}\n'
            self.bot.reply_to(message, balances)

        @self.bot.message_handler(commands=['token_balances'])
        def token_balances_handler(message):
            tokens = Token.objects.filter(dex=self.dex)
            balances = ''
            for token in tokens:
                balance = token.swap_contract_token_balance / (10 ** token.decimals)
                balances += f'{token.network}: {balance} {token.symbol}\n'
            self.bot.reply_to(message, balances)

        @self.bot.message_handler(commands=['ping'])
        def ping_handler(message):
            self.bot.reply_to(message, 'Pong')

    def run(self):
        while True:
            try:
                self.bot.polling(none_stop=True)
            except Exception:
                print('\n'.join(traceback.format_exception(*sys.exc_info())), flush=True)
                time.sleep(15)


if __name__ == '__main__':
    dexes = Dex.objects.all()
    bots = {}
    for dex in dexes:
        Bot(dex).start()
        print(f'{dex.name} bot started', flush=True)
