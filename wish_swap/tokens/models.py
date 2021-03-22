import requests
from django.db import models
from encrypted_fields import fields
from requests_http_signature import HTTPSignatureAuth
from web3 import Web3, HTTPProvider
from wish_swap.settings import NETWORKS, GAS_LIMIT, REMOTE_SIGN_URL, SECRET_KEY, SECRET_KEY_ID
from wish_swap.transfers.binance_chain_api import get_balance


class Dex(models.Model):
    name = models.CharField(max_length=100, primary_key=True)
    min_swap_amount = models.IntegerField()
    bot_token = models.CharField(max_length=100, default='', primary_key=True)

    def __getitem__(self, network):
        return Token.objects.get(dex=self, network=network)


class TokenMethodException(Exception):
    pass


class Token(models.Model):
    dex = models.ForeignKey('tokens.Dex', on_delete=models.CASCADE, related_name='tokens')
    token_address = models.CharField(max_length=100, default='', blank=True)
    token_abi = models.JSONField(blank=True, null=True, default=None)
    swap_address = models.CharField(max_length=100)
    swap_owner = models.CharField(max_length=100, default='', blank=True)
    swap_abi = models.JSONField(blank=True, null=True, default=None)
    swap_secret = fields.EncryptedTextField(default='', blank=True)  # private key for Ethereum-like, mnemonic for Binance-Chain
    _fee_address = models.CharField(max_length=100, default='', blank=True)
    _fee = models.DecimalField(max_digits=100, decimal_places=0, blank=True, null=True, default=None)
    decimals = models.IntegerField()
    symbol = models.CharField(max_length=50)
    network = models.CharField(max_length=100)
    is_original = models.BooleanField(default=False)
    remote_sign = models.BooleanField(default=False)

    @property
    def fee_address(self):
        if self.network in ('Ethereum', 'Binance-Smart-Chain'):
            return self.contract_read_function_value('swap', 'feeAddress')
        elif self.network == 'Binance-Chain':
            return self._fee_address
        else:
            raise TokenMethodException('Invalid network')

    @property
    def fee(self):
        if self.network in ('Ethereum', 'Binance-Smart-Chain'):
            num = self.contract_read_function_value('swap', 'numOfThisBlockchain')
            fee = self.contract_read_function_value('swap', 'feeAmountOfBlockchain', num)
            return fee
        elif self.network == 'Binance-Chain':
            return int(self._fee)
        else:
            raise TokenMethodException('Invalid network')

    def contract_read_function_value(self, contract_type, func_name, *args):
        w3 = Web3(HTTPProvider(NETWORKS[self.network]['node']))
        if contract_type == 'token':
            address = self.token_address
            abi = self.token_abi
        elif contract_type == 'swap':
            address = self.swap_address
            abi = self.swap_abi
        else:
            raise TokenMethodException('Invalid contract type')

        contract = w3.eth.contract(address=address, abi=abi)
        return getattr(contract.functions, func_name)(*args).call()

    def execute_swap_contract_function(self, func_name, gas_price=None, *args):
        network = NETWORKS[self.network]
        w3 = Web3(HTTPProvider(network['node']))
        tx_params = {
            'nonce': w3.eth.getTransactionCount(self.swap_owner, 'pending'),
            'gasPrice': gas_price or w3.eth.gasPrice,
            'gas': GAS_LIMIT,
        }
        contract = w3.eth.contract(address=self.swap_address, abi=self.swap_abi)
        func = getattr(contract.functions, func_name)(*args)
        initial_tx = func.buildTransaction(tx_params)
        if self.remote_sign:
            auth = HTTPSignatureAuth(key=SECRET_KEY, key_id=SECRET_KEY_ID)
            initial_tx['from'] = self.swap_owner
            response = requests.post(REMOTE_SIGN_URL, auth=auth, json=initial_tx)
            signed_tx = response.json()['signed_tx']
        else:
            signed_tx = w3.eth.account.sign_transaction(initial_tx, self.swap_secret).rawTransaction
        tx_hash = w3.eth.sendRawTransaction(signed_tx)
        tx_hex = tx_hash.hex()
        return tx_hex

    @property
    def swap_contract_token_balance(self):
        if self.network in ('Ethereum', 'Binance-Smart-Chain'):
            return self.contract_read_function_value('token', 'balanceOf', self.swap_address)
        elif self.network == 'Binance-Chain':
            return int(get_balance(self.swap_address, self.symbol) * (10 ** self.decimals))
        else:
            raise TokenMethodException('Invalid network')

    @property
    def swap_owner_balance(self):
        if self.network in ('Ethereum', 'Binance-Smart-Chain'):
            network = NETWORKS[self.network]
            w3 = Web3(HTTPProvider(network['node']))
            checksum_address = Web3.toChecksumAddress(self.swap_owner)
            return w3.eth.get_balance(checksum_address)
        elif self.network == 'Binance-Chain':
            return int(get_balance(self.swap_address, 'BNB') * (10 ** 8))
        else:
            raise TokenMethodException('Invalid network')
