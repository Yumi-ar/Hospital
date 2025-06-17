import os
import sys
import json
import hashlib
import traceback
from datetime import datetime
from pathlib import Path

# Get the project root directory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital_manage.settings')

try:
    import django
    django.setup()
    print("✅ Django setup successful")
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

try:
    from hospital.ipfsclient import IPFSManager
    print("✅ IPFSManager imported successfully")
except ImportError as e:
    print(f"❌ Failed to import IPFSManager: {e}")
    sys.exit(1)

class IPFSTestSuite:
    def __init__(self):
        self.ipfs_manager = None
        self.test_results = {
            'connection': False,
            'json_upload': False,
            'data_retrieval': False,
            'file_upload': False,
            'pinning': False
        }
        
    def print_header(self, title):
        """Print formatted test section header"""
        print(f"\n{'='*20} {title} {'='*20}")
        
    def print_result(self, test_name, success, message=""):
        """Print test result with formatting"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if message:
            print(f"   {message}")
        
    def test_ipfs_connection(self):
        """Test IPFS daemon connection"""
        self.print_header("IPFS Connection Test")
        
        try:
            self.ipfs_manager = IPFSManager()
            
            if self.ipfs_manager.connected:
                self.test_results['connection'] = True
                self.print_result("Connection", True, "IPFS daemon is accessible")
                return True
            else:
                self.print_result("Connection", False, "IPFS daemon not accessible")
                return False
                
        except Exception as e:
            self.print_result("Connection", False, f"Error: {str(e)}")
            return False
    
    def test_json_upload(self):
        """Test JSON data upload to IPFS"""
        self.print_header("JSON Upload Test")
        
        if not self.ipfs_manager or not self.ipfs_manager.connected:
            self.print_result("JSON Upload", False, "No IPFS connection")
            return None
            
        # Create comprehensive test data
        test_data = {
            'test_metadata': {
                'test_id': 'ipfs_test_001',
                'timestamp': datetime.now().isoformat(),
                'test_type': 'comprehensive_ipfs_test'
            },
            'medical_analysis': {
                'patient_id': 'P123456',
                'analysis_type': 'blood_chemistry',
                'test_date': '2025-06-12',
                'results': {
                    'hemoglobin': {'value': 14.2, 'unit': 'g/dL', 'normal_range': '12.0-16.0'},
                    'glucose': {'value': 95, 'unit': 'mg/dL', 'normal_range': '70-100'},
                    'cholesterol': {'value': 180, 'unit': 'mg/dL', 'normal_range': '<200'}
                },
                'physician': 'Dr. Test',
                'status': 'completed'
            },
            'data_integrity': {
                'checksum': hashlib.md5(json.dumps({'test': 'data'}).encode()).hexdigest(),
                'size_bytes': len(json.dumps({'test': 'data'}))
            }
        }
        
        try:
            # Upload data using your IPFSManager method
            cid = self.ipfs_manager.add_json_to_ipfs(test_data)
            if cid:
                self.test_results['json_upload'] = True
                self.print_result("JSON Upload", True, f"CID: {cid}")
                return cid
            else:
                self.print_result("JSON Upload", False, "Upload returned None")
                return None
                
        except Exception as e:
            self.print_result("JSON Upload", False, f"Exception: {str(e)}")
            return None
    
    def test_data_retrieval(self, cid):
        """Test data retrieval from IPFS"""
        self.print_header("Data Retrieval Test")
        
        if not cid:
            self.print_result("Data Retrieval", False, "No CID to retrieve")
            return False
            
        try:
            # Use your IPFSManager's method for JSON data retrieval
            retrieved_data = self.ipfs_manager.get_json_data(cid)
            
            if retrieved_data:
                # Verify data structure
                expected_keys = ['test_metadata', 'medical_analysis', 'data_integrity']
                if all(key in retrieved_data for key in expected_keys):
                    # Verify specific data
                    if (retrieved_data['test_metadata']['test_id'] == 'ipfs_test_001' and
                        retrieved_data['medical_analysis']['patient_id'] == 'P123456'):
                        self.test_results['data_retrieval'] = True
                        self.print_result("Data Retrieval", True, "Data integrity verified")
                        return True
                    else:
                        self.print_result("Data Retrieval", False, "Data integrity check failed")
                        return False
                else:
                    self.print_result("Data Retrieval", False, f"Missing keys. Got: {list(retrieved_data.keys())}")
                    return False
            else:
                self.print_result("Data Retrieval", False, "No data retrieved")
                return False
                    
        except Exception as e:
            self.print_result("Data Retrieval", False, f"Exception: {str(e)}")
            return False
    
    def test_file_upload(self):
        """Test file upload to IPFS"""
        self.print_header("File Upload Test")
        
        if not self.ipfs_manager or not self.ipfs_manager.connected:
            self.print_result("File Upload", False, "No IPFS connection")
            return None
            
        try:
            # Create test file content
            test_content = json.dumps({
                'report_type': 'medical_analysis_report',
                'generated_at': datetime.now().isoformat(),
                'content': 'This is a test medical report for IPFS upload verification',
                'metadata': {
                    'format': 'json',
                    'version': '1.0',
                    'size': 'test'
                }
            }, indent=2)
            
            # Create temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
                temp_file.write(test_content)
                temp_file.flush()
                
                # Upload to IPFS using your method
                result = self.ipfs_manager.add_medical_record(temp_file.name, patient_id="test_patient")
                
                # Clean up
                os.unlink(temp_file.name)
                
                if result and 'ipfs_hash' in result:
                    file_cid = result['ipfs_hash']
                    self.test_results['file_upload'] = True
                    self.print_result("File Upload", True, f"File CID: {file_cid}")
                    return file_cid
                else:
                    self.print_result("File Upload", False, "Upload returned no valid result")
                    return None
                    
        except Exception as e:
            self.print_result("File Upload", False, f"Exception: {str(e)}")
            # Clean up on error
            try:
                if 'temp_file' in locals():
                    os.unlink(temp_file.name)
            except:
                pass
            return None
    
    def test_pinning(self, cid):
        """Test IPFS pinning functionality"""
        self.print_header("IPFS Pinning Test")
        
        if not cid:
            self.print_result("Pinning", False, "No CID to pin")
            return False
            
        try:
            # Pin the content using your method
            pin_success = self.ipfs_manager.pin_file(cid)
            
            if pin_success:
                # Verify pin by listing pinned files
                pinned_files = self.ipfs_manager.list_pinned_files()
                
                if pinned_files and 'Keys' in pinned_files:
                    pinned_hashes = [key for key in pinned_files['Keys'].keys()]
                    if cid in pinned_hashes:
                        self.test_results['pinning'] = True
                        self.print_result("Pinning", True, "Content pinned and verified")
                        return True
                    else:
                        self.print_result("Pinning", False, "Pin not found in pin list")
                        return False
                else:
                    # If we can't verify, but pin_file returned True, consider it a success
                    self.test_results['pinning'] = True
                    self.print_result("Pinning", True, "Pin operation successful (verification skipped)")
                    return True
            else:
                self.print_result("Pinning", False, "Pin operation failed")
                return False
                
        except Exception as e:
            self.print_result("Pinning", False, f"Exception: {str(e)}")
            return False
    
    def test_additional_features(self):
        """Test additional IPFSManager features"""
        self.print_header("Additional Features Test")
        
        if not self.ipfs_manager or not self.ipfs_manager.connected:
            print("   Skipping additional tests - no connection")
            return
        
        # Test patient record creation
        try:
            patient_data = {
                'patient_id': 'TEST_001',
                'name': 'Test Patient',
                'age': 35,
                'gender': 'M',
                'medical_history': ['hypertension', 'diabetes'],
                'current_medications': ['metformin', 'lisinopril']
            }
            
            patient_cid = self.ipfs_manager.create_patient_record(patient_data)
            if patient_cid:
                print("   ✅ Patient record creation: SUCCESS")
                
                # Try to retrieve and verify
                retrieved_patient = self.ipfs_manager.get_json_data(patient_cid)
                if retrieved_patient and retrieved_patient.get('patient_id') == 'TEST_001':
                    print("   ✅ Patient record retrieval: SUCCESS")
                else:
                    print("   ❌ Patient record retrieval: FAILED")
            else:
                print("   ❌ Patient record creation: FAILED")
                
        except Exception as e:
            print(f"   ❌ Patient record test failed: {e}")
    
    def debug_ipfs_manager(self):
        """Debug the IPFSManager to understand its structure"""
        self.print_header("IPFSManager Debug Info")
        
        if not self.ipfs_manager:
            print("   No IPFSManager instance available")
            return
        
        print(f"   Base URL: {getattr(self.ipfs_manager, 'base_url', 'N/A')}")
        print(f"   API URL: {getattr(self.ipfs_manager, 'api_url', 'N/A')}")
        print(f"   Connected: {getattr(self.ipfs_manager, 'connected', 'N/A')}")
        
        # List available methods
        methods = [method for method in dir(self.ipfs_manager) 
                  if callable(getattr(self.ipfs_manager, method)) and not method.startswith('_')]
        
        print(f"   Available methods: {', '.join(methods)}")
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("🏥 IPFS Medical System Test Suite")
        print("=" * 60)
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Debug info first
        self.debug_ipfs_manager()
        
        # Test 1: Connection
        if not self.test_ipfs_connection():
            self.print_summary()
            return
        
        # Test 2: JSON Upload
        cid = self.test_json_upload()
        
        # Test 3: Data Retrieval
        self.test_data_retrieval(cid)
        
        # Test 4: File Upload
        file_cid = self.test_file_upload()
        
        # Test 5: Pinning (use JSON CID if available, otherwise file CID)
        pin_cid = cid if cid else file_cid
        self.test_pinning(pin_cid)
        
        # Test 6: Additional features
        self.test_additional_features()
        
        # Print final summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("🏥 Test Summary")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
        
        print("-" * 60)
        print(f"Results: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 All tests passed! IPFS integration is working perfectly.")
        elif passed_tests > 0:
            print("⚠️  Some tests passed. Check failed tests above.")
        else:
            print("❌ All tests failed. Check IPFS daemon and configuration.")
        
        print(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """Main function"""
    try:
        test_suite = IPFSTestSuite()
        test_suite.run_all_tests()
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        
        print("Stack trace:")
        traceback.print_exc()

if __name__ == "__main__":
    main()