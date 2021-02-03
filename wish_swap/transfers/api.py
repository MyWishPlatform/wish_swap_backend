import pika
import os
import json
from wish_swap.transfers.models import Transfer
from wish_swap.networks.models import GasInfo
from wish_swap.settings import NETWORKS, TX_STATUS_CHECK_TIMEOUT
import time
from rabbitmq_api import send_rabbitmq_message


def send_transfer_to_queue(transfer):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        'rabbitmq',
        5672,
        os.getenv('RABBITMQ_DEFAULT_VHOST', 'wish_swap'),
        pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER', 'wish_swap'),
                              os.getenv('RABBITMQ_DEFAULT_PASS', 'wish_swap')),
    ))
    channel = connection.channel()
    channel.queue_declare(
        queue=transfer.network + '-transfers',
        durable=True,
        auto_delete=False,
        exclusive=False
    )
    channel.basic_publish(
        exchange='',
        routing_key=transfer.network + '-transfers',
        body=json.dumps({'transferId': transfer.id, 'status': 'COMMITTED'}),
        properties=pika.BasicProperties(type='execute_transfer'),
    )
    connection.close()


def send_transfer_to_bot(transfer):
    send_rabbitmq_message(transfer.network + '-bot', 'transfer', {'transferId': transfer.id})


def parse_execute_transfer_message(message, queue):
    transfer = Transfer.objects.get(id=message['transferId'])
    print(f'{queue}: received transfer \n{transfer}\n', flush=True)

    if transfer.status not in ('WAITING FOR TRANSFER', 'HIGH GAS PRICE'):
        print(f'{queue}: there was already an attempt for transfer \n{transfer}\n', flush=True)
        return

    network = transfer.network

    if network in ('Ethereum', 'Binance-Smart-Chain'):
        gas_info = GasInfo.objects.get(network=network)
        gas_price = gas_info.price
        gas_price_limit = gas_info.price_limit
        if gas_price > gas_price_limit:
            transfer.status = 'HIGH GAS PRICE'
            transfer.save()
            print(f'{queue}: high gas price ({gas_price} Gwei > {gas_price_limit} Gwei), '
                  f'postpone transfer \n{transfer}\n', flush=True)
            send_transfer_to_bot(transfer)
            return

    transfer.execute()
    transfer.save()

    if transfer.status == 'FAIL':
        print(f'{queue}: failed transfer \n{transfer}\n', flush=True)
        send_transfer_to_bot(transfer)
    else:
        transfer.update_status()
        transfer.save()
        send_transfer_to_bot(transfer)
        while transfer.status == 'PENDING':
            print(f'{queue}: pending transfer \n{transfer}\n', flush=True)
            print(f'{queue}: waiting {TX_STATUS_CHECK_TIMEOUT} seconds before next status check...\n', flush=True)
            time.sleep(TX_STATUS_CHECK_TIMEOUT)
            transfer.update_status()
            transfer.save()
        if transfer.status == 'SUCCESS':
            print(f'{queue}: successful transfer \n{transfer}\n', flush=True)
        else:
            print(f'{queue}: failed transfer after pending \n{transfer}\n', flush=True)
        send_transfer_to_bot(transfer)

    timeout = NETWORKS[network]['transfer_timeout']
    print(f'{queue}: waiting {timeout} seconds before next transfer...\n', flush=True)
    time.sleep(timeout)
