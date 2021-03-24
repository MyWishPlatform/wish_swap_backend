from subprocess import Popen, PIPE
import json
import requests
from wish_swap.settings import NETWORKS


class BinanceChainInterface:
    def __init__(self):
        self.network = NETWORKS['Binance-Chain']

    def add_key(self, key, password, mnemonic):
        command_list = [self.network['cli'], 'keys', 'add', key, '--recover']
        is_ok, stdout, stderr = self._execute_command_line_command(command_list, [password, mnemonic])
        if not is_ok:
            return is_ok, stderr
        return is_ok, stdout

    def delete_key(self, key, password):
        command_list = [self.network['cli'], 'keys', 'delete', key]
        is_ok, stdout, stderr = self._execute_command_line_command(command_list, [password])
        if not is_ok:
            return is_ok, stderr
        return is_ok, stdout

    def multi_send(self, key, password, symbol, transfers):
        command_list = [
            self.network['cli'], 'token', 'multi-send',
            '--from', key,
            '--chain-id', self.network['chain-id'],
            '--node', self.network['node'],
            '--transfers',
            self._generate_transfers_info(transfers, symbol),
            '--json',
        ]
        is_ok, stdout, stderr = self._execute_command_line_command(command_list, [password])
        if not is_ok:
            return is_ok, stderr
        tx_hash = json.loads(stdout)['TxHash']
        return is_ok, tx_hash

    @staticmethod
    def _generate_transfers_info(transfers, symbol):
        result = '['
        for address, amount in transfers.items():
            result += '{' + f'"to":"{address}","amount":"{amount}:{symbol}"' + '},'
        result = result[:-1] + ']'
        return result

    @staticmethod
    def _execute_command_line_command(command_list, inputs):
        process = Popen(command_list, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        for input in inputs:
            process.stdin.write((input + '\n').encode())
            process.stdin.flush()
        stdout, stderr = process.communicate()
        return process.returncode == 0, stdout.decode(), stderr.decode()


def get_tx_info(tx_hash):
    url = f'{NETWORKS["Binance-Chain"]["api-url"]}tx/{tx_hash}?format=json'
    response = requests.get(url)
    return json.loads(response.text)


def get_balance(address, symbol):
    url = f'{NETWORKS["Binance-Chain"]["api-url"]}account/{address}?format=json'
    response = requests.get(url)

    balances = response.json()['balances']
    for balance in balances:
        if balance['symbol'] == symbol:
            return float(balance['free'])

    return None
