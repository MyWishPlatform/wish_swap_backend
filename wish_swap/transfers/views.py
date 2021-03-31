from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from rest_framework.decorators import api_view
from wish_swap.payments.models import Payment
from wish_swap.transfers.models import Transfer


payment_not_found_response = openapi.Response(
    description='response if no such payment exists in db',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'detail': openapi.Schema(type=openapi.TYPE_STRING),
        },
    )
)

swap_status_response = openapi.Response(
    description='Swap status: `SUCCESS`, `IN_PROCESSS`, `FAIL` and transfer hash if available',
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'status': openapi.Schema(type=openapi.TYPE_STRING),
            'transfer_hash': openapi.Schema(type=openapi.TYPE_STRING),
        },
    )
)


@swagger_auto_schema(
    method='get',
    operation_description='Get transfer info by payment hash',
    manual_parameters=[
        openapi.Parameter('payment_hash', openapi.IN_PATH, type=openapi.TYPE_STRING),
    ],
    responses={200: swap_status_response, 404: payment_not_found_response}
)
@api_view(http_method_names=['GET'])
def swap_status_view(request, payment_hash):
    try:
        payment = Payment.objects.get(tx_hash=payment_hash)
    except Payment.DoesNotExist:
        return Response({'detail': 'no such payment exists in db'}, 404)

    if payment.validation in (Payment.Validation.PROVIDER_IS_UNREACHABLE, Payment.Validation.WAITING_FOR):
        return Response({'status': 'IN_PROCESS'}, status=200)
    if payment.validation != Payment.Validation.SUCCESS:
        return Response({'status': 'FAIL'}, status=200)

    transfer = Transfer.objects.get(payment=payment)
    status = transfer.status

    if status in (
            Transfer.Status.HIGH_GAS_PRICE,
            Transfer.Status.CREATED,
            Transfer.Status.VALIDATION,
            Transfer.Status.PROVIDER_IS_UNREACHABLE,
            Transfer.Status.INSUFFICIENT_TOKEN_BALANCE,
            Transfer.Status.INSUFFICIENT_BALACE):
        return Response({'status': 'IN_PROCESS'}, status=200)
    if status == Transfer.Status.PENDING:
        return Response({'status': 'IN_PROCESS', 'transfer_hash': transfer.tx_hash}, status=200)
    if status == Transfer.Status.FAIL:
        return Response({'status': 'FAIL'}, status=200)

    return Response({'status': 'SUCCESS', 'transfer_hash': transfer.tx_hash}, status=200)
