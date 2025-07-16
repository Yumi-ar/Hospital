import os
import json
import time
import uuid
import hashlib
import binascii
import base64
import datetime
from Crypto.PublicKey import RSA
from Crypto import Random
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
import logging


# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DIFFICULTY = "00"  # Difficulté ajustable


class Wallet:
    def __init__(self):
        random = Random.new().read
        self._private_key = RSA.generate(2048, random)
        self._public_key = self._private_key.publickey()
        self._signer = PKCS1_v1_5.new(self._private_key)

    @property
    def identity(self):
        pub_key_der = self._public_key.export_key(format='DER')
        return hashlib.sha256(pub_key_der).hexdigest()
    
    @property
    def public_key_pem(self):
        return self._public_key.export_key(format='PEM').decode('utf-8') 
    
    def to_wallet_dict(self, user_id, filename="wallet.json"):
        """Sauvegarde le wallet dans un fichier JSON"""
        wallet_data = {
            'public_key': self.public_key_pem, 
            'identity': self.identity,
            'user_id': str(user_id) if user_id is not None else None
        }
       
        existing_wallets = []
        if os.path.exists(filename):
            with open(filename, "r") as f:
                try:
                    existing_wallets = json.load(f)
                except json.JSONDecodeError:
                    existing_wallets = []

        existing_wallets.append(wallet_data)

        with open(filename, "w") as f:
            json.dump(existing_wallets, f, indent=4)

    @classmethod
    def load_wallet(cls, user_or_identity, filename="wallet.json"):
        try:
            with open(filename, 'r') as f:
                wallets = json.load(f)

            for w in wallets:
                if hasattr(user_or_identity, 'id'):
                    if str(w.get("user_id")) == str(user_or_identity.id):
                        public_key_pem = w.get("public_key")
                        wallet = cls.__new__(cls)
                        wallet._private_key = None
                        wallet._public_key = RSA.import_key(public_key_pem)
                        return wallet
                elif str(w.get("user_id")) == str(user_or_identity):
                    public_key_pem = w.get("public_key")
                    wallet = cls.__new__(cls)
                    wallet._private_key = None
                    wallet._public_key = RSA.import_key(public_key_pem)
                    return wallet
                elif str(w.get("identity")) == str(user_or_identity):
                    public_key_pem = w.get("public_key")
                    wallet = cls.__new__(cls)
                    wallet._private_key = None
                    wallet._public_key = RSA.import_key(public_key_pem)
                    return wallet
        except FileNotFoundError:
            logger.error("Fichier wallet.json introuvable.")
        return None


class Transaction:
    def __init__(self, sender, recipient, data):
        self.sender = sender
        self.recipient = recipient
        self.data = data or {}
        self.timestamp = time.time()
        self.transaction_id = str(uuid.uuid4())
        self.signature = None

    

    def sign_transaction(self):
        """Signe la transaction en chargeant la clé privée si nécessaire"""
        try:
            if not hasattr(self.sender, '_private_key') or not self.sender._private_key:
                sender_identity = self.sender.identity if hasattr(self.sender, 'identity') else self.sender
                private_key = self.sender._private_key
                if not private_key:
                    raise ValueError(f"Clé privée introuvable pour l'identité: {sender_identity}")
            else:
                private_key = self.sender._private_key

            signer = PKCS1_v1_5.new(private_key)
            transaction_dict = self.to_dict()
            transaction_dict.pop('signature', None)
            
            # Utiliser json.dumps pour une sérialisation cohérente
            h = SHA256.new(json.dumps(transaction_dict, sort_keys=True).encode('utf8'))
            signature = signer.sign(h)
            self.signature = binascii.hexlify(signature).decode('ascii')
            return self.signature
        except Exception as e:
            logger.error(f"Erreur lors de la signature: {e}")
            return None
        
    def verify_transaction(self, wallet_file="wallet.json"):
        """Vérifie la transaction avec la clé publique depuis wallet.json"""
        if not self.signature:
            logger.error("Signature manquante")
            return False
        
        try:
            with open(wallet_file, 'r') as f:
                wallets = json.load(f)
            
            sender_public_key = None
            sender_identity = self.sender.identity if hasattr(self.sender, 'identity') else self.sender
            
            for w in wallets:
                if w['identity'] == sender_identity:
                    sender_public_key = RSA.import_key(w['public_key'])
                    break
            
            if not sender_public_key:
                logger.error(f"Clé publique introuvable pour l'identité: {sender_identity}")
                return False
            
            # Créer une copie du dictionnaire sans la signature pour la vérification
            transaction_dict = self.to_dict()
            transaction_dict.pop('signature', None)
            
            verifier = PKCS1_v1_5.new(sender_public_key)
            # CORRECTION: Utiliser json.dumps comme dans sign_transaction
            h = SHA256.new(json.dumps(transaction_dict, sort_keys=True).encode('utf8'))
            
            result = verifier.verify(h, binascii.unhexlify(self.signature))
            if not result:
                logger.error("Vérification de signature échouée")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur vérification transaction: {e}")
            return False

    def to_dict(self):
        return {
            'transaction_id': self.transaction_id,
            'sender': self.sender.identity if hasattr(self.sender, 'identity') else self.sender,
            'recipient': self.recipient.identity if hasattr(self.recipient, 'identity') else self.recipient,
            'data': self.data,
            'timestamp': self.timestamp,
            'signature': self.signature
        }
 
class Block:
    def __init__(self, index, previous_hash, verified_transactions, miner_address=None):
        self.index = index
        self.previous_hash = previous_hash
        self.verified_transactions = verified_transactions
        self.timestamp = datetime.datetime.now()
        self.nonce = 0
        self.hash = ""
        self.miner_address = miner_address


    def compute_hash(self):
        """Calcule le hash du bloc"""
        block_data = {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp.isoformat(),
            "nonce": self.nonce,
            "transactions": [tx.to_dict() for tx in self.verified_transactions],
            "miner_address": self.miner_address
        }
        block_string = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def validate_transactions(self):
        """Vérifie que toutes les transactions du bloc sont valides"""
        for tx in self.verified_transactions:
            if not tx.verify_transaction():
                logger.error(f"Transaction invalide dans le bloc {self.index}: {tx.transaction_id}")
                return False
        return True
    
    def mine_block(self, difficulty=DIFFICULTY):
        """Mine le bloc avec la difficulté donnée"""
        if not self.validate_transactions():
            raise ValueError("Transactions invalides dans le bloc")
        start_time = time.time()
        while True:
            self.hash = self.compute_hash()
            if self.hash.startswith(difficulty):
                break
            self.nonce += 1
        mining_time = time.time() - start_time
        logger.info(f"Bloc #{self.index} miné en {mining_time:.2f}s - Hash: {self.hash}")


    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(),  # Format ISO 8601
            "transactions": [tx.to_dict() for tx in self.verified_transactions],
            "previous_hash": self.previous_hash,
            "hash": self.hash,
            "nonce": self.nonce,
            "miner_address": self.miner_address
        }

    def save_to_json(self, filename='blocks.json'):
        dict0 = self.to_dict() 

        if not os.path.isfile(filename):
            # Si le fichier n'existe pas
            with open(filename, 'w') as json_file:
                json.dump([], json_file)

        # Lire le contenu existant du fichier
        with open(filename, 'r') as json_file:
            data = json.load(json_file)

        # Ajouter le nouveau bloc
        data.append(dict0)

        # Écrire les données mises à jour dans le fichier
        with open(filename, 'w') as json_file:
            json.dump(data, json_file, indent=4, separators=(',', ': '))

    @classmethod
    def from_dict(cls, block_dict):
        transactions = []
        for tx_data in block_dict['transactions']:
            tx = Transaction(
                sender=tx_data['sender'],
                recipient=tx_data['recipient'],
                data=tx_data['data']
            )
            tx.transaction_id = tx_data['transaction_id']
            tx.timestamp = tx_data['timestamp']
            tx.signature = tx_data['signature']
            transactions.append(tx)

        block = cls(
            index=block_dict['index'],
            previous_hash=block_dict['previous_hash'],
            verified_transactions=transactions,
            miner_address=block_dict.get('miner_address')
        )
        block.timestamp = datetime.datetime.fromisoformat(block_dict['timestamp'])
        block.hash = block_dict['hash']
        block.nonce = block_dict['nonce']
        return block
        

class Blockchain:
    last_block_hash = None 
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        filename = 'blocks.json'

        if not os.path.isfile(filename):
            print("Création du bloc Genesis...")
            self._create_genesis_block()
        else:
            print("Chargement de la blockchain existante...")
            with open(filename) as fileBlocks:
                chain_data = json.load(fileBlocks)
                self.chain = chain_data
                if not self.validate_chain(self.chain):
                    raise ValueError("La blockchain chargée est invalide")
                # CORRECTION: Initialiser last_block_hash
                Blockchain.last_block_hash = self.chain[-1]['hash'] if self.chain else None
                print(f"Blockchain chargée avec {len(self.chain)} blocs")
    def _create_genesis_block(self):
        """Crée le bloc Genesis si la blockchain est vide"""
        genesis_block = Block(
            index=0,
            previous_hash="0"*64,
            verified_transactions=[]
        )
        genesis_block.mine_block()
        self.chain.append(genesis_block.to_dict())
        genesis_block.save_to_json()
        Blockchain.last_block_hash = genesis_block.hash
        print(f"Bloc Genesis créé")
        
    def add_transaction(self, sender, recipient, data):
        """Ajoute une transaction à la liste des transactions en attente"""
        tx = Transaction(sender, recipient, data)
        tx.signature = tx.sign_transaction()
        if not tx.signature:
            logger.error("Erreur de signature de la transaction")
            return False

        if not tx.verify_transaction():
            logger.error("Vérification de la transaction échouée")
            return False

        self.pending_transactions.append(tx)
        logger.info(f"Ajout de la transaction: {data}")
        return True



        
    def mine_pending_transactions(self, miner_address):
        """Traite les transactions en attente et crée un nouveau bloc"""
        if not self.pending_transactions:
            return False

        new_block = Block(
            index=len(self.chain),
            previous_hash=Blockchain.last_block_hash,
            verified_transactions=self.pending_transactions,
            miner_address=miner_address
        )
    
        new_block.mine_block()
        self.chain.append(new_block.to_dict()) 
        self.pending_transactions = []
        Blockchain.last_block_hash = new_block.hash
        
        logger.info(f"[Nouveau Bloc Miné] Total blocs: {len(self.chain)}")
    
        # Sauvegarde du nouveau bloc
        new_block.save_to_json() 
        return True

    
    
    @classmethod
    def validate_chain(cls, chain):
        """Valide l'intégrité de la blockchain"""
        for i, block_dict in enumerate(chain[1:], 1):
            try:
                block = Block.from_dict(block_dict)
            except Exception as e:
                logger.error(f"Erreur lors de la reconstitution du bloc {i}: {e}")
                return False

            computed_hash = block.compute_hash()
            if block.hash != computed_hash:
                logger.error(f"Hash invalide pour le bloc {block.index}")
                logger.error(f"Hash enregistré : {block.hash}")
                logger.error(f"Hash recalculé : {computed_hash}")
                return False

            if block.previous_hash != chain[i-1]['hash']:
                logger.error(f"Chaînage invalide au bloc {block.index}")
                logger.error(f"Hash attendu : {chain[i-1]['hash']}")
                logger.error(f"Hash trouvé  : {block.previous_hash}")
                return False

        return True

