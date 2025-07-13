#!/usr/bin/env python3
"""
Test the actual interface functionality by making API calls
"""
import requests
import json
import time

def test_interface_availability():
    """Test if both interfaces are accessible"""
    print("🔍 Testing Interface Accessibility")
    print("=" * 50)
    
    try:
        # Test main interface
        response = requests.get("http://localhost:7788", timeout=10)
        if response.status_code == 200:
            print("✅ Main interface accessible (HTTP 200)")
            
            # Check for test automation tab
            if "🧪 Test Automation" in response.text:
                print("✅ Test Automation tab found in interface")
            else:
                print("❌ Test Automation tab not found")
                return False
        else:
            print(f"❌ Main interface returned {response.status_code}")
            return False
        
        # Test VNC interface
        vnc_response = requests.get("http://localhost:6080", timeout=5)
        if vnc_response.status_code == 200:
            print("✅ VNC interface accessible (HTTP 200)")
            if "noVNC" in vnc_response.text:
                print("✅ noVNC interface loaded")
            else:
                print("❌ noVNC not properly loaded")
                return False
        else:
            print(f"❌ VNC interface returned {vnc_response.status_code}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Interface test failed: {e}")
        return False

def test_create_test_case():
    """Test creating a test case via API"""
    print("\n🔍 Testing Test Case Creation")
    print("=" * 50)
    
    try:
        # First get the interface to find the session hash
        response = requests.get("http://localhost:7788", timeout=10)
        
        # Extract session hash from the page
        import re
        session_match = re.search(r'"session_hash":"([^"]+)"', response.text)
        if session_match:
            session_hash = session_match.group(1)
            print(f"✅ Found session hash: {session_hash[:16]}...")
        else:
            print("❌ Could not find session hash")
            return False
        
        # Test case data
        test_data = {
            "data": [
                "SauceLabs Demo Test",  # test_name
                "https://www.saucedemo.com/v1/",  # test_url  
                "Navigate to https://www.saucedemo.com/v1/\nType \"standard_user\" into username field\nType \"secret_sauce\" into password field\nClick login button\nVerify that \"Sauce Labs Backpack\" text is present on page"  # test_steps
            ],
            "session_hash": session_hash
        }
        
        # Try to create test case
        api_url = "http://localhost:7788/gradio_api/call/create_test"
        response = requests.post(api_url, json=test_data, timeout=10)
        
        if response.status_code == 200:
            print("✅ Test case creation API call successful")
            return True
        else:
            print(f"❌ Test case creation failed: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Test case creation failed: {e}")
        return False

def test_vnc_passwordless():
    """Test VNC access without password"""
    print("\n🔍 Testing VNC Passwordless Access")
    print("=" * 50)
    
    try:
        # Check if VNC HTML contains any password prompts
        response = requests.get("http://localhost:6080/vnc.html", timeout=5)
        
        if response.status_code == 200:
            print("✅ VNC HTML page accessible")
            
            # Look for password-related elements
            if "password" in response.text.lower():
                print("⚠️ VNC page may still require password")
                return False
            else:
                print("✅ No password prompts detected in VNC interface")
                return True
        else:
            print(f"❌ VNC HTML page returned {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ VNC test failed: {e}")
        return False

def main():
    """Run all interface tests"""
    print("🧪 Complete Interface Functionality Test")
    print("=" * 60)
    
    tests = [
        ("Interface Accessibility", test_interface_availability),
        ("VNC Passwordless Access", test_vnc_passwordless),
        ("Test Case Creation", test_create_test_case)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n🎯 Interface Test Results")
    print("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL INTERFACE TESTS PASSED!")
        print("The intelligent test automation platform is working correctly:")
        print("• Main platform accessible with Test Automation tab")
        print("• VNC browser view accessible without password")
        print("• Test case creation API functional")
        return True
    else:
        print(f"\n❌ {total - passed} interface tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)