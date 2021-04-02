from wish_swap.bots.models import BotSub, BotSwapMessage
from wish_swap.payments.models import Payment
from wish_swap.settings_local import NETWORKS
from wish_swap.transfers.models import Transfer


def generate_swap_status_message(p):
    p_amount = p.amount / (10 ** p.token.decimals)
    p_symbol = p.token.symbol
    p_network = p.token.network
    p_tx_url = NETWORKS[p_network]["explorer_url"] + p.tx_hash
    p_message = f'Received <a href="{p_tx_url}">{p_amount} {p_symbol}</a>'

    try:
        transfer = Transfer.objects.get(payment=p)
    except Transfer.DoesNotExist:
        return p_message

    t_amount = transfer.amount / (10 ** transfer.token.decimals)
    t_symbol = transfer.token.symbol
    t_network = transfer.token.network
    t_tx_url = NETWORKS[t_network]["explorer_url"] + transfer.tx_hash

    if transfer.status in (Transfer.Status.CREATED, Transfer.Status.VALIDATION):
        return p_message
    elif transfer.status == Transfer.Status.PROVIDER_IS_UNREACHABLE:
        return f'{p_message}. swap will be executed later due to unreachable provider in {t_network} network'
    elif transfer.status == Transfer.Status.SUCCESS:
        return f'successful swap: <a href="{p_tx_url}">{p_amount} {p_symbol}</a> > <a href="{t_tx_url}">{t_amount} {t_symbol}</a>'
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


def parse_change_swap_status_bot_message(message):
    p = Payment.objects.get(pk=message['paymentId'])
    message = generate_swap_status_message(p)
    subs = BotSub.objects.filter(dex=p.token.dex)
    bot = p.token.dex.bot

    for sub in subs:
        try:
            message_id = BotSwapMessage.objects.get(payment=p, sub=sub).message_id
            bot.edit_message_text(message, sub.chat_id, message_id, parse_mode='html', disable_web_page_preview=True)
        except BotSwapMessage.DoesNotExist:
            msg_id = bot.send_message(sub.chat_id, message, parse_mode='html', disable_web_page_preview=True).message_id
            BotSwapMessage(payment=p, sub=sub, message_id=msg_id).save()
            return
