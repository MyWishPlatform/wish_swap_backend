from telebot import TeleBot
from wish_swap.bots.models import BotSub, BotSwapMessage
from wish_swap.payments.models import Payment
from wish_swap.settings_local import NETWORKS
from wish_swap.transfers.models import Transfer


def generate_swap_status_message(p):
    hyperlink = '<a href="{url}">{text}</a>'
    p_amount = f'{p.amount / (10 ** p.token.decimals)} {p.token.symbol}'
    p_tx_url = NETWORKS[p.token.network]["explorer_url"] + p.tx_hash
    p_message = f'received {hyperlink.format(url=p_tx_url, text=p_amount)}'

    try:
        t = Transfer.objects.get(payment=p)
    except Transfer.DoesNotExist:
        return p_message

    t_amount = f'{t.amount / (10 ** t.token.decimals)} {t.token.symbol}'
    t_network = t.token.network
    t_tx_url = NETWORKS[t_network]["explorer_url"] + t.tx_hash

    if t.status in (Transfer.Status.CREATED, Transfer.Status.VALIDATION):
        return p_message
    elif t.status == Transfer.Status.PENDING:
        return f'pending: ' \
               f'{hyperlink.format(url=p_tx_url, text=p_amount)} → ' \
               f'{hyperlink.format(url=t_tx_url, text=t_amount)}'
    elif t.status == Transfer.Status.SUCCESS:
        return f'success: ' \
               f'{hyperlink.format(url=p_tx_url, text=p_amount)} → ' \
               f'{hyperlink.format(url=t_tx_url, text=t_amount)}'
    elif t.status == Transfer.Status.PROVIDER_IS_UNREACHABLE:
        return f'{p_message}. swap will be executed later due to unreachable provider in {t_network} network'
    elif t.status == Transfer.Status.HIGH_GAS_PRICE:
        return f'{p_message}. swap will be executed later due to high gas price in {t_network} network'
    elif t.status == Transfer.Status.INSUFFICIENT_TOKEN_BALANCE:
        token_balance = f'{t.token.swap_contract_token_balance / (10 ** t.token.decimals)} {t.token.symbol}'
        return f'{p_message}. please top up swap contract token balance to make a transfer, current is {token_balance}'
    elif t.status == Transfer.Status.INSUFFICIENT_BALANCE:
        decimals = NETWORKS[t_network]['decimals']
        balance = f'{t.token.swap_owner_balance / (10 ** decimals)} {NETWORKS[t_network]["symbol"]}'
        return f'{p_message}. please top up swap contract owner balance to make a transfer, current is {balance}'
    elif t.status == Transfer.Status.FAIL:
        return f'<b>fail</b>: {hyperlink.format(url=p_tx_url, text=p_amount)} → {t_amount}\n{t.tx_error}'


def parse_change_swap_status_bot_message(message):
    p = Payment.objects.get(pk=message['paymentId'])
    message = generate_swap_status_message(p)
    subs = BotSub.objects.filter(dex=p.token.dex)
    bot = TeleBot(p.token.dex.bot_token)

    for sub in subs:
        try:
            message_id = BotSwapMessage.objects.get(payment=p, sub=sub).message_id
            bot.edit_message_text(message, sub.chat_id, message_id, parse_mode='html', disable_web_page_preview=True)
        except BotSwapMessage.DoesNotExist:
            msg_id = bot.send_message(sub.chat_id, message, parse_mode='html', disable_web_page_preview=True).message_id
            BotSwapMessage(payment=p, sub=sub, message_id=msg_id).save()
