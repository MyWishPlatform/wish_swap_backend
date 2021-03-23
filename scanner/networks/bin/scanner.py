import os
import collections
import time

from scanner.blockchain_common.wrapper_block import WrapperBlock
from scanner.eventscanner.queue.subscribers import pub
from scanner.scanner.events.block_event import BlockEvent
from scanner.scanner.services.scanner_polling import ScannerPolling
from scanner.mywish_models.models import Dex, Token, Transfer, session
from scanner.eventscanner.queue.pika_handler import send_to_backend

class BinScanner(ScannerPolling):
    base_dir = 'scanner/settings'

    def poller(self):
        print('hello from {}'.format(self.network.type), flush=True)
        while True:
            self.polling()

    def polling(self):
        network_types = ['Binance-Chain', ]
        status=['WAITING FOR CONFIRM']
        try:
            tokens = session.query(Token).filter(getattr(Token, 'network').in_(network_types)).all()
            for token in tokens:
                swap_address = token.swap_address
                block=self.network.get_block(token, swap_address, int(time.time()*1000-604800000))
                self.process_block(block)
                time.sleep(2)
            while True:
                for token in tokens:
                    swap_address = token.swap_address
                    block = self.network.get_block(token, swap_address, int(time.time() * 1000 - 604800000))
                    self.process_block(block)
                    time.sleep(2)
                time.sleep(20)
                #disabled confirms
                '''transfers = session.query(Transfer).filter(getattr(Transfer, 'status').in_(status)).filter(getattr(Transfer, 'network').in_(network_types)).all()
                print(f'len:{len(transfers)}')
                for transfer in transfers:
                    confirm=self.network.confirm_transfer(transfer)
                    time.sleep(2)'''
                try:
                    with open(os.path.join(self.base_dir, 'Binance-Chain', 'status'), 'r') as file:
                        status = file.read()
                        if status == 'dead':
                            send_to_backend('scanner_up', 'scanner-bot', 'scanner ressurected')
                    with open(os.path.join(self.base_dir, 'Binance-Chain', 'status'), 'w') as file:
                        file.write('alive')
                except FileNotFoundError:
                    pass
                time.sleep(20)
            print('got out of the main loop')
        except Exception as e:
            #send_to_backend('scanner_crash', 'scanner-bot', 'scanner is dead')
            try:
                with open(os.path.join(self.base_dir, 'Binance-Chain', 'status'), 'r') as file:
                    status = file.read()
                    if status == 'alive':
                        write = True
                        send_to_backend('scanner_crash', 'scanner-bot', 'scanner is dead')
                    else:
                        write = False
                if write:
                    with open(os.path.join(self.base_dir, 'Binance-Chain', 'status'), 'w') as file:
                        file.write('dead')
                time.sleep(20)
            except FileNotFoundError:
                print('except creation')
                filename = os.path.join(self.base_dir, 'Binance-Chain')
                os.makedirs(filename, exist_ok=True)
                with open(os.path.join(self.base_dir, 'Binance-Chain', 'status'), 'w') as file:
                    file.write('dead')
                    send_to_backend('scanner_crash', 'scanner-bot', 'scanner is dead')
                time.sleep(20)


    def process_block(self, block: WrapperBlock):
        address_transactions = collections.defaultdict(list)
        for transaction in block.transactions:
            self._check_tx_to(transaction, address_transactions)
        block_event = BlockEvent(self.network, block, address_transactions)
        pub.sendMessage(self.network.type, block_event=block_event)

    def _check_tx_to(self, tx, addresses):
        to_address = tx.outputs[0].address

        if to_address:
            addresses[to_address.lower()].append(tx)
