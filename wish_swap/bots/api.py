from wish_swap.settings_local import NETWORKS
from wish_swap.transfers.models import Transfer


def generate_bot_message(payment):
    p_amount = payment.amount / (10 ** payment.token.decimals)
    p_symbol = payment.token.symbol
    p_message = f'received {p_amount} {p_symbol}'
    try:
        transfer = Transfer.objects.get(payment=payment)
    except Transfer.DoesNotExist:
        return p_message

    t_amount = transfer.amount / (10 ** transfer.token.decimals)
    t_symbol = transfer.token.symbol
    t_network = transfer.token.network

    if transfer.status == Transfer.Status.PROVIDER_IS_UNREACHABLE:
        return f'{p_message}. swap will be executed later due to unreachable provider in {t_network} network'
    elif transfer.status == Transfer.Status.SUCCESS:
        return f'successful swap: {p_amount} {p_symbol} -> {t_amount} {t_symbol}'
    elif transfer.status == Transfer.Status.HIGH_GAS_PRICE:
        return f'{p_message}. swap will be executed later due to high gas price in {t_network} network'
    elif transfer.status == Transfer.Status.INSUFFICIENT_TOKEN_BALANCE:
        token_balance = transfer.token.swap_contract_token_balance / (10 ** transfer.token.decimals)
        return f'{p_message}. please top up swap contract token balance to make a transfer, current is {token_balance} {t_symbol}'
    elif transfer.status == Transfer.Status.INSUFFICIENT_BALANCE:
        decimals = NETWORKS[t_network]['decimals']
        balance = transfer.token.swap_owner_balance / (10 ** decimals)
        symbol = NETWORKS[t_network]['symbol']
        return f'{p_message}. please top up swap contract owner balance to make a transfer, current is {balance} {symbol}'
    elif transfer.status == Transfer.Status.FAIL:
        return f'failed swap: {p_amount} {p_symbol} -> {t_amount} {t_symbol} ({transfer.tx_error})'
