from wish_swap.payments.models import Payment
from wish_swap.settings import NETWORKS_BY_NUMBER
from wish_swap.tokens.models import Token, Dex
from wish_swap.transfers.models import Transfer
from web3 import Web3, HTTPProvider
from wish_swap.settings import NETWORKS
import requests
import json


class PaymentValidationException(Exception):
    def __init__(self, status, message=''):
        self.status = status
        self.message = message
        super().__init__(self.message)


def create_transfer_from_payment(payment):
    try:
        to_network = NETWORKS_BY_NUMBER[payment.transfer_network_number]
    except KeyError:
        raise PaymentValidationException(Payment.ValidationStatus.INVALID_NETWORK_ID)

    try:
        to_token = payment.token.dex[to_network]
    except Token.DoesNotExist:
        raise PaymentValidationException(Payment.ValidationStatus.INVALID_NETWORK)

    min_swap_amount = to_token.dex.min_swap_amount * (10 ** to_token.decimals)

    try:
        fee = to_token.fee
    except requests.exceptions.RequestException:
        raise PaymentValidationException(Payment.ValidationStatus.PROVIDER_IS_DOWN)

    if payment.amount <= fee or payment.amount < min_swap_amount:
        raise PaymentValidationException(Payment.ValidationStatus.INSUFFICIENT_AMOUNT)

    payment.validation_status = Payment.ValidationStatus.SUCCESS
    payment.save()

    transfer = Transfer(
        payment=payment,
        token=to_token,
        address=payment.transfer_address,
        amount=payment.amount - fee,
        fee_address=to_token.fee_address,
        fee_amount=fee,
        network=to_token.network,
    )
    transfer.save()
    return transfer


def parse_validate_payment_message(queue, message):
    payment = Payment.objects.get(pk=message['paymentId'])
    try:
        transfer = create_transfer_from_payment(payment)
        print(f'{queue}: payment validation success, send transfer to queue \n{transfer}\n', flush=True)
        transfer.send_to_transfers_queue()
    except PaymentValidationException as e:
        if payment.validation_status != e.status:
            payment.status = e.status
            payment.save()
            payment.send_to_bot_queue()
        print(f'{queue}: payment validation failed \n{payment}\n', flush=True)


def parse_payment(message, queue):
    network_number = message['networkNumber']
    tx_hash = message['transactionHash']
    from_address = message['address']
    to_address = message['toAddress']
    amount = message['amount']
    from_token = Token.objects.get(pk=message['tokenId'])

    if not Payment.objects.filter(tx_hash=tx_hash, token=from_token).count() > 0:
        payment = Payment(
            token=from_token,
            address=from_address,
            tx_hash=tx_hash,
            amount=amount,
            transfer_address=to_address,
            transfer_network_number=network_number,
        )
        payment.save()
        print(f'{queue}: payment saved, send to validation queue \n{payment}\n', flush=True)

        payment.send_to_validation_queue()
        payment.send_to_bot_queue()
    else:
        print(f'{queue}: tx {tx_hash} already registered\n', flush=True)


def parse_payment_manually(tx_hash, network_name, dex_name):
    dex = Dex.objects.get(name=dex_name)
    token = dex[network_name]
    if network_name in ('Ethereum', 'Binance-Smart-Chain'):
        w3 = Web3(HTTPProvider(NETWORKS[token.network]['node']))
        contract = w3.eth.contract(address=token.swap_address, abi=token.swap_abi)
        tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
        receipt = contract.events.TransferToOtherBlockchain().processReceipt(tx_receipt)
        if not receipt:
            # TODO: logging
            return

        event = receipt[0].args
        message = {
            'tokenId': token.id,
            'address': event.user,
            'transactionHash': tx_hash,
            'amount': event.amount,
            'toAddress': event.newAddress,
            'networkNumber': event.blockchain
        }
        parse_payment(message, network_name)
    elif network_name == 'Binance-Chain':
        url = f'{NETWORKS[network_name]["api-url"]}tx/{tx_hash}?format=json'
        response = requests.get(url)
        json_data = json.loads(response.text)
        data = json_data['tx']['value']['msg'][0]['value']
        memo = json_data['tx']['value']['memo'].replace(' ', '')
        to_address = data['outputs'][0]['address']
        from_address = data['inputs'][0]['address']
        symbol = data['inputs'][0]['coins'][0]['denom']
        amount = data['inputs'][0]['coins'][0]['amount']

        if from_address == token.swap_address:
            # TODO: logging
            return

        if to_address != token.swap_address:
            # TODO: logging
            return

        if symbol != token.symbol:
            # TODO: logging
            return

        message = {
            'tokenId': token.id,
            'address': from_address,
            'transactionHash': tx_hash,
            'amount': int(amount),
            'toAddress': memo[1:],
            'networkNumber': int(memo[0])
        }
        parse_payment(message, network_name)
