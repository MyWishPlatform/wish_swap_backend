from wish_swap.payments.models import Payment
from wish_swap.settings import NETWORKS_BY_NUMBER
from wish_swap.tokens.models import Token
from wish_swap.transfers.models import Transfer


def parse_payment(message):
    network_number = message['networkNumber']
    try:
        to_network = NETWORKS_BY_NUMBER[network_number]
    except KeyError:
        print(f'parsing payment: Network associated with number {network_number} doesn`t exist!', flush=True)

    tx_hash = message['transactionHash']
    from_address = message['address']
    to_address = message['toAddress']
    amount = message['amount']
    from_token = Token.objects.get(message['tokenId'])

    if not Payment.objects.filter(tx_hash=tx_hash, token=from_token).count() > 0:
        payment = Payment(address=from_address, tx_hash=tx_hash, token=from_token, amount=amount)
        payment.save()
        print(f'parsing payment: Payment {payment.tx_hash} from {payment.address} '
              f'for {amount / from_token.decimals} {from_token.symbol} successfully saved', flush=True)

        try:
            to_token = from_token.dex[to_network]
        except Token.DoesNotExist:
            print(f'parsing payment: Matching token doesn`t exist in {to_network} network!', flush=True)
            return

        fee_amount = to_token.fee * (10 ** to_token.decimals)

        transfer = Transfer(
            payment=payment,
            token=to_token,
            address=to_address,
            amount=amount - fee_amount,
            fee_address=to_token.fee_address,
            fee_amount=amount-fee_amount,
        )
        transfer.save()
        transfer.execute()
        transfer.save()

        if transfer.status == 'FAIL':
            print(f'parsing payment: Transfer failed with error {transfer.tx_error}', flush=True)
        else:
            print(f'parsing payment: Successful transfer {transfer.tx_hash} to {transfer.address} '
                  f'for {transfer.amount / transfer.token.decimals} {transfer.token.symbol}', flush=True)

    else:
        print(f'parsing payment: Tx {tx_hash} already registered', flush=True)
