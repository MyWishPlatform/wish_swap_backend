from django.db import models
from wish_swap.settings import NETWORKS, GAS_LIMIT
from web3 import Web3, HTTPProvider
from wish_swap.tokens.swap_contract_abi import SWAP_CONTRACT_ABI
from wish_swap.transfers.bnbcli_api import Bnbcli


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

    def _swap_contract_transfer(self):
        network = NETWORKS[self.token.network]
        w3 = Web3(HTTPProvider(network['node']))
        tx_params = {
            'nonce': w3.eth.getTransactionCount(self.token.swap_contract.owner_address, 'pending'),
            'gasPrice': w3.eth.gasPrice,
            'gas': GAS_LIMIT,
        }
        contract = w3.eth.contract(address=self.token.swap_contract.address, abi=SWAP_CONTRACT_ABI)
        checksum_address = Web3.toChecksumAddress(self.address)
        func = contract.functions.transferToUserWithFee(checksum_address, self.token_amount, self.fee_amount)
        initial_tx = func.buildTransaction(tx_params)
        signed_tx = w3.eth.account.signTransaction(initial_tx, self.token.swap_contract.owner_private)
        tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
        tx_hex = tx_hash.hex()
        return tx_hex

    def _binance_transfer(self):

        key = self.token.swap_address.bnbcli_key
        password = self.token.swap_address.bnbcli_password
        transfers = {self.address: self.amount, self.fee_address: self.fee_amount}
        return Bnbcli().multi_send(key, password, self.token.symbol, transfers)

    def execute(self):
        if self.token.network in ('Ethereum', 'Binance-Smart-Chain'):
            try:
                self.tx_hash = self._swap_contract_transfer()
                self.status = 'WAITING FOR CONFIRM'
            except Exception as e:
                self.tx_error = repr(e)
                self.status = 'FAIL'
            self.save()
        elif self.token.network == 'Binance-Chain':
            is_ok, data = self._binance_transfer()
            if is_ok:
                self.tx_hash = data
                self.status = 'WAITING FOR CONFIRM'
            else:
                self.tx_error = data
                self.status = 'FAIL'
            self.save()




