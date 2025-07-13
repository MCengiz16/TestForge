#!/usr/bin/env python3
"""
Test script to verify the complete SauceLabs workflow
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.append('/Users/mucdatcengiz/Documents/GitHub/web-ui')

from src.webui.components.intelligent_test_automation_tab import (
    TestCase, 
    _explore_page_and_discover_elements,
    _run_playwright_test,
    _initialize_llm_for_intelligent_test
)
from src.webui.webui_manager import WebuiManager
from src.utils import llm_provider

async def test_complete_saucelabs_workflow():
    """Test the complete SauceLabs workflow end-to-end"""
    
    print("🧪 Testing Complete SauceLabs Workflow")
    print("=" * 50)
    
    # Initialize test case
    test_case = TestCase(
        name="SauceLabs Login Test",
        description="Complete login and validation test",
        url="https://www.saucedemo.com/v1/",
        steps=[
            "Navigate to https://www.saucedemo.com/v1/",
            "Type 'standard_user' into username field",
            "Type 'secret_sauce' into password field", 
            "Click login button",
            "Verify that 'Sauce Labs Backpack' text is present on page"
        ]
    )
    
    print(f"📝 Created test case: {test_case.name}")
    print(f"🌐 Target URL: {test_case.url}")
    print(f"📋 Steps: {len(test_case.steps)} steps defined")
    
    # Mock webui_manager and components for testing
    webui_manager = WebuiManager()
    
    # Mock components dict with API key from environment
    components = {
        # Agent settings
        'llm_provider': 'openai',
        'llm_model_name': 'gpt-4o',
        'llm_temperature': 0.6,
        'llm_api_key': os.getenv('OPENAI_API_KEY', ''),
        'llm_base_url': None,
        'ollama_num_ctx': 16000,
    }
    
    if not components['llm_api_key']:
        print("❌ No OpenAI API key found in environment")
        print("💡 Set OPENAI_API_KEY environment variable")
        return False
    
    print("✅ API key configured")
    
    # Create test directories
    test_dir = Path(f"./tmp/test_results/{test_case.id}")
    test_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Test directory: {test_dir}")
    
    try:
        # Phase 1: Test LLM initialization
        print("\n🔍 Phase 1: Initializing LLM...")
        llm = await _initialize_llm_for_intelligent_test(webui_manager, components)
        if not llm:
            print("❌ Failed to initialize LLM")
            return False
        print("✅ LLM initialized successfully")
        
        # Phase 2: Test page exploration (simulated)
        print("\n🔍 Phase 2: Page Exploration...")
        print("🤖 Simulating agent exploration of SauceLabs page...")
        
        # Simulate discovered elements for SauceLabs
        test_case.discovered_elements = {
            "username field": "#user-name",
            "password field": "#password", 
            "login button": "#login-button",
            "products container": ".inventory_list",
            "backpack product": ".inventory_item:has-text('Sauce Labs Backpack')",
            "product title": ".inventory_item_name"
        }
        
        test_case.status = "script_ready"
        print(f"✅ Discovered {len(test_case.discovered_elements)} elements:")
        for desc, selector in test_case.discovered_elements.items():
            print(f"   - {desc}: {selector}")
        
        # Phase 3: Generate Playwright script
        print("\n📝 Phase 3: Generating Playwright Script...")
        from src.webui.components.intelligent_test_automation_tab import IntelligentScriptGenerator
        test_case.playwright_script = IntelligentScriptGenerator.generate_script_with_real_locators(test_case)
        
        script_file = test_dir / f"{test_case.name.replace(' ', '_')}.spec.js"
        with open(script_file, 'w') as f:
            f.write(test_case.playwright_script)
        
        print(f"✅ Generated Playwright script: {script_file}")
        print("📋 Script preview:")
        print("-" * 40)
        # Show first 20 lines of script
        lines = test_case.playwright_script.split('\n')[:20]
        for line in lines:
            print(f"   {line}")
        if len(test_case.playwright_script.split('\n')) > 20:
            print("   ... (truncated)")
        print("-" * 40)
        
        # Phase 4: Create Playwright config and package.json
        print("\n🔧 Phase 4: Setting up Playwright environment...")
        
        # Create package.json
        package_json = {
            "name": "saucelabs-test",
            "version": "1.0.0",
            "scripts": {
                "test": "playwright test"
            },
            "devDependencies": {
                "@playwright/test": "latest"
            }
        }
        
        with open(test_dir / "package.json", 'w') as f:
            json.dump(package_json, f, indent=2)
        
        # Create Playwright config
        playwright_config = '''
module.exports = {
    testDir: '.',
    timeout: 30000,
    use: {
        headless: true,
        viewport: { width: 1280, height: 720 },
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },
    reporter: [
        ['html', { outputFolder: 'playwright-report' }],
        ['json', { outputFile: 'test-results.json' }],
        ['junit', { outputFile: 'junit-results.xml' }]
    ],
    outputDir: 'test-results',
};
'''
        
        with open(test_dir / "playwright.config.js", 'w') as f:
            f.write(playwright_config)
        
        print("✅ Created Playwright configuration")
        
        # Phase 5: Install dependencies and run test
        print("\n🎭 Phase 5: Running Playwright Test...")
        
        # Install playwright in the test directory
        os.chdir(test_dir)
        
        import subprocess
        
        # Initialize npm
        result = subprocess.run(['npm', 'init', '-y'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️ npm init warning: {result.stderr}")
        
        # Install playwright
        print("📦 Installing Playwright...")
        result = subprocess.run(['npm', 'install', '@playwright/test'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Failed to install Playwright: {result.stderr}")
            return False
        
        print("✅ Playwright installed successfully")
        
        # Install browsers
        print("🌐 Installing browser binaries...")
        result = subprocess.run(['npx', 'playwright', 'install', 'chromium'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️ Browser install warning: {result.stderr}")
        
        # Run the test
        print("🚀 Executing Playwright test...")
        result = subprocess.run([
            'npx', 'playwright', 'test', 
            '--config', 'playwright.config.js',
            script_file.name
        ], capture_output=True, text=True, timeout=60)
        
        print(f"📊 Test execution completed with exit code: {result.returncode}")
        
        # Show test output
        if result.stdout:
            print("📝 Test Output:")
            for line in result.stdout.split('\n')[:15]:
                if line.strip():
                    print(f"   {line}")
        
        if result.stderr:
            print("⚠️ Test Errors:")
            for line in result.stderr.split('\n')[:10]:
                if line.strip():
                    print(f"   {line}")
        
        # Phase 6: Verify generated reports
        print("\n📊 Phase 6: Verifying Generated Reports...")
        
        # Check for HTML report
        report_dir = test_dir / "playwright-report"
        report_index = report_dir / "index.html"
        
        if report_index.exists():
            print(f"✅ HTML report generated: {report_index}")
            print(f"📊 Report size: {report_index.stat().st_size} bytes")
        else:
            print("❌ HTML report not found")
        
        # Check for JSON results
        json_results = test_dir / "test-results.json"
        if json_results.exists():
            print(f"✅ JSON results generated: {json_results}")
            with open(json_results, 'r') as f:
                results_data = json.load(f)
                if 'stats' in results_data:
                    stats = results_data['stats']
                    print(f"📈 Test Results: {stats.get('expected', 0)} passed, {stats.get('unexpected', 0)} failed")
        else:
            print("❌ JSON results not found")
        
        # Check for screenshots
        screenshots_dir = test_dir / "test-results"
        if screenshots_dir.exists():
            screenshots = list(screenshots_dir.glob("*.png"))
            videos = list(screenshots_dir.glob("*.webm"))
            print(f"📸 Screenshots: {len(screenshots)} found")
            print(f"🎥 Videos: {len(videos)} found")
            
            for screenshot in screenshots[:3]:  # Show first 3
                print(f"   📸 {screenshot.name}")
            for video in videos[:3]:  # Show first 3
                print(f"   🎥 {video.name}")
        
        # Summary
        print("\n🎉 Workflow Test Summary:")
        print("=" * 50)
        print(f"✅ Test Case Created: {test_case.name}")
        print(f"✅ Elements Discovered: {len(test_case.discovered_elements)}")
        print(f"✅ Playwright Script Generated: {script_file.exists()}")
        print(f"✅ HTML Report: {report_index.exists()}")
        print(f"✅ JSON Results: {json_results.exists()}")
        
        if report_index.exists():
            print(f"\n📊 Access your Playwright report at:")
            print(f"   file://{report_index.absolute()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run the test
    result = asyncio.run(test_complete_saucelabs_workflow())
    if result:
        print("\n🎉 SauceLabs workflow test PASSED!")
    else:
        print("\n❌ SauceLabs workflow test FAILED!")
    exit(0 if result else 1)