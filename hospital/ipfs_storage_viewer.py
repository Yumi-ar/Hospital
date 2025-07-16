
"""
Visualisateur IPFS autonome - N'a pas besoin de la classe IPFSManager
Peut être placé n'importe où et exécuté directement
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any

class StandaloneIPFSViewer:
    def __init__(self, base_url: str = "http://localhost:5002"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v0"
        self.connected = self.test_connection()
    
    def test_connection(self) -> bool:
        """Test de connexion au daemon IPFS"""
        try:
            response = requests.post(f"{self.api_url}/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                print(f"✅ Connecté à IPFS version: {version_info['Version']}")
                return True
        except Exception as e:
            print(f"❌ Échec de connexion à IPFS: {e}")
            return False
        return False
    
    def get_repo_stats(self) -> Dict[str, Any]:
        """Statistiques du dépôt IPFS"""
        try:
            response = requests.post(f"{self.api_url}/repo/stat")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"Erreur stats: {e}")
            return {}
    
    def list_pins(self) -> List[str]:
        """Liste des fichiers épinglés"""
        try:
            response = requests.post(f"{self.api_url}/pin/ls")
            if response.status_code == 200:
                result = response.json()
                return list(result.get('Keys', {}).keys())
            return []
        except Exception as e:
            print(f"Erreur pins: {e}")
            return []
    
    def get_file_info(self, ipfs_hash: str) -> Dict[str, Any]:
        """Informations sur un fichier"""
        try:
            response = requests.post(f"{self.api_url}/object/stat", 
                                   data={'arg': ipfs_hash})
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"Erreur info fichier: {e}")
            return {}
    
    def format_bytes(self, bytes_value: int) -> str:
        """Formatage des octets"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def show_summary(self):
        """Afficher le résumé du stockage"""
        print("\n" + "="*50)
        print("📊 RÉSUMÉ DU STOCKAGE IPFS")
        print("="*50)
        
        stats = self.get_repo_stats()
        if stats:
            print(f"Taille totale: {self.format_bytes(stats.get('RepoSize', 0))}")
            print(f"Nombre d'objets: {stats.get('NumObjects', 0):,}")
            print(f"Limite de stockage: {self.format_bytes(stats.get('StorageMax', 0))}")
        
        pins = self.list_pins()
        print(f"Fichiers épinglés: {len(pins)}")
        
        if pins:
            print(f"\n📌 Premiers fichiers épinglés:")
            for i, pin_hash in enumerate(pins[:5]):
                info = self.get_file_info(pin_hash)
                size = info.get('CumulativeSize', 0)
                print(f"  {i+1}. {pin_hash[:20]}... ({self.format_bytes(size)})")
            
            if len(pins) > 5:
                print(f"  ... et {len(pins) - 5} autres")
    
    def show_all_pins(self):
        """Afficher tous les pins"""
        pins = self.list_pins()
        print(f"\n📌 TOUS LES FICHIERS ÉPINGLÉS ({len(pins)}):")
        print("-" * 80)
        
        for i, pin_hash in enumerate(pins, 1):
            info = self.get_file_info(pin_hash)
            size = info.get('CumulativeSize', 0)
            print(f"{i:3d}. {pin_hash}")
            print(f"     Taille: {self.format_bytes(size)}")
            print()
    
    def examine_file(self, ipfs_hash: str):
        """Examiner un fichier spécifique"""
        print(f"\n🔍 EXAMEN DU FICHIER: {ipfs_hash}")
        print("-" * 60)
        
        info = self.get_file_info(ipfs_hash)
        if info:
            print(f"Taille cumulative: {self.format_bytes(info.get('CumulativeSize', 0))}")
            print(f"Taille des données: {self.format_bytes(info.get('DataSize', 0))}")
            print(f"Nombre de liens: {info.get('NumLinks', 0)}")
            
            # Essayer de voir le contenu (si c'est du texte/JSON)
            try:
                response = requests.post(f"{self.api_url}/cat", 
                                       data={'arg': ipfs_hash})
                if response.status_code == 200:
                    content = response.text[:500]  # Premiers 500 caractères
                    print(f"\nAperçu du contenu:")
                    print("-" * 30)
                    print(content)
                    if len(response.text) > 500:
                        print("... (contenu tronqué)")
            except:
                print("Impossible d'afficher le contenu (fichier binaire?)")


def main():
    """Fonction principale"""
    viewer = StandaloneIPFSViewer()
    
    if not viewer.connected:
        print("\n❌ IPFS n'est pas accessible!")
        print("Démarrez le daemon IPFS avec: ipfs daemon")
        return
    
    while True:
        print("\n" + "="*50)
        print("🏥 GESTIONNAIRE DE STOCKAGE IPFS")
        print("="*50)
        print("1. Résumé du stockage")
        print("2. Lister tous les fichiers épinglés")
        print("3. Examiner un fichier spécifique")
        print("4. Statistiques détaillées")
        print("5. Quitter")
        
        choice = input("\nChoix (1-5): ").strip()
        
        if choice == '1':
            viewer.show_summary()
        
        elif choice == '2':
            viewer.show_all_pins()
        
        elif choice == '3':
            hash_input = input("Hash IPFS: ").strip()
            if hash_input:
                viewer.examine_file(hash_input)
            else:
                print("Hash requis!")
        
        elif choice == '4':
            stats = viewer.get_repo_stats()
            print(f"\n📈 STATISTIQUES DÉTAILLÉES:")
            print(json.dumps(stats, indent=2))
        
        elif choice == '5':
            print("👋 Au revoir!")
            break
        
        else:
            print("❌ Choix invalide!")
        
        input("\n⏸️  Appuyez sur Entrée pour continuer...")


if __name__ == "__main__":
    main()