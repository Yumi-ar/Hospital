import hashlib
import json
import time
import os
import binascii
import datetime
import collections
from datetime import datetime
from typing import Dict, List, Optional, Union
import requests
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import logging
import ipfshttpclient
from web3 import Web3
from eth_account import Account
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256

# Configuration du logging
logger = logging.getLogger(__name__)

class MedicalWallet:
    """Portefeuille médical avec clés RSA pour les utilisateurs (patients/médecins)"""
    
    def __init__(self, user_id: str = None, key_size: int = 2048):
        if not RSA_AVAILABLE:
            raise Exception("RSA non disponible - impossible de créer un portefeuille")
        
        self.user_id = user_id
        self.key_size = max(1024, min(key_size, 4096))  # Sécurité minimale 1024, max 4096
        
        # Générer les clés RSA
        random_generator = Crypto.Random.new().read
        self._private_key = RSA.generate(self.key_size, random_generator)
        self._public_key = self._private_key.publickey()
        self._signer = PKCS1_v1_5.new(self._private_key)
        
        logger.info(f"Portefeuille créé pour {user_id} avec clés RSA {key_size} bits")
    
    @property
    def identity(self) -> str:
        """Identité unique basée sur la clé publique"""
        return binascii.hexlify(self._public_key.exportKey(format='DER')).decode('ascii')
    
    @property
    def public_key_pem(self) -> str:
        """Clé publique au format PEM"""
        return self._public_key.exportKey(format='PEM').decode('ascii')
    
    @property
    def private_key_pem(self) -> str:
        """Clé privée au format PEM (à utiliser avec précaution)"""
        return self._private_key.exportKey(format='PEM').decode('ascii')
    
    def sign_data(self, data: str) -> str:
        """Signer des données avec la clé privée"""
        try:
            h = SHA256.new(data.encode('utf-8'))
            signature = self._signer.sign(h)
            return binascii.hexlify(signature).decode('ascii')
        except Exception as e:
            logger.error(f"Erreur signature: {e}")
            return ""
    
    def verify_signature(self, data: str, signature: str, public_key_pem: str = None) -> bool:
        """Vérifier une signature avec la clé publique"""
        try:
            if public_key_pem:
                public_key = RSA.importKey(public_key_pem.encode('ascii'))
            else:
                public_key = self._public_key
            
            verifier = PKCS1_v1_5.new(public_key)
            h = SHA256.new(data.encode('utf-8'))
            signature_bytes = binascii.unhexlify(signature.encode('ascii'))
            return verifier.verify(h, signature_bytes)
        except Exception as e:
            logger.error(f"Erreur vérification signature: {e}")
            return False
    
    def encrypt_data(self, data: str, recipient_public_key_pem: str = None) -> str:
        """Chiffrer des données avec RSA"""
        try:
            if recipient_public_key_pem:
                public_key = RSA.importKey(recipient_public_key_pem.encode('ascii'))
            else:
                public_key = self._public_key
            
            cipher = PKCS1_OAEP.new(public_key)
            # RSA ne peut chiffrer que des données de taille limitée
            # Pour de gros volumes, on utiliserait un chiffrement hybride
            max_data_size = (self.key_size // 8) - 42  # PKCS1_OAEP padding
            
            if len(data.encode('utf-8')) > max_data_size:
                raise ValueError(f"Données trop volumineuses pour RSA (max: {max_data_size} bytes)")
            
            encrypted_data = cipher.encrypt(data.encode('utf-8'))
            return binascii.hexlify(encrypted_data).decode('ascii')
        except Exception as e:
            logger.error(f"Erreur chiffrement RSA: {e}")
            return ""
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Déchiffrer des données avec RSA"""
        try:
            cipher = PKCS1_OAEP.new(self._private_key)
            encrypted_bytes = binascii.unhexlify(encrypted_data.encode('ascii'))
            decrypted_data = cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"Erreur déchiffrement RSA: {e}")
            return ""
    
    def save_to_file(self, filepath: str, password: str = None):
        """Sauvegarder le portefeuille dans un fichier"""
        try:
            wallet_data = {
                'user_id': self.user_id,
                'identity': self.identity,
                'public_key': self.public_key_pem,
                'created_at': datetime.now().isoformat()
            }
            
            if password:
                # En production, utiliser un chiffrement plus robuste
                private_key_encrypted = self._private_key.exportKey(
                    format='PEM', 
                    passphrase=password.encode('utf-8')
                ).decode('ascii')
                wallet_data['private_key_encrypted'] = private_key_encrypted
            else:
                wallet_data['private_key'] = self.private_key_pem
            
            with open(filepath, 'w') as f:
                json.dump(wallet_data, f, indent=2)
            
            logger.info(f"Portefeuille sauvegardé: {filepath}")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde portefeuille: {e}")
    
    @classmethod
    def load_from_file(cls, filepath: str, password: str = None):
        """Charger un portefeuille depuis un fichier"""
        try:
            with open(filepath, 'r') as f:
                wallet_data = json.load(f)
            
            instance = cls.__new__(cls)
            instance.user_id = wallet_data.get('user_id')
            
            if 'private_key_encrypted' in wallet_data and password:
                instance._private_key = RSA.importKey(
                    wallet_data['private_key_encrypted'].encode('ascii'),
                    passphrase=password.encode('utf-8')
                )
            elif 'private_key' in wallet_data:
                instance._private_key = RSA.importKey(
                    wallet_data['private_key'].encode('ascii')
                )
            else:
                raise ValueError("Clé privée non trouvée ou mot de passe requis")
            
            instance._public_key = instance._private_key.publickey()
            instance._signer = PKCS1_v1_5.new(instance._private_key)
            instance.key_size = instance._private_key.size_in_bits()
            
            logger.info(f"Portefeuille chargé: {filepath}")
            return instance
            
        except Exception as e:
            logger.error(f"Erreur chargement portefeuille: {e}")
            return None


class MedicalTransaction:
    """Transaction médicale avec signature RSA"""
    
    def __init__(self, from_wallet: MedicalWallet, to_identity: str, 
                 data: Dict, transaction_type: str = "medical_data"):
        self.from_wallet = from_wallet
        self.from_identity = from_wallet.identity if from_wallet else "ADMIN"
        self.to_identity = to_identity
        self.data = data
        self.transaction_type = transaction_type
        self.timestamp = datetime.now()
        self.transaction_id = self._generate_id()
        self.signature = ""
        
        # Signer automatiquement si portefeuille disponible
        if from_wallet:
            self.sign_transaction()
    
    def _generate_id(self) -> str:
        """Générer un ID unique pour la transaction"""
        tx_string = f"{self.from_identity}{self.to_identity}{self.transaction_type}{self.timestamp}"
        return hashlib.sha256(tx_string.encode('utf-8')).hexdigest()[:16]
    
    def to_dict(self) -> collections.OrderedDict:
        """Convertir la transaction en dictionnaire ordonné"""
        return collections.OrderedDict({
            'id': self.transaction_id,
            'type': self.transaction_type,
            'from': self.from_identity,
            'to': self.to_identity,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'signature': self.signature
        })
    
    def sign_transaction(self) -> str:
        """Signer la transaction avec la clé privée"""
        if not self.from_wallet:
            logger.warning("Impossible de signer - portefeuille manquant")
            return ""
        
        try:
            # Créer une représentation canonique de la transaction
            tx_dict = self.to_dict()
            tx_dict['signature'] = ""  # Exclure la signature du hash
            tx_string = json.dumps(tx_dict, sort_keys=True, ensure_ascii=False)
            
            self.signature = self.from_wallet.sign_data(tx_string)
            return self.signature
            
        except Exception as e:
            logger.error(f"Erreur signature transaction: {e}")
            return ""
    
    def verify_signature(self, public_key_pem: str = None) -> bool:
        """Vérifier la signature de la transaction"""
        if not self.signature:
            return False
        
        try:
            # Recréer la transaction sans signature pour vérification
            tx_dict = self.to_dict()
            original_signature = tx_dict['signature']
            tx_dict['signature'] = ""
            tx_string = json.dumps(tx_dict, sort_keys=True, ensure_ascii=False)
            
            if self.from_wallet:
                return self.from_wallet.verify_signature(tx_string, original_signature, public_key_pem)
            elif public_key_pem:
                # Vérification avec clé publique externe
                wallet_temp = MedicalWallet()
                return wallet_temp.verify_signature(tx_string, original_signature, public_key_pem)
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur vérification signature: {e}")
            return False
    
    def display_transaction(self):
        """Afficher les détails de la transaction"""
        tx_dict = self.to_dict()
        print("=== TRANSACTION MÉDICALE ===")
        print(f"ID: {tx_dict['id']}")
        print(f"Type: {tx_dict['type']}")
        print(f"De: {tx_dict['from'][:20]}...")
        print(f"Vers: {tx_dict['to'][:20]}...")
        print(f"Données: {tx_dict['data']}")
        print(f"Timestamp: {tx_dict['timestamp']}")
        print(f"Signature: {'✓' if self.signature else '✗'}")
        print("=" * 30)


class IPFSManager:
    """Gestionnaire pour les opérations IPFS avec gestion d'erreurs améliorée"""
    
    def __init__(self, host='localhost', port=5001):
        self.client = None
        self.connected = False
        
        if not IPFS_AVAILABLE:
            logger.error("IPFS client non disponible")
            return
            
        try:
            # Tenter plusieurs méthodes de connexion
            connection_attempts = [
                f'/dns/{host}/tcp/{port}/http',
                f'/ip4/127.0.0.1/tcp/{port}/http',
                f'http://{host}:{port}'
            ]
            
            for attempt in connection_attempts:
                try:
                    self.client = ipfshttpclient.connect(attempt)
                    # Test de connexion
                    self.client.version()
                    self.connected = True
                    logger.info(f"IPFS connecté via: {attempt}")
                    break
                except Exception as e:
                    logger.debug(f"Échec connexion IPFS {attempt}: {e}")
                    continue
                    
            if not self.connected:
                logger.error("Impossible de se connecter à IPFS")
                
        except Exception as e:
            logger.error(f"Erreur initialisation IPFS: {e}")
    
    def add_file(self, file_content: bytes, filename: str = None) -> Optional[str]:
        """Ajouter un fichier à IPFS avec validation"""
        if not self.connected or not self.client:
            logger.error("IPFS non connecté")
            return None
            
        try:
            # Validation de la taille du fichier (limite à 50MB)
            if len(file_content) > 50 * 1024 * 1024:
                logger.error("Fichier trop volumineux (>50MB)")
                return None
            
            result = self.client.add_bytes(file_content)
            logger.info(f"Fichier ajouté à IPFS: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur ajout fichier IPFS: {e}")
            return None
    
    def get_file(self, hash_ipfs: str) -> Optional[bytes]:
        """Récupérer un fichier depuis IPFS avec validation"""
        if not self.connected or not self.client:
            logger.error("IPFS non connecté")
            return None
            
        # Validation du hash IPFS
        if not self._is_valid_ipfs_hash(hash_ipfs):
            logger.error(f"Hash IPFS invalide: {hash_ipfs}")
            return None
            
        try:
            content = self.client.cat(hash_ipfs)
            return content
        except Exception as e:
            logger.error(f"Erreur récupération fichier IPFS {hash_ipfs}: {e}")
            return None
    
    def pin_file(self, hash_ipfs: str) -> bool:
        """Épingler un fichier pour éviter sa suppression"""
        if not self.connected or not self.client:
            return False
            
        try:
            self.client.pin.add(hash_ipfs)
            logger.info(f"Fichier épinglé: {hash_ipfs}")
            return True
        except Exception as e:
            logger.error(f"Erreur épinglage IPFS {hash_ipfs}: {e}")
            return False
    
    def _is_valid_ipfs_hash(self, hash_ipfs: str) -> bool:
        """Valider un hash IPFS"""
        if not hash_ipfs or not isinstance(hash_ipfs, str):
            return False
        # Hash IPFS v0 commence par Qm et fait 46 caractères
        # Hash IPFS v1 commence par b et est plus long
        return (hash_ipfs.startswith('Qm') and len(hash_ipfs) == 46) or \
               (hash_ipfs.startswith('b') and len(hash_ipfs) > 46)


class MedicalBlock:
    """Bloc de la blockchain médicale avec validation renforcée et minage optimisé"""
    
    def __init__(self, index: int, transactions: List[MedicalTransaction], previous_hash: str, nonce: int = 0):
        # Validation des paramètres
        if not isinstance(index, int) or index < 0:
            raise ValueError("L'index doit être un entier positif")
        if not isinstance(transactions, list):
            raise ValueError("Les transactions doivent être une liste")
        if not isinstance(previous_hash, str):
            raise ValueError("Le hash précédent doit être une chaîne")
            
        self.index = index
        self.timestamp = datetime.now()
        self.transactions = self._validate_transactions(transactions)
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()
    
    def _validate_transactions(self, transactions: List[MedicalTransaction]) -> List[Dict]:
        """Valider les transactions et convertir en dictionnaires"""
        validated_transactions = []
        for tx in transactions:
            if isinstance(tx, MedicalTransaction):
                # Vérifier la signature
                if tx.verify_signature():
                    validated_transactions.append(tx.to_dict())
                else:
                    logger.warning(f"Transaction avec signature invalide ignorée: {tx.transaction_id}")
            elif isinstance(tx, dict) and self._is_valid_transaction_dict(tx):
                validated_transactions.append(tx)
            else:
                logger.warning(f"Transaction invalide ignorée: {tx}")
        return validated_transactions
    
    def _is_valid_transaction_dict(self, transaction: Dict) -> bool:
        """Vérifier la validité d'un dictionnaire de transaction"""
        required_fields = ['type', 'timestamp', 'from', 'to']
        return all(field in transaction for field in required_fields)
    
    def calculate_hash(self) -> str:
        """Calculer le hash du bloc avec gestion d'erreurs"""
        try:
            block_data = {
                'index': self.index,
                'timestamp': self.timestamp.isoformat(),
                'transactions': self.transactions,
                'previous_hash': self.previous_hash,
                'nonce': self.nonce
            }
            block_string = json.dumps(block_data, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(block_string.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"Erreur calcul hash bloc: {e}")
            return hashlib.sha256(b'').hexdigest()
    
    def mine_block(self, difficulty: int = 4):
        """Miner le bloc avec preuve de travail optimisée"""
        if difficulty < 1 or difficulty > 8:
            difficulty = 4  # Valeur par défaut sécurisée
            
        target = "0" * difficulty
        start_time = time.time()
        max_mining_time = 300  # 5 minutes maximum
        
        logger.info(f"Début minage bloc {self.index} (difficulté: {difficulty})")
        
        while not self.hash.startswith(target):
            # Vérifier le timeout
            current_time = time.time()
            if current_time - start_time > max_mining_time:
                logger.warning("Timeout du minage - difficulté réduite")
                difficulty = max(1, difficulty - 1)
                target = "0" * difficulty
                start_time = current_time
            
            self.nonce += 1
            self.hash = self.calculate_hash()
            
            # Affichage du progrès
            if self.nonce % 10000 == 0:
                elapsed = current_time - start_time
                logger.debug(f"Minage... nonce: {self.nonce}, temps: {elapsed:.2f}s")
            
            # Éviter une boucle infinie
            if self.nonce > 2000000:
                logger.error("Minage abandonné - trop d'itérations")
                break
        
        mining_time = time.time() - start_time
        logger.info(f"Bloc {self.index} miné en {mining_time:.2f}s (nonce: {self.nonce}, hash: {self.hash})")
    
    def to_dict(self) -> Dict:
        """Convertir le bloc en dictionnaire"""
        return {
            'index': self.index,
            'timestamp': self.timestamp.isoformat(),
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'hash': self.hash
        }
    
    def save_to_json(self, filename: str = 'blocks.json'):
        """Sauvegarder le bloc dans un fichier JSON"""
        try:
            data = []
            
            # Lire le fichier existant
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # Ajouter le nouveau bloc
            data.append(self.to_dict())
            
            # Sauvegarder
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            logger.info(f"Bloc {self.index} sauvegardé dans {filename}")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde bloc: {e}")


class MedicalBlockchain:
    """Blockchain pour les données médicales """
    
    def __init__(self, difficulty: int = 4):
        self.difficulty = max(1, min(difficulty, 6))  # Limiter la difficulté
        self.chain = []
        self.pending_transactions = []
        self.transaction_ids = set()  # Ensemble pour suivre les IDs des transactions
        self.mining_reward = 100
        self.ipfs_manager = IPFSManager()
        self.user_wallets = {}  # Cache des portefeuilles utilisateurs
        
        # Charger ou créer la blockchain
        self._load_or_create_chain()
    
    def add_transaction(self, transaction: Union[MedicalTransaction, Dict]) -> bool:
        """Ajouter une transaction en attente avec validation RSA"""
        try:
            # Convertir dict en MedicalTransaction si nécessaire
            if isinstance(transaction, dict):
                tx = MedicalTransaction(
                    from_wallet=None,
                    to_identity=transaction.get('to', ''),
                    data=transaction.get('data', {}),
                    transaction_type=transaction.get('type', 'basic')
                )
                tx.from_identity = transaction.get('from', 'UNKNOWN')
                transaction = tx
            
            # Vérifier que la transaction n'existe pas déjà
            if transaction.transaction_id in self.transaction_ids:
                logger.warning("Transaction déjà en attente")
                return False
            
            # Vérifier la validité de la transaction
            if not transaction.verify_signature():
                logger.warning("Transaction avec signature invalide")
                return False
            
            # Ajouter la transaction à la liste des transactions en attente
            self.pending_transactions.append(transaction)
            self.transaction_ids.add(transaction.transaction_id)  # Ajouter l'ID à l'ensemble
            logger.info(f"Transaction RSA ajoutée: {transaction.transaction_type}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur ajout transaction: {e}")
            return False
    
    def mine_pending_transactions(self, mining_reward_address: str) -> bool:
        """Miner les transactions en attente avec récompense RSA"""
        if not self.pending_transactions:
            logger.info("Aucune transaction en attente")
            return False
        
        try:
            # Ajouter la récompense de minage
            reward_transaction = MedicalTransaction(
                from_wallet=None,
                to_identity=mining_reward_address,
                data={'amount': self.mining_reward, 'type': 'mining_reward'},
                transaction_type='mining_reward'
            )
            reward_transaction.from_identity = "BLOCKCHAIN_SYSTEM"
            
            transactions = self.pending_transactions + [reward_transaction]
            
            # Créer et miner le nouveau bloc
            block = MedicalBlock(
                len(self.chain),
                transactions,
                self.get_latest_block().hash
            )
            block.mine_block(self.difficulty)
            
            # Ajouter à la chaîne
            self.chain.append(block)
            self.pending_transactions = []
            self.transaction_ids.clear()  # Réinitialiser les IDs des transactions
            
            # Sauvegarder
            self._save_to_cache()
            block.save_to_json()
            
            logger.info(f"Bloc {block.index} miné avec {len(transactions)} transactions")
            return True
            
        except Exception as e:
            logger.error(f"Erreur minage: {e}")
            return False



