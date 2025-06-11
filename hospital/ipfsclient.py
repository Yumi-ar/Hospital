import requests
import json
import os
from typing import Optional, Dict, Any
import hashlib
from datetime import datetime

class HospitalIPFSClient:
    """
    IPFS Client specifically designed for hospital management system
    Handles medical records, documents, and patient data storage
    """
    
    def __init__(self, base_url: str = "http://localhost:5001"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v0"
        
    def test_connection(self) -> bool:
        """Test if IPFS daemon is running and accessible"""
        try:
            # Use POST method for newer IPFS versions
            response = requests.post(f"{self.api_url}/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                print(f"Connected to IPFS daemon version: {version_info['Version']}")
                return True
        except Exception as e:
            print(f"Failed to connect to IPFS daemon: {e}")
            return False
        return False
    
    def add_medical_record(self, file_path: str, patient_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Add a medical record to IPFS
        Returns IPFS hash and metadata
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(f"{self.api_url}/add", files=files)
                
            if response.status_code == 200:
                result = response.json()
                
                # Create metadata
                metadata = {
                    'ipfs_hash': result['Hash'],
                    'file_name': os.path.basename(file_path),
                    'file_size': result['Size'],
                    'patient_id': patient_id,
                    'upload_time': datetime.now().isoformat(),
                    'file_type': self._get_file_type(file_path)
                }
                
                print(f"Medical record uploaded successfully!")
                print(f"IPFS Hash: {result['Hash']}")
                print(f"Size: {result['Size']} bytes")
                
                return metadata
            else:
                print(f"Failed to upload file: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error uploading medical record: {e}")
            return None
    
    def get_medical_record(self, ipfs_hash: str, save_path: str = None) -> Optional[bytes]:
        """
        Retrieve a medical record from IPFS
        """
        try:
            response = requests.post(f"{self.api_url}/cat", data={'arg': ipfs_hash})
            
            if response.status_code == 200:
                content = response.content
                
                if save_path:
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    print(f"Medical record saved to: {save_path}")
                
                return content
            else:
                print(f"Failed to retrieve file: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error retrieving medical record: {e}")
            return None
    
    def add_json_data(self, data: Dict[str, Any], description: str = "Hospital Data") -> Optional[str]:
        """
        Add JSON data (like patient info, medical history) to IPFS
        """
        try:
            json_data = json.dumps(data, indent=2)
            
            files = {'file': ('data.json', json_data.encode(), 'application/json')}
            response = requests.post(f"{self.api_url}/add", files=files)
            
            if response.status_code == 200:
                result = response.json()
                print(f"{description} uploaded to IPFS!")
                print(f"IPFS Hash: {result['Hash']}")
                return result['Hash']
            else:
                print(f"Failed to upload JSON data: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error uploading JSON data: {e}")
            return None
    
    def get_json_data(self, ipfs_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve JSON data from IPFS
        """
        try:
            response = requests.post(f"{self.api_url}/cat", data={'arg': ipfs_hash})
            
            if response.status_code == 200:
                return json.loads(response.text)
            else:
                print(f"Failed to retrieve JSON data: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error retrieving JSON data: {e}")
            return None
    
    def pin_file(self, ipfs_hash: str) -> bool:
        """
        Pin a file to ensure it stays in local IPFS storage
        Important for critical medical records
        """
        try:
            response = requests.post(f"{self.api_url}/pin/add", data={'arg': ipfs_hash})
            
            if response.status_code == 200:
                print(f"File {ipfs_hash} pinned successfully")
                return True
            else:
                print(f"Failed to pin file: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error pinning file: {e}")
            return False
    
    def list_pinned_files(self) -> Optional[Dict[str, Any]]:
        """
        List all pinned files (important medical records)
        """
        try:
            response = requests.post(f"{self.api_url}/pin/ls")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to list pinned files: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error listing pinned files: {e}")
            return None
    
    def get_file_info(self, ipfs_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a file stored in IPFS
        """
        try:
            response = requests.post(f"{self.api_url}/object/stat", data={'arg': ipfs_hash})
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get file info: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error getting file info: {e}")
            return None
    
    def _get_file_type(self, file_path: str) -> str:
        """
        Determine file type based on extension
        """
        _, ext = os.path.splitext(file_path)
        file_types = {
            '.pdf': 'PDF Document',
            '.jpg': 'JPEG Image',
            '.jpeg': 'JPEG Image',
            '.png': 'PNG Image',
            '.dcm': 'DICOM Medical Image',
            '.txt': 'Text Document',
            '.json': 'JSON Data',
            '.xml': 'XML Document'
        }
        return file_types.get(ext.lower(), 'Unknown')
    
    def create_patient_record(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a complete patient record and store in IPFS
        """
        # Add timestamp and hash for integrity
        patient_data['created_at'] = datetime.now().isoformat()
        patient_data['record_hash'] = hashlib.sha256(
            json.dumps(patient_data, sort_keys=True).encode()
        ).hexdigest()
        
        return self.add_json_data(patient_data, "Patient Record")

    def remove_pinned_file(self, ipfs_hash: str) -> bool:
        """
        Remove (unpin) a file from local IPFS node
        """
        try:
            response = requests.post(f"{self.api_url}/pin/rm", data={'arg': ipfs_hash})
            if response.status_code == 200:
                print(f"File {ipfs_hash} unpinned successfully")
                return True
            else:
                print(f"Failed to unpin file: {response.text}")
                return False
        except Exception as e:
            print(f"Error unpinning file: {e}")
            return False

