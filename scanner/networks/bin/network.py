import os
import sys
import time
import requests
import json
from hexbytes import HexBytes

from scanner.blockchain_common.eth_tokens import erc20_abi
from scanner.blockchain_common.wrapper_block import WrapperBlock
from scanner.blockchain_common.wrapper_network import WrapperNetwork
from scanner.blockchain_common.wrapper_output import WrapperOutput
from scanner.blockchain_common.wrapper_transaction import WrapperTransaction
from scanner.blockchain_common.wrapper_transaction_receipt import WrapperTransactionReceipt
from wish_swap.settings_local import NETWORKS

from binance_chain.http import HttpApiClient
from binance_chain.http import PeerType
from binance_chain.constants import KlineInterval
from binance_chain.environment import BinanceEnvironment
from binance_chain.node_rpc.http import HttpRpcClient

client = HttpApiClient(request_params={"verify": False, "timeout": 60})
client = HttpApiClient()
testnet_env = BinanceEnvironment.get_testnet_env()
client = HttpApiClient(env=testnet_env, request_params={"verify": False, "timeout": 60})
peers = client.get_node_peers()
listen_addr = peers[0]['listen_addr']
rpc_client = HttpRpcClient(listen_addr)
processed = []
commited = []

class BinNetwork(WrapperNetwork):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(BASE_DIR)
    base_dir = 'scanner/settings'

    def __init__(self, type):
        super().__init__(type)

    def get_last_block(self):
        pass

    def get_block(self, token, s_time) -> WrapperBlock:
        print('BINANCE_MAINNET: scanning', flush=True)
        client_transactions = client.get_transactions(address=token.swap_address.address,
                              tx_asset=token.symbol, start_time=s_time, limit=1000)
        tx_count = client_transactions['total']
        print(tx_count, flush=True)
        client_transactions = client_transactions['tx']
        offset = 0
        i = 0
        while tx_count > len(client_transactions):
            offset += 1000
            client_transactions_append = client.get_transactions(
                address=token.swap_address.address,
                              tx_asset=token.symbol, offset=offset, start_time=s_time, limit=1000)
            tx_count = client_transactions_append['total']
            client_transactions += client_transactions_append['tx']
            time.sleep(1)
            i += 1
            if i > 100:
                print('got out of the loop')
                break
        with open(os.path.join(self.base_dir, 'BINANCE_MAINNET'), 'r') as file:
            max_block = file.read()
        if len(max_block) == 0:
            max_block = 0
        max_block = int(max_block)
        new_transactions = []
        for c_t in client_transactions:
            if c_t['blockHeight'] <= max_block:
                break
            new_transactions.append(c_t)
        transactions = []
        for t in new_transactions[::-1]:
            if t['code'] == 0 and t['txType'] == 'TRANSFER':
                output = WrapperOutput(
                    t['txHash'],
                    t['txAsset'],
                    t['toAddr'],
                    t['value'],
                    t['memo']
                )
                transaction = WrapperTransaction(
                    t['txHash'],
                    t['fromAddr'],
                    [output],
                    False,
                    ""
                )

                transactions.append(transaction)
                if int(t['blockHeight']) > max_block:
                    max_block = int(t['blockHeight'])
        block = WrapperBlock('', '', '', transactions)

        with open(os.path.join(self.base_dir, self.type), 'w') as file:
            file.write(str(max_block))
        return block
