import os
import traceback
import threading
import json
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wish_swap.settings')
import django
django.setup()

from wish_swap.settings import NETWORKS
from wish_swap.payments.api import parse_payment, parse_validate_payment_message
from wish_swap.transfers.models import Transfer
from wish_swap.transfers.api import parse_execute_transfer_message
from wish_swap.tokens.models import Token
import rabbitmq


class Receiver(threading.Thread):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def run(self):
        connection = rabbitmq.get_connection()
        channel = rabbitmq.get_channel(connection, self.queue)
        channel.basic_consume(
            queue=self.queue,
            on_message_callback=self.callback
        )
        print(f'{self.queue}: queue was started', flush=True)
        channel.start_consuming()

    def validate_payment(self, message):
        print(f'{self.queue}: validate payment message has been received\n', flush=True)
        parse_validate_payment_message(self.queue, message)

    def payment(self, message):
        print(f'{self.queue}: payment message has been received\n', flush=True)
        parse_payment(message, self.queue)

    '''
    def transfer(self, message):
        print(f'{self.queue}: transfer message has been received\n', flush=True)
        transfer = Transfer.objects.get(pk=message['transferId'])
        if transfer.status == 'SUCCESS':
            print(f'{self.queue}: transfer has already been confirmed\n', flush=True)
            return
        if message['success']:
            transfer = Transfer.objects.get(pk=message['transferId'])
            transfer.status = 'SUCCESS'
            print(f'{self.queue}: transfer confirmed successfully\n', flush=True)
        else:
            transfer.status = 'FAIL'
            print(f'{self.queue}: transfer was not completed, confirmation fail\n', flush=True)
        transfer.save()
    '''

    def execute_transfer(self, message):
        print(f'{self.queue}: execute transfer message has been received\n', flush=True)
        parse_execute_transfer_message(message, self.queue)

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

    def unknown_handler(self, message):
        print(f'{self.queue}: unknown message has been received\n', message, flush=True)


for token in Token.objects.all():
    receiver = Receiver(f'{token.network}-{token.symbol}-transfers')
    receiver.start()

for network in NETWORKS.keys():
    receiver = Receiver(network)
    receiver.start()

receiver = Receiver('payments-validation')
receiver.start()
