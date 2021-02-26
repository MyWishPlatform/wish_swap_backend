from wish_swap.transfers.models import Transfer
from wish_swap.networks.models import GasInfo
from wish_swap.settings import NETWORKS, TX_STATUS_CHECK_TIMEOUT
import time


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
            return

    transfer.execute()
    transfer.save()

    if transfer.status == 'FAIL':
        print(f'{queue}: failed transfer \n{transfer}\n', flush=True)
        transfer.send_to_queue('bot')
    else:
        transfer.update_status()
        transfer.save()
        transfer.send_to_queue('bot')
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
        transfer.send_to_queue('bot')

    timeout = NETWORKS[network]['transfer_timeout']
    print(f'{queue}: waiting {timeout} seconds before next transfer...\n', flush=True)
    time.sleep(timeout)
