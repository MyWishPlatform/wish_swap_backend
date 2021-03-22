from wish_swap.transfers.models import Transfer
from celery import shared_task


@shared_task
def push_transfers():
    transfers = Transfer.objects.filter(status__in=(Transfer.Status.HIGH_GAS_PRICE,
                                                    Transfer.Status.INSUFFICIENT_TOKEN_BALANCE,
                                                    Transfer.Status.INSUFFICIENT_BALANCE,
                                                    Transfer.Status.PROVIDER_IS_DOWN))
    if not transfers.count():
        print(f'PUSHING TRANSFERS: no transfers to push', flush=True)
        return
    print(f'PUSHING TRANSFERS: start pushing...', flush=True)
    for transfer in transfers:
        transfer.send_to_transfers_queue()
    print(f'PUSHING TRANSFERS: pushing completed', flush=True)
