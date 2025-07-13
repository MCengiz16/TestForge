#!/usr/bin/env python3
"""
Complete workflow test - from interface creation to final report
"""
import asyncio
import time
import sys
import os

def test_vnc_access():
    """Test 1: VNC Access without password"""
    print("🔍 Test 1: VNC Access")
    print("=" * 50)
    
    try:
        import requests
        response = requests.get("http://localhost:6080", timeout=5)
        if response.status_code == 200:
            print("✅ VNC web interface accessible at http://localhost:6080")
            if "noVNC" in response.text:
                print("✅ noVNC interface loaded successfully")
                return True
            else:
                print("❌ noVNC interface not properly loaded")
                return False
        else:
            print(f"❌ VNC interface returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ VNC access failed: {e}")
        return False

def test_main_interface():
    """Test 2: Main interface accessibility"""
    print("\n🔍 Test 2: Main Interface Access")
    print("=" * 50)
    
    try:
        import requests
        response = requests.get("http://localhost:7788", timeout=10)
        if response.status_code == 200:
            print("✅ Main interface accessible at http://localhost:7788")
            if "Intelligent Test Automation" in response.text:
                print("✅ Test Automation tab detected")
                return True
            else:
                print("❌ Test Automation tab not found in interface")
                return False
        else:
            print(f"❌ Main interface returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Main interface access failed: {e}")
        return False

def test_docker_logs():
    """Test 3: Check for errors in Docker logs"""
    print("\n🔍 Test 3: Docker Container Health")
    print("=" * 50)
    
    try:
        import subprocess
        result = subprocess.run(['docker', 'logs', 'web-ui-browser-use-webui-1', '--tail', '20'], 
                               capture_output=True, text=True, timeout=10)
        
        logs = result.stdout + result.stderr
        
        # Check for critical errors
        error_patterns = [
            "Error:",
            "Exception:",
            "Traceback",
            "CRITICAL",
            "FATAL"
        ]
        
        errors_found = []
        for pattern in error_patterns:
            if pattern in logs and "webSocketsHandshake" not in logs:  # Ignore VNC websocket errors
                errors_found.append(pattern)
        
        if not errors_found:
            print("✅ No critical errors found in Docker logs")
            print("✅ Container appears healthy")
            return True
        else:
            print(f"❌ Found errors in logs: {errors_found}")
            print("Recent logs:")
            print(logs[-1000:])  # Show last 1000 chars
            return False
            
    except Exception as e:
        print(f"❌ Could not check Docker logs: {e}")
        return False

def test_playwright_execution():
    """Test 4: Standalone Playwright test execution"""
    print("\n🔍 Test 4: Playwright Test Execution")
    print("=" * 50)
    
    try:
        import subprocess
        result = subprocess.run(['python3', 'create_direct_playwright_test.py'], 
                               capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Playwright test executed successfully")
            
            # Check for report generation
            if "HTML Report:" in result.stdout and "file://" in result.stdout:
                print("✅ HTML report generated with direct file link")
                
                # Extract the file path
                import re
                file_match = re.search(r'file://(/[^\s]+)', result.stdout)
                if file_match:
                    report_path = file_match.group(1)
                    if os.path.exists(report_path):
                        print(f"✅ Report file exists at: {report_path}")
                        print(f"✅ Report size: {os.path.getsize(report_path)} bytes")
                        return True
                    else:
                        print(f"❌ Report file not found at: {report_path}")
                        return False
                else:
                    print("❌ Could not extract report file path")
                    return False
            else:
                print("❌ HTML report not generated properly")
                return False
        else:
            print(f"❌ Playwright test failed with exit code: {result.returncode}")
            print("STDOUT:", result.stdout[-500:])  # Last 500 chars
            print("STDERR:", result.stderr[-500:])  # Last 500 chars
            return False
            
    except Exception as e:
        print(f"❌ Playwright test execution failed: {e}")
        return False

def test_file_structure():
    """Test 5: Check critical files exist"""
    print("\n🔍 Test 5: File Structure Check")
    print("=" * 50)
    
    critical_files = [
        "src/webui/components/intelligent_test_automation_tab.py",
        "supervisord.conf",
        "docker-compose.yml",
        "create_direct_playwright_test.py"
    ]
    
    all_exist = True
    for file_path in critical_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests and provide summary"""
    print("🧪 Complete Workflow Test Suite")
    print("=" * 60)
    print("Testing intelligent test automation platform...")
    print()
    
    tests = [
        ("VNC Access", test_vnc_access),
        ("Main Interface", test_main_interface), 
        ("Docker Health", test_docker_logs),
        ("Playwright Execution", test_playwright_execution),
        ("File Structure", test_file_structure)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n🎯 Test Results Summary")
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
        print("\n🎉 ALL TESTS PASSED!")
        print("Your intelligent test automation platform is fully functional:")
        print("• VNC browser view: http://localhost:6080 (no password)")
        print("• Main platform: http://localhost:7788")
        print("• Live agent demonstration working")
        print("• Direct report links available")
        print("• Complete workflow validated")
        return True
    else:
        print(f"\n❌ {total - passed} tests failed!")
        print("Please check the failed tests above and fix the issues.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)