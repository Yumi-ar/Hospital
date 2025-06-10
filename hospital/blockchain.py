import hashlib
import time
import os
import binascii
import datetime
import json
import logging
from typing import Dict, List, Optional, Union
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
import Crypto.Random
from django.contrib.auth.models import User
from .models import UserWallet  # Import the UserWallet model

logger = logging.getLogger(__name__)

class Wallet:
    """Classe Wallet pour gérer les clés cryptographiques avec stockage en BDD"""
    def __init__(self, user_id=None, user=None):
        random = Crypto.Random.new().read
        self._private_key = RSA.generate(2048, random)
        self._public_key = self._private_key.publickey()
        self._signer = PKCS1_v1_5.new(self._private_key)
        self.user_id = user_id
        self.user = user  # Reference to Django User instance
        self.created_at = datetime.datetime.now()

    @property
    def identity(self):
        return binascii.hexlify(self._public_key.exportKey(format='DER')).decode('ascii')

    @property
    def public_key_pem(self):
        return self._public_key.exportKey().decode('ascii')

    @property
    def private_key_pem(self):
        return self._private_key.exportKey().decode('ascii')

    def sign_data(self, data: str) -> str:
        """Sign data with the private key"""
        try:
            h = SHA256.new(data.encode('utf-8'))
            signature = self._signer.sign(h)
            return binascii.hexlify(signature).decode('ascii')
        except Exception as e:
            logger.error(f"Error signing data: {e}")
            return ""

    @classmethod
    def load_from_db(cls, user):
        """Load wallet from UserWallet model"""
        try:
            user_wallet = UserWallet.objects.get(user=user)
            wallet = cls(user_id=str(user.id), user=user)
            wallet._private_key = RSA.importKey(user_wallet.get_private_key())
            wallet._public_key = wallet._private_key.publickey()
            wallet._signer = PKCS1_v1_5.new(wallet._private_key)
            return wallet
        except UserWallet.DoesNotExist:
            logger.error(f"No wallet found for user {user.id}")
            return None
        except Exception as e:
            logger.error(f"Error loading wallet from DB: {e}")
            return None

    def save_to_db(self):
        """Save wallet to UserWallet model"""
        try:
            user_wallet, created = UserWallet.objects.get_or_create(
                user=self.user,
                defaults={'public_key': self.public_key_pem}
            )
            user_wallet.set_private_key(self.private_key_pem)
            user_wallet.save()
            return True
        except Exception as e:
            logger.error(f"Error saving wallet to DB: {e}")
            return False

class BlockchainTransaction:
    """Classe pour représenter une transaction"""
    def __init__(self, sender, recipient, data):
        self.sender = sender
        self.recipient = recipient
        self.data = data
        self.timestamp = datetime.datetime.now()
        self.signature = None
        self.transaction_id = self._generate_id()

    def _generate_id(self):
        """Generate a unique transaction ID"""
        tx_string = f"{self.sender.identity if hasattr(self.sender, 'identity') else str(self.sender)}{self.recipient}{json.dumps(self.data, sort_keys=True)}{self.timestamp.isoformat()}"
        return hashlib.sha256(tx_string.encode('utf-8')).hexdigest()[:16]

    def to_dict(self):
        """Convertir la transaction en dictionnaire sérialisable"""
        return {
            'transaction_id': self.transaction_id,
            'sender': self.sender.identity if hasattr(self.sender, 'identity') else str(self.sender),
            'recipient': str(self.recipient),
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'signature': self.signature
        }

    def sign_transaction(self):
        """Sign the transaction with the sender's private key"""
        if isinstance(self.sender, Wallet):
            tx_dict = self.to_dict()
            tx_dict['signature'] = None  # Exclude signature from signing
            tx_string = json.dumps(tx_dict, sort_keys=True)
            self.signature = self.sender.sign_data(tx_string)
            return self.signature
        logger.error("Cannot sign transaction: sender is not a Wallet instance")
        return None

    def verify_signature(self):
        """Verify the transaction signature"""
        if not self.signature:
            return False
        try:
            tx_dict = self.to_dict()
            original_signature = tx_dict['signature']
            tx_dict['signature'] = None
            tx_string = json.dumps(tx_dict, sort_keys=True)
            public_key = RSA.importKey(self.sender.public_key_pem)
            verifier = PKCS1_v1_5.new(public_key)
            h = SHA256.new(tx_string.encode('utf-8'))
            signature_bytes = binascii.unhexlify(original_signature.encode('ascii'))
            return verifier.verify(h, signature_bytes)
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

class Block:
    """Classe Block pour la blockchain"""
    def __init__(self, index, transactions, previous_hash):
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = datetime.datetime.now()
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
    """Blockchain médicale simplifiée"""
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.transaction_ids = set()
        self.load_chain()  # Load existing chain or create genesis block

    def create_genesis_block(self):
        """Create the genesis block"""
        genesis_block = Block(0, [], "0")
        genesis_block.hash = genesis_block.compute_hash()  # Ensure genesis block has valid hash
        self.chain.append(genesis_block)
        self.save_chain()

    def add_transaction(self, transaction):
        if not transaction.sender or not transaction.recipient:
            logger.error("Transaction missing sender or recipient")
            return False
        if transaction.transaction_id in self.transaction_ids:
            logger.warning(f"Duplicate transaction ID: {transaction.transaction_id}")
            return False
        if not transaction.signature or not transaction.verify_signature():
            logger.error("Invalid or missing transaction signature")
            return False
        self.pending_transactions.append(transaction)
        self.transaction_ids.add(transaction.transaction_id)
        logger.info(f"Transaction {transaction.transaction_id} added to pending transactions")
        
        # Miner si le seuil est atteint
        if len(self.pending_transactions) >= 5:
            block = self.mine_pending_transactions("Miner")
            if block:
                logger.info(f"Block {block.index} mined with {len(block.transactions)} transactions")
        
        return True
    def mine_pending_transactions(self, miner_address):
        """Mine pending transactions"""
        if not self.pending_transactions:
            logger.info("No transactions to mine")
            return None

        logger.info(f"Mining {len(self.pending_transactions)} pending transactions")
        block = Block(
            len(self.chain),
            self.pending_transactions.copy(),
            self.chain[-1].hash if self.chain else "0"
        )

        # Proof of Work
        while block.hash[:4] != "0000":
            block.nonce += 1
            block.hash = block.compute_hash()

        self.chain.append(block)
        self.pending_transactions = []
        self.transaction_ids.update(tx.transaction_id for tx in block.transactions)
        self.save_chain()
        logger.info(f"Block {block.index} mined successfully")
        return block

    def is_chain_valid(self):
        """Check if the blockchain is valid"""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            if current.hash != current.compute_hash():
                logger.error(f"Invalid hash for block {i}")
                return False
            if current.previous_hash != previous.hash:
                logger.error(f"Broken chain link between blocks {i-1} and {i}")
                return False
        return True

    def save_chain(self, filename="blocks.json"):
        """Save the blockchain to a JSON file"""
        try:
            chain_data = []
            for block in self.chain:
                chain_data.append({
                    "index": block.index,
                    "transactions": [tx.to_dict() for tx in block.transactions],
                    "previous_hash": block.previous_hash,
                    "timestamp": block.timestamp.isoformat(),
                    "nonce": block.nonce,
                    "hash": block.hash
                })
            with open(filename, 'w') as f:
                json.dump(chain_data, f, indent=4)
            logger.info(f"Blockchain saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving blockchain: {e}")

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
                        sender = Wallet(user_id=tx_data["sender"])  # Temporary wallet for loading
                        sender._public_key = RSA.importKey(binascii.unhexlify(tx_data["sender"]))
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