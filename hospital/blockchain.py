import hashlib
import json
from time import time
from django.db import models
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

class Block(models.Model):
    index = models.PositiveIntegerField(unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    previous_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64)
    nonce = models.PositiveIntegerField(default=0)
    merkle_root = models.CharField(max_length=64)
    difficulty = models.PositiveIntegerField(default=4)

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": str(self.timestamp),
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def mine_block(self):
        self.hash = self.calculate_hash()
        while not self.hash.startswith('0' * self.difficulty):
            self.nonce += 1
            self.hash = self.calculate_hash()
        self.save()

class Transaction(models.Model):
    TX_TYPES = [
        ('USER_CREATE', 'User creation'),
        ('PATIENT_CREATE', 'Patient creation'),
        ('DOCTOR_CREATE', 'Doctor creation'),
        ('DOCUMENT_CREATE', 'Document creation'),
        ('ACCESS_GRANT', 'Access grant'),
        ('CONSULTATION', 'Consultation'),
        ('PRESCRIPTION', 'Prescription')
    ]
    
    tx_id = models.CharField(max_length=64, unique=True)
    tx_type = models.CharField(max_length=20, choices=TX_TYPES)
    sender_id = models.PositiveIntegerField()  # Stocke l'ID plutôt qu'une ForeignKey
    recipient_id = models.PositiveIntegerField(null=True)
    data = models.JSONField()
    signature = models.CharField(max_length=512)
    block = models.ForeignKey(Block, null=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True)

    def calculate_hash(self):
        tx_string = json.dumps({
            "tx_type": self.tx_type,
            "sender": self.sender_id,
            "recipient": self.recipient_id,
            "data": self.data,
            "timestamp": str(self.timestamp)
        }, sort_keys=True).encode()
        return hashlib.sha256(tx_string).hexdigest()

class Blockchain:
    def __init__(self):
        self.difficulty = 4
        self.pending_txs = []

    def create_genesis_block(self):
        if not Block.objects.exists():
            genesis = Block(
                index=0,
                previous_hash="0",
                merkle_root="",
                nonce=0
            )
            genesis.hash = genesis.calculate_hash()
            genesis.save()

    def add_transaction(self, tx_type, sender_id, data, recipient_id=None):
        tx = Transaction(
            tx_type=tx_type,
            sender_id=sender_id,
            recipient_id=recipient_id,
            data=data,
            tx_id=hashlib.sha256(f"{tx_type}{sender_id}{time()}".encode()).hexdigest()
        )
        self.pending_txs.append(tx)
        return tx

    def mine_pending_transactions(self):
        if not self.pending_txs:
            return None

        last_block = Block.objects.order_by('-index').first()
        new_block = Block(
            index=last_block.index + 1 if last_block else 0,
            previous_hash=last_block.hash if last_block else "0",
            merkle_root=self._calculate_merkle_root(),
            difficulty=self.difficulty
        )

        new_block.mine_block()
        for tx in self.pending_txs:
            tx.block = new_block
            tx.save()
        
        self.pending_txs = []
        return new_block

    def _calculate_merkle_root(self):
        tx_hashes = [tx.tx_id for tx in self.pending_txs]
        if not tx_hashes:
            return ""
        
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            tx_hashes = [hashlib.sha256((tx_hashes[i] + tx_hashes[i+1]).encode()).hexdigest() 
                         for i in range(0, len(tx_hashes), 2)]
        return tx_hashes[0]