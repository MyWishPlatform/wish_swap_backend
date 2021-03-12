from django.db import models
from encrypted_fields import fields
from web3 import Web3, HTTPProvider
from wish_swap.settings import NETWORKS, GAS_LIMIT


class Dex(models.Model):
    name = models.CharField(max_length=100, primary_key=True)

    def __getitem__(self, network):
        return Token.objects.get(dex=self, network=network)


class Token(models.Model):
    dex = models.ForeignKey('tokens.Dex', on_delete=models.CASCADE, related_name='tokens')
    token_address = models.CharField(max_length=100, default='', blank=True)
    token_abi = models.JSONField(blank=True, null=True, default=None)
    swap_address = models.CharField(max_length=100)
    swap_owner = models.CharField(max_length=100, default='', blank=True)
    swap_abi = models.JSONField(blank=True, null=True, default=None)
    swap_secret = fields.EncryptedTextField(default='', blank=True)  # private key for Ethereum-like, mnemonic for Binance-Chain
    fee_address = models.CharField(max_length=100)
    _fee = models.IntegerField(null=True, default=True)
    decimals = models.IntegerField()
    symbol = models.CharField(max_length=50)
    network = models.CharField(max_length=100)
    is_original = models.BooleanField(default=False)

    @property
    def fee(self):
        if self.network in ('Ethereum', 'Binance-Smart-Chain'):
            num = self.swap_contract_read_function_value('numOfThisBlockchain')
            raw_fee = self.swap_contract_read_function_value('feeAmountOfBlockchain', num)
            return raw_fee // 10 ** self.decimals
        else:
            return self._fee

    def swap_contract_read_function_value(self, func_name, *args):
        w3 = Web3(HTTPProvider(NETWORKS[self.network]['node']))
        contract = w3.eth.contract(address=self.swap_address, abi=self.swap_abi)
        return getattr(contract.functions, func_name)(*args).call()

    def execute_swap_contract_function(self, func_name, *args):
        network = NETWORKS[self.network]
        w3 = Web3(HTTPProvider(network['node']))
        tx_params = {
            'nonce': w3.eth.getTransactionCount(self.swap_owner, 'pending'),
            'gasPrice': w3.eth.gasPrice,
            'gas': GAS_LIMIT,
        }
        contract = w3.eth.contract(address=self.swap_address, abi=self.swap_abi)
        func = getattr(contract.functions, func_name)(*args)
        initial_tx = func.buildTransaction(tx_params)
        signed_tx = w3.eth.account.signTransaction(initial_tx, self.swap_secret)
        tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
        tx_hex = tx_hash.hex()
        return tx_hex
