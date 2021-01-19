from scanner.eventscanner.queue.pika_handler import send_to_backend
from scanner.mywish_models.models import Dex, Token, session
from scanner.scanner.events.block_event import BlockEvent
from wish_swap.settings_local import BLOCKCHAINS_BY_NUMBER, NETWORKS


class EthPaymentMonitor:

    network_types = ['Ethereum']
    event_type = 'payment'
    queue = 'Ethereum'
    #tokens = ERC20_TOKENS

    
    @classmethod
    def network(cls, model):
        s = 'network'
        return getattr(model, s)


    @classmethod
    def on_new_block_event(cls, block_event: BlockEvent):
        if block_event.network.type not in cls.network_types:
            return
        addresses = block_event.transactions_by_address.keys()
        tokens = session.query(Token).filter(cls.network(Token).in_(cls.network_types)).all()
        for token in tokens:
            swap_address = token.token_address.address.lower()
            if swap_address in addresses:
                transactions = block_event.transactions_by_address[swap_address]
                cls.handle(token, transactions, block_event.network)
        
        
    @classmethod
    def handle(cls, token, transactions, network):
        for tx in transactions:
            if token.token_address.address.lower() != tx.outputs[0].address.lower():
                continue

            processed_receipt = network.get_processed_tx_receipt(tx.tx_hash, token.symbol, token.token_address.address)
            if not processed_receipt:
                print('{}: WARNING! Can`t handle tx {}, probably we dont support this event'.format(
                    cls.network_types[0], tx.tx_hash), flush=True)
                return
            transfer_from = processed_receipt[0].args.user
            amount = processed_receipt[0].args.amount
            networkNumber = processed_receipt[0].args.blockchain
            swap_to = processed_receipt[0].args.newAddress

        
            tx_receipt = network.get_tx_receipt(tx.tx_hash)
            if tx_receipt.success==True:
                success='COMMITTED'
            else:
                success='ERROR'
            print(tx.outputs[0].raw_output_script)
            message = {
                'tokenId': token.id,
                'address': transfer_from,
                'transactionHash': tx.tx_hash,
                'amount': amount,
                'toAddress': swap_to,
                'status': success,
                'networkNumber': networkNumber
            }
            
            send_to_backend(cls.event_type, cls.queue, message)


class BSPaymentMonitor(EthPaymentMonitor):
    network_types = ['Binance-Smart-Chain']
    event_type = 'payment'
    queue = 'Binance-Smart-Chain'
    #tokens = ERC20_TOKENS
