import collections
import time

from scanner.blockchain_common.wrapper_block import WrapperBlock
from scanner.eventscanner.queue.subscribers import pub
from scanner.scanner.events.block_event import BlockEvent
from scanner.scanner.services.scanner_polling import ScannerPolling
from mywish_models.models import Dex, Token, session

class BinScanner(ScannerPolling):

    network_types=['Binance-Chain',]

    @classmethod
    def network(cls, model):
        s = 'network'
        return getattr(model, s)

    def polling(self):
        tokens = session.query(Token).filter(cls.network(Token).in_(network_types)).all()
        for token in tokens
            block=self.network.get_block(token, int(time.time()*1000-604800000))
            self.process_block(block)
            time.sleep(2)
            while True:
                for token in tokens:
                    block = self.network.get_block(token, int(time.time() * 1000 - 604800000))
                    self.process_block(block)
                    time.sleep(2)
                time.sleep(120)
            print('got out of the main loop')

    
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
