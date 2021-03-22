from wish_swap.transfers.models import Transfer
from wish_swap.payments.models import Payment
from celery import shared_task


@shared_task
def push_transfers_and_payments():
    transfers = Transfer.objects.filter(status__in=(Transfer.Status.HIGH_GAS_PRICE,
                                                    Transfer.Status.INSUFFICIENT_TOKEN_BALANCE,
                                                    Transfer.Status.INSUFFICIENT_BALANCE,
                                                    Transfer.Status.PROVIDER_IS_DOWN))

    for transfer in transfers:
        transfer.send_to_transfers_queue()
    print(f'{transfers.count()} transfers pushed', flush=True)

    payments = Payment.objects.filter(validation_status=Payment.ValidationStatus.PROVIDER_IS_DOWN)

    for payments in payments:
        payments.send_to_validation_queue()
    print(f'{payments.count()} payments pushed', flush=True)
