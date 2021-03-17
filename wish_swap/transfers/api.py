from wish_swap.transfers.models import Transfer
from wish_swap.networks.models import GasInfo
from wish_swap.settings import NETWORKS, TX_STATUS_CHECK_TIMEOUT
import time


def parse_execute_transfer_message(message, queue):
    transfer = Transfer.objects.get(id=message['transferId'])
    print(f'{queue}: received transfer \n{transfer}\n', flush=True)

    if transfer.status not in ('WAITING FOR TRANSFER', 'HIGH GAS PRICE', 'SMALL TOKEN BALANCE', 'SMALL BALANCE'):
        print(f'{queue}: there was already an attempt for transfer \n{transfer}\n', flush=True)
        return

    network = transfer.network

    if not transfer.check_token_balance():
        transfer.save()
        print(f'{queue}: small token balance for transfer \n{transfer}\n', flush=True)
        return

    if network in ('Ethereum', 'Binance-Smart-Chain'):
        gas_info = GasInfo.objects.get(network=network)
        gas_price = gas_info.price * (10 ** 9)
        gas_price_limit = gas_info.price_limit * (10 ** 9)
        if not transfer.check_gas_price(gas_price, gas_price_limit):
            print(f'{queue}: high gas price ({gas_price} Gwei > {gas_price_limit} Gwei), '
                  f'postpone transfer \n{transfer}\n', flush=True)
            transfer.save()
            return
        if not transfer.check_balance(gas_price=gas_price):
            transfer.save()
            print(f'{queue}: small balance for transfer \n{transfer}\n', flush=True)
            return
        transfer.execute(gas_price=gas_price)
        transfer.save()
    elif network == 'Binance-Chain':
        if not transfer.check_balance():
            transfer.save()
            return

        transfer.execute()
        transfer.save()
    else:
        print(f'{queue}: unknown network for transfer \n{transfer}\n', flush=True)
        raise Exception('Unknown network')

    if transfer.status == 'FAIL':
        print(f'{queue}: failed transfer \n{transfer}\n', flush=True)
        transfer.send_to_bot_queue()
    else:
        transfer.update_status()
        transfer.save()
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
        transfer.send_to_bot_queue()

    timeout = NETWORKS[network]['transfer_timeout']
    print(f'{queue}: waiting {timeout} seconds before next transfer...\n', flush=True)
    time.sleep(timeout)
