from django.db import models
from web3 import Web3, HTTPProvider
from web3.exceptions import TransactionNotFound
from wish_swap.settings import NETWORKS, GAS_LIMIT
from wish_swap.transfers.binance_chain_api import BinanceChainInterface, get_tx_info
import rabbitmq


class Transfer(models.Model):
    payment = models.ForeignKey('payments.Payment', on_delete=models.CASCADE)
    token = models.ForeignKey('tokens.Token', on_delete=models.CASCADE)

    address = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=100, decimal_places=0)

    fee_address = models.CharField(max_length=100)
    fee_amount = models.DecimalField(max_digits=100, decimal_places=0)

    tx_hash = models.CharField(max_length=100)
    tx_error = models.TextField(default='')
    status = models.CharField(max_length=50, default='WAITING FOR TRANSFER')
    network = models.CharField(max_length=100)

    def __str__(self):
        symbol = self.token.symbol
        return (f'\taddress: {self.address}\n'
                f'\tamount: {self.amount / (10 ** self.token.decimals)} {symbol}\n'
                f'\tfee address: {self.fee_address}\n'
                f'\tfee amount: {self.fee_amount / (10 ** self.token.decimals)} {symbol}\n'
                f'\tnetwork: {self.network}\n'
                f'\tstatus: {self.status}\n'
                f'\ttx hash: {self.tx_hash}\n'
                f'\ttx error: {self.tx_error}')

    def _binance_transfer(self):
        bnbcli = BinanceChainInterface()
        bnbcli.add_key('key', 'password', self.token.swap_secret)
        transfers = {self.address: self.amount, self.fee_address: self.fee_amount}
        transfer_data = bnbcli.multi_send('key', 'password', self.token.symbol, transfers)
        bnbcli.delete_key('key', 'password')
        return transfer_data

    def update_status(self):
        if self.status != 'PENDING':
            return
        if self.network in ('Ethereum', 'Binance-Smart-Chain'):
            network = NETWORKS[self.token.network]
            w3 = Web3(HTTPProvider(network['node']))
            try:
                receipt = w3.eth.getTransactionReceipt(self.tx_hash)
                if receipt['status'] == 1:
                    self.status = 'SUCCESS'
                else:
                    self.status = 'FAIL'
                self.save()
            except TransactionNotFound:
                pass
        elif self.network == 'Binance-Chain':
            tx_info = get_tx_info(self.tx_hash)
            if tx_info:
                if tx_info['ok']:
                    self.status = 'SUCCESS'
                else:
                    self.status = 'FAIL'
                self.save()

    def execute(self):
        if self.token.network in ('Ethereum', 'Binance-Smart-Chain'):
            try:
                self.tx_hash = self.token.execute_swap_contract_function(
                    'transferToUserWithFee', Web3.toChecksumAddress(self.address), self.amount)
                self.status = 'PENDING'
            except Exception as e:
                self.tx_error = repr(e)
                self.status = 'FAIL'
            self.save()
        elif self.token.network == 'Binance-Chain':
            is_ok, data = self._binance_transfer()
            if is_ok:
                self.tx_hash = data
                self.status = 'PENDING'
            else:
                self.tx_error = data
                self.status = 'FAIL'
            self.save()

    def send_to_queue(self, queue):  # queue is 'transfers' / 'bot'
        message = {'transferId': self.id, 'status': 'COMMITTED'}
        type = 'transfer' if queue == 'bot' else 'execute_transfer'
        rabbitmq.publish_message(f'{self.network}-{queue}', type, message)
