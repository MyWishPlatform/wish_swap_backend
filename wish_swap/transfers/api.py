import time
import requests
from wish_swap.payments.models import ValidationException
from wish_swap.transfers.models import Transfer
from wish_swap.networks.models import GasInfo
from wish_swap.settings import NETWORKS, TX_STATUS_CHECK_TIMEOUT, GAS_LIMIT


def parse_execute_transfer_message(message, queue):
    transfer = Transfer.objects.get(id=message['transferId'])
    print(f'{queue}: received transfer \n{transfer}\n', flush=True)
    try:
        execute_transfer(transfer, queue)
    except requests.exceptions.RequestException as e:
        print(f'{queue}: provider is down ({repr(e)}) while executing transfer \n{transfer}\n', flush=True)
        if transfer.status != Transfer.Status.PROVIDER_IS_UNREACHABLE:
            transfer.status = Transfer.Status.PROVIDER_IS_UNREACHABLE
            transfer.save()
            transfer.send_to_bot_queue()
    except ValidationException as e:
        if transfer.status != e.status:
            transfer.status = e.status
            transfer.save()
            transfer.send_to_bot_queue()


def execute_transfer(transfer, queue):
    if transfer.status not in (Transfer.Status.CREATED,
                               Transfer.Status.PROVIDER_IS_UNREACHABLE,
                               Transfer.Status.HIGH_GAS_PRICE,
                               Transfer.Status.INSUFFICIENT_BALANCE,
                               Transfer.Status.INSUFFICIENT_TOKEN_BALANCE):
        print(f'{queue}: there was already an attempt for transfer \n{transfer}\n', flush=True)
        return

    if transfer.token.swap_contract_token_balance < transfer.amount:
        print(f'{queue}: insufficient token balance for transfer \n{transfer}\n', flush=True)
        raise ValidationException(Transfer.Status.INSUFFICIENT_TOKEN_BALANCE)

    network = transfer.network

    if network in ('Ethereum', 'Binance-Smart-Chain'):
        gas_info = GasInfo.objects.get(network=network)
        gas_price = gas_info.price * (10 ** 9)
        gas_price_limit = gas_info.price_limit * (10 ** 9)
        if gas_price > gas_price_limit:
            print(f'{queue}: high gas price ({gas_price} Gwei > {gas_price_limit} Gwei), '
                  f'postpone transfer \n{transfer}\n', flush=True)
            raise ValidationException(Transfer.Status.HIGH_GAS_PRICE)

        if transfer.token.swap_owner_balance < gas_price * GAS_LIMIT:
            print(f'{queue}: small balance for transfer \n{transfer}\n', flush=True)
            raise ValidationException(Transfer.Status.INSUFFICIENT_BALANCE)

        transfer.execute(gas_price=gas_price)
        transfer.save()
    elif network == 'Binance-Chain':
        if transfer.token.swap_owner_balance < 60000:  # multi-send price for 2 addresses
            print(f'{queue}: small balance for transfer \n{transfer}\n', flush=True)
            raise ValidationException(Transfer.Status.INSUFFICIENT_BALANCE)

        transfer.execute()
        transfer.save()

    if transfer.status == Transfer.Status.FAIL:
        print(f'{queue}: failed transfer \n{transfer}\n', flush=True)
        transfer.send_to_bot_queue()
    else:
        transfer.update_status()
        transfer.save()
        while transfer.status == Transfer.Status.PENDING:
            print(f'{queue}: pending transfer \n{transfer}\n', flush=True)
            print(f'{queue}: waiting {TX_STATUS_CHECK_TIMEOUT} seconds before next status check...\n', flush=True)
            time.sleep(TX_STATUS_CHECK_TIMEOUT)
            transfer.update_status()
            transfer.save()
        if transfer.status == Transfer.Status.SUCCESS:
            print(f'{queue}: successful transfer \n{transfer}\n', flush=True)
        else:
            print(f'{queue}: failed transfer after pending \n{transfer}\n', flush=True)
        transfer.send_to_bot_queue()

    timeout = NETWORKS[network]['transfer_timeout']
    print(f'{queue}: waiting {timeout} seconds before next transfer...\n', flush=True)
    time.sleep(timeout)
