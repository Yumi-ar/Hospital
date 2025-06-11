import hashlib
import time
import datetime
import json
import logging
from typing import Dict, List, Optional
import ecdsa
import base58
from django.contrib.auth import get_user_model
from .models import UserWallet
from copy import deepcopy

logger = logging.getLogger(__name__)
User = get_user_model()


class Wallet:
    def __init__(self, user_id=None):
        self.identity = None
        self.private_key = None
        self.public_key = None
        self.user_id = user_id

    @staticmethod
    def generate_wallet():
        wallet = Wallet()
        private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        public_key = private_key.get_verifying_key()
        wallet.private_key = private_key.to_string().hex()
        wallet.public_key = public_key.to_string().hex()
        public_key_bytes = bytes.fromhex(wallet.public_key)
        public_key_hash = hashlib.sha256(public_key_bytes).digest()
        wallet.identity = base58.b58encode(public_key_hash).decode('utf-8')
        logger.debug(f"Generated wallet: identity={wallet.identity}, private_key_len={len(bytes.fromhex(wallet.private_key))}")
        return wallet

    @classmethod
    def load_from_db(cls, user):
        from hospital.models import UserWallet
        try:
            wallet_obj = UserWallet.objects.get(user=user)
            wallet = cls(user_id=str(user.id))
            wallet.identity = wallet_obj.identity
            wallet.private_key = wallet_obj.private_key
            wallet.public_key = wallet_obj.public_key
            return wallet
        except UserWallet.DoesNotExist:
            return None


class BlockchainTransaction:
    def __init__(self, sender, recipient, data):
        self.sender = sender
        self.recipient = recipient
        self.data = data
        self.timestamp = time.time()
        self.transaction_id = self.calculate_transaction_id()
        self.signature = None
        self.wallet_private_key = sender.private_key if sender else None

    def _generate_id(self):
        """Generate a unique transaction ID"""
        tx_string = f"{self.sender.identity}{self.recipient}{json.dumps(self.data, sort_keys=True)}{self.timestamp.isoformat()}"
        return hashlib.sha256(tx_string.encode('utf-8')).hexdigest()[:16]

    def calculate_transaction_id(self):
        transaction_string = (
            f"{self.sender.identity if self.sender else None}"
            f"{self.recipient}"
            f"{json.dumps(self.data, sort_keys=True)}"
            f"{self.timestamp}"
        )
        return hashlib.sha256(transaction_string.encode()).hexdigest()

    def sign_transaction(self):
        try:
            private_key_bytes = bytes.fromhex(self.wallet_private_key)
            if len(private_key_bytes) != 32:
                logger.error(f"Invalid private key length: {len(private_key_bytes)} bytes")
                return False
            private_key = ecdsa.SigningKey.from_string(
                private_key_bytes, curve=ecdsa.SECP256k1
            )
            transaction_string = self.calculate_transaction_id()
            self.signature = private_key.sign(transaction_string.encode()).hex()
            logger.info(f"Transaction signed: {self.signature}")
            return True
        except ValueError as e:
            logger.error(f"Invalid private key format: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected signature error: {str(e)}")
            return False

    def verify_signature(self):
        """Verify the transaction signature using ECDSA"""
        if not self.signature:
            logger.error("No signature found for transaction")
            return False
        try:
            tx_dict = self.to_dict()
            original_signature = tx_dict['signature']
            tx_dict['signature'] = None
            tx_string = json.dumps(tx_dict, sort_keys=True).encode('utf-8')
            public_key = ecdsa.VerifyingKey.from_string(bytes.fromhex(self.sender.public_key))
            signature_bytes = bytes.fromhex(original_signature)
            return public_key.verify(signature_bytes, tx_string)
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    def to_dict(self):
        return {
            'sender': self.sender.identity if self.sender else None,
            'recipient': self.recipient,
            'data': self.data,
            'timestamp': self.timestamp,
            'transaction_id': self.transaction_id,
            'signature': self.signature
        }


class Block:
    def __init__(self, index, transactions, previous_hash):
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = datetime.datetime.utcnow()
        self.nonce = 0
        self.hash = self.compute_hash()

    def compute_hash(self):
        """Calculate the block hash"""
        block_string = json.dumps({
            "index": self.index,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp.isoformat(),
            "nonce": self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()


class MedicalBlockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.load_blockchain()

    def create_genesis_block(self):
        """Create the genesis block"""
        genesis_block = Block(0, [], "0")
        genesis_block.hash = genesis_block.compute_hash()  # Ensure genesis block has valid hash
        self.chain.append(genesis_block)
        self.save_blockchain()

    def load_blockchain(self):
        try:
            with open('blocks.json', 'r') as file:
                chain_data = json.load(file)
                self.chain = []
                for block_data in chain_data:
                    # Créez des objets BlockchainTransaction à partir des données de transaction
                    transactions = []
                    for tx_data in block_data.get('transactions', []):
                        # Vérifiez si tx_data['sender'] est None avant de créer un Wallet
                        sender = Wallet()
                        sender.identity = tx_data['sender']
                        tx = BlockchainTransaction(
                            sender=sender if tx_data['sender'] else None,  # Créez un objet Wallet temporaire
                            recipient=tx_data['recipient'],
                            data=tx_data['data']
                        )
                        tx.timestamp = tx_data['timestamp']
                        tx.transaction_id = tx_data['transaction_id']
                        tx.signature = tx_data['signature']
                        transactions.append(tx)

                    # Créez un objet Block à partir des données du bloc
                    block = Block(
                        index=block_data['index'],
                        transactions=transactions,
                        previous_hash=block_data['previous_hash']
                    )
                    block.timestamp = datetime.datetime.fromtimestamp(block_data['timestamp'])
                    block.hash = block_data['hash']
                    block.nonce = block_data['nonce']
                    self.chain.append(block)
                logger.info(f"Blockchain loaded with {len(self.chain)} blocks")
        except FileNotFoundError:
            logger.info("Blockchain file not found, creating genesis block")
            self.create_genesis_block()
        except Exception as e:
            logger.error(f"Error loading blockchain: {e}")
            self.create_genesis_block()

    def add_transaction(self, transaction):
        try:
            if not transaction.signature:
                logger.error("Invalid or missing transaction signature")
                return False

            if transaction.sender and transaction.sender.public_key:
                public_key_bytes = bytes.fromhex(transaction.sender.public_key)
                verifying_key = ecdsa.VerifyingKey.from_string(
                    public_key_bytes, curve=ecdsa.SECP256k1
                )
                transaction_string = transaction.calculate_transaction_id()
                signature_bytes = bytes.fromhex(transaction.signature)
                if not verifying_key.verify(signature_bytes, transaction_string.encode()):
                    logger.error("Invalid transaction signature")
                    return False
            else:
                logger.warning("Skipping signature verification for transaction with no sender or public key.")

            self.pending_transactions.append(transaction)  # Ajoutez l'objet transaction directement
            logger.info(f"Transaction added: {transaction.transaction_id}")
            return True
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            return False

    def mine_pending_transactions(self, miner_address):
        if not self.pending_transactions:
            return None

        # Créez un nouvel objet Block
        new_block = Block(
            index=len(self.chain),
            transactions=self.pending_transactions,
            previous_hash=self.chain[-1].hash if self.chain else "0"  # Utilisez l'attribut hash de l'objet Block précédent
        )
        new_block.hash = new_block.compute_hash()

        self.chain.append(new_block)
        self.pending_transactions = []
        self.save_blockchain()
        logger.info(f"Block {new_block.index} mined successfully")
        return new_block

    def is_chain_valid(self):
        """Check if the blockchain is valid"""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                logger.error(f"Invalid hash for block {i}")
                return False
            if current.previous_hash != previous.hash:
                logger.error(f"Broken chain link between blocks {i - 1} and {i}")
                return False
        return True

    def save_blockchain(self):
        # Convertissez les objets Block en dictionnaires avant de les sérialiser
        chain_data = [
            {
                'index': block.index,
                'timestamp': block.timestamp.timestamp(),  # Convertissez datetime en timestamp
                'transactions': [tx.to_dict() for tx in block.transactions],
                'previous_hash': block.previous_hash,
                'hash': block.hash,
                'nonce': block.nonce
            }
            for block in self.chain
        ]
        with open('blocks.json', 'w') as file:
            json.dump(chain_data, file, indent=4)

    def load_chain(self, filename="blocks.json"):
        """Load the blockchain from a JSON file"""
        try:
            with open(filename, 'r') as f:
                chain_data = json.load(f)
                self.chain = []
                self.transaction_ids = set()
                for block_data in chain_data:
                    transactions = []
                    for tx_data in block_data["transactions"]:
                        sender = Wallet()
                        sender.identity = tx_data["sender"]  # Temporary wallet for loading
                        tx = BlockchainTransaction(
                            sender=sender,
                            recipient=tx_data["recipient"],
                            data=tx_data["data"]
                        )
                        tx.transaction_id = tx_data["transaction_id"]
                        tx.timestamp = datetime.datetime.fromisoformat(tx_data["timestamp"])
                        tx.signature = tx_data.get("signature")
                        transactions.append(tx)
                        self.transaction_ids.add(tx.transaction_id)
                    block = Block(
                        block_data["index"],
                        transactions,
                        block_data["previous_hash"]
                    )
                    block.timestamp = datetime.datetime.fromisoformat(block_data["timestamp"])
                    block.nonce = block_data["nonce"]
                    block.hash = block_data["hash"]
                    self.chain.append(block)
            logger.info(f"Blockchain loaded with {len(self.chain)} blocks")
        except FileNotFoundError:
            logger.info("Blockchain file not found, creating genesis block")
            self.create_genesis_block()
        except Exception as e:
            logger.error(f"Error loading blockchain: {e}")
            self.create_genesis_block()
