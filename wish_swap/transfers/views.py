from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from rest_framework.decorators import api_view
from wish_swap.payments.models import Payment
from wish_swap.transfers.models import Transfer
'''
from wish_swap.transfers.serializers import TransferSerializer
from wish_swap.transfers.models import Transfer
from rest_framework.views import APIView
'''

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
    description='Swap status: `SUCCESS`, `IN PROCESSS`, `FAIL` and transfer hash if `SUCCESS`',
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

    if payment.validation_status != 'SUCCESS':
        return Response({'status': 'FAIL'}, status=200)

    transfer = Transfer.objects.get(payment=payment)
    status = transfer.status
    if status in ('HIGH GAS PRICE', 'WAITING FOR CONFIRM', 'SMALL TOKEN BALANCE', 'SMALL BALANCE'):
        return Response({'status': 'IN PROCESS'}, status=200)
    elif status == 'FAIL':
        return Response({'status': 'FAIL'}, status=200)
    return Response({'status': status, 'transfer_hash': transfer.tx_hash}, status=200)


'''
class TransferView(APIView):
    @swagger_auto_schema(
        operation_description="Get transfer info by payment hash\n"
                              "Transfer statuses: `SUCCESS`, `HIGH GAS PRICE`, "
                              "`FAIL` or `DECLINED` (of fee is more then token amount)",
        manual_parameters=[
            openapi.Parameter('payment_hash', openapi.IN_PATH, type=openapi.TYPE_STRING),
        ],
        responses={200: TransferSerializer(), 404: payment_not_found_response},
    )
    def get(self, request, payment_hash):
        try:
            payment = Payment.objects.get(tx_hash=payment_hash)
        except Payment.DoesNotExist:
            return Response({'detail': 'no such payment exists in db'}, 404)
        transfer = Transfer.objects.get(payment=payment)
        serializer = TransferSerializer(transfer)
        return Response(serializer.data, status=200)
'''