import os
import sys
import time
import requests
import json
from hexbytes import HexBytes

from scanner.blockchain_common.wrapper_block import WrapperBlock
from scanner.blockchain_common.wrapper_network import WrapperNetwork
from scanner.blockchain_common.wrapper_output import WrapperOutput
from scanner.blockchain_common.wrapper_transaction import WrapperTransaction
from scanner.eventscanner.queue.pika_handler import send_to_backend
from binance_chain.exceptions import BinanceChainAPIException
from wish_swap.settings import NETWORKS

from binance_chain.http import HttpApiClient
from binance_chain.http import PeerType
from binance_chain.constants import KlineInterval
from binance_chain.environment import BinanceEnvironment
from binance_chain.node_rpc.http import HttpRpcClient





class BinNetwork(WrapperNetwork):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(BASE_DIR)
    base_dir = 'scanner/settings'

    def __init__(self, type):
        super().__init__(type)
        #Setting Binance-Chain params, testnet_env for testnet
        if NETWORKS['Binance-Chain']['scanner']['is_testnet']:
            testnet_env = BinanceEnvironment.get_testnet_env()
            self.client = HttpApiClient(env=testnet_env, request_params={"verify": False, "timeout": 60})
        else:
            self.client = HttpApiClient(request_params={"verify": False, "timeout": 60})
        peers = client.get_node_peers()
        listen_addr = peers[0]['listen_addr']
        rpc_client = HttpRpcClient(listen_addr)
        processed = []
        commited = []

    #No need to get last block number because we don't parse blocks in binance chain
    def get_last_block(self):
        pass


    def get_block(self, token, swap_address, s_time) -> WrapperBlock:
        print('BINANCE_MAINNET: scanning', flush=True)
        #try:
        #getting all transactions for last day
        client_transactions = self.client.get_transactions(address=swap_address,
                              tx_asset=token.symbol, start_time=s_time, limit=1000)
        '''except:
            #mainly for testnet, because it simultaneously breaks with timeout error
            print('Binance-Chain is falling down, falling down, falling down.... Binance-Chain is falling dowm, fuck this testnet')
            client_transactions={'total':0, 'tx':[]}
            time.sleep(2)'''

        tx_count = client_transactions['total']
        client_transactions = client_transactions['tx']
        offset = 0
        i = 0
        #getting more than 1000(max in one request) transactions if needed
        while tx_count > len(client_transactions):
            offset += 1000
            client_transactions_append = self.client.get_transactions(
                address=swap_address,
                              tx_asset=token.symbol, offset=offset, start_time=s_time, limit=1000)
            tx_count = client_transactions_append['total']
            client_transactions += client_transactions_append['tx']
            time.sleep(1)
            #emergency escape from "getting more transactions" loop
            i += 1
            if i > 100:
                print('got out of the loop')
                break
        #getting block number of last checked transaction for each token
        try:
            with open(os.path.join(self.base_dir, 'Binance-Chain', token.symbol), 'r') as file:
                max_block = file.read()
        except FileNotFoundError:
            max_block = '1'
        if len(max_block) == 0:
            max_block = '1'
        max_block = int(max_block)
        new_transactions = []
        #get new transactions
        for c_t in client_transactions:
            if c_t['blockHeight'] <= max_block:
                break
            new_transactions.append(c_t)
        transactions = []

        for t in new_transactions[::-1]:
            # check tx success and type
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

                # set max_block to highest block in transaction list
                transactions.append(transaction)
                if int(t['blockHeight']) > max_block:
                    max_block = int(t['blockHeight'])
        block = WrapperBlock('', '', '', transactions)

        #rewrite max block number
        try:
            with open(os.path.join(self.base_dir, self.type, token.symbol), 'w') as file:
                file.write(str(max_block))
            return block
        except FileNotFoundError:
            print('except creation')
            filename = os.path.join(self.base_dir, self.type)
            os.makedirs(filename, exist_ok=True)
            with open(os.path.join(self.base_dir, self.type, token.symbol), 'w') as file:
                file.write(str(max_block))
            return block

    """transfer confirmation is currently here because binance chain transfer confirmation couln't work
       normally with basic BlockEvent->pubsub->monitor logic"""
    def confirm_transfer(self, transfer):
        transaction={}
        try:
            transaction = client.get_transaction(transfer.tx_hash)
            print(f'transaction:{transaction}')
        except BinanceChainAPIException:
            transaction['ok']=False
        if transaction['ok']:
            message = {
                'transactionHash': transaction['hash'],
                'transferId': transfer.id,
                'amount': int(transfer.amount),
                'success': True,
                'status': 'COMMITTED',
            }
            send_to_backend('transfer', 'Binance-Chain', message)
