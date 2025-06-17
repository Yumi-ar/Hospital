#blockchain.py fonctionne 
import base64
import hashlib
import json
import time
from datetime import datetime
import datetime
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from django.contrib.auth import get_user_model
import logging

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
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()

        # Export keys
        wallet.private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()

        wallet.public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

       
        public_key_hash = hashlib.sha256(wallet.public_key.encode()).digest()
        wallet.identity = base64.b58encode(public_key_hash).decode()

        return wallet

    def sign_data(self, data: str) -> str:
        private_key = serialization.load_pem_private_key(
            self.private_key.encode(), password=None
        )
        signature = private_key.sign(
            data.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def verify_integrity(self) -> bool:
        """Vérifie que les clés du portefeuille correspondent en signant et validant un message."""
        try:
            test_message = b"integrity_check"
            signature = self.sign_data(test_message)
            return self.verify_signature(test_message, signature)
        except Exception as e:
            print(f"[!] Erreur d'intégrité du wallet: {e}")
            return False

class BlockchainTransaction:
    def __init__(self, sender, recipient, data):
        self.sender = sender
        self.recipient = recipient
        self.data = data
        self.timestamp = time.time()
        self.transaction_id = self.calculate_transaction_id()
        self.signature = None
        self.wallet_private_key = sender.private_key if sender else None

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
            private_key = serialization.load_pem_private_key(
                self.wallet_private_key.encode(),
                password=None,
                backend=default_backend()
            )
            tx_string = self.calculate_transaction_id()
            signature = private_key.sign(
                tx_string.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            self.signature = base64.b64encode(signature).decode()
            return True
        except Exception as e:
            logger.error(f"Error signing transaction: {str(e)}")
            return False

    def verify_signature(self):
        if not self.signature:
            return False
        try:
            public_key = serialization.load_pem_public_key(
                transaction.sender.public_key.encode(),
                backend=default_backend()
            )
            tx_string = self.calculate_transaction_id()
           
            public_key.verify(
                base64.b64decode(transaction.signature),
                transaction.calculate_transaction_id().encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
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
        """Charge la blockchain depuis un fichier JSON"""
        try:
            with open(filename, 'r') as f:
                chain_data = json.load(f)
                self.chain = []
                self.transaction_ids = set()

                for block_data in chain_data:
                    transactions = []
                    for tx_data in block_data["transactions"]:
                        sender = Wallet()
                        sender.identity = tx_data["sender"]  # Identité temporaire
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
                    block.timestamp = datetime.datetime.fromtimestamp(block_data["timestamp"])  # ✅ Correction ici
                    block.nonce = block_data["nonce"]
                    block.hash = block_data["hash"]

                    self.chain.append(block)

            logger.info(f"✅ Blockchain chargée avec succès ({len(self.chain)} blocs).")

        except FileNotFoundError:
            logger.warning("Fichier blockchain non trouvé, création d'un bloc genesis.")
            self.create_genesis_block()

        except Exception as e:
            logger.error(f"Erreur lors du chargement de la blockchain : {e}")
            self.create_genesis_block()
