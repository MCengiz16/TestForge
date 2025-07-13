#!/usr/bin/env python3
"""
Direct Playwright test creation for SauceLabs scenario
"""
import os
import json
import subprocess

def create_saucelabs_test():
    """Create a complete Playwright test for SauceLabs with the discovered selectors"""
    
    print("🧪 Creating Direct SauceLabs Playwright Test")
    print("=" * 50)
    
    # Create test directory
    test_dir = "./tmp/saucelabs_test"
    os.makedirs(test_dir, exist_ok=True)
    print(f"📁 Created test directory: {test_dir}")
    
    # Generate the Playwright test with real SauceLabs selectors
    playwright_test = '''// SauceLabs Login Test
// Generated with discovered real selectors
// Generated: 2025-07-13

const { test, expect } = require('@playwright/test');

test.describe('SauceLabs Login Test', () => {
    test('should complete saucelabs login test', async ({ page }) => {
        // Test configuration
        await page.setViewportSize({ width: 1280, height: 720 });
        
        // Start test execution
        console.log('Starting test: SauceLabs Login Test');
        
        // Step 1: Navigate to https://www.saucedemo.com/v1/
        await page.goto('https://www.saucedemo.com/v1/');
        await page.waitForLoadState('networkidle');
        await page.screenshot({ path: 'step-1-navigate.png' });

        // Step 2: Type 'standard_user' into username field
        // Wait for input field and type text
        await page.waitForSelector('#user-name', { visible: true });
        await page.fill('#user-name', 'standard_user');
        await page.screenshot({ path: 'step-2-username.png' });

        // Step 3: Type 'secret_sauce' into password field
        // Wait for input field and type text
        await page.waitForSelector('#password', { visible: true });
        await page.fill('#password', 'secret_sauce');
        await page.screenshot({ path: 'step-3-password.png' });

        // Step 4: Click login button
        // Wait for element and click
        await page.waitForSelector('#login-button', { visible: true });
        await page.click('#login-button');
        await page.waitForLoadState('networkidle');
        await page.screenshot({ path: 'step-4-login.png' });

        // Step 5: Verify that 'Sauce Labs Backpack' text is present on page
        // Verification step - target the first product specifically
        await expect(page.locator('.inventory_item_name').first()).toContainText('Sauce Labs Backpack');
        await page.screenshot({ path: 'step-5-verify.png' });

        // Final verification screenshot
        await page.screenshot({ path: 'test-completed.png', fullPage: true });
        
        console.log('Test completed successfully: SauceLabs Login Test');
    });
});
'''
    
    # Write the test file
    test_file = os.path.join(test_dir, "saucelabs.spec.js")
    with open(test_file, 'w') as f:
        f.write(playwright_test)
    print(f"✅ Created test file: {test_file}")
    
    # Create package.json
    package_json = {
        "name": "saucelabs-test",
        "version": "1.0.0",
        "scripts": {
            "test": "playwright test",
            "test:headed": "playwright test --headed",
            "report": "playwright show-report"
        },
        "devDependencies": {
            "@playwright/test": "^1.40.0"
        }
    }
    
    with open(os.path.join(test_dir, "package.json"), 'w') as f:
        json.dump(package_json, f, indent=2)
    print("✅ Created package.json")
    
    # Create Playwright config with comprehensive reporting
    playwright_config = '''
module.exports = {
    testDir: '.',
    timeout: 30000,
    expect: {
        timeout: 5000
    },
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: [
        ['html', { 
            outputFolder: 'playwright-report',
            open: 'never'
        }],
        ['json', { 
            outputFile: 'test-results.json' 
        }],
        ['junit', { 
            outputFile: 'junit-results.xml' 
        }],
        ['list']
    ],
    use: {
        baseURL: 'https://www.saucedemo.com',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
        viewport: { width: 1280, height: 720 },
        ignoreHTTPSErrors: true,
    },
    outputDir: 'test-results/',
    projects: [
        {
            name: 'chromium',
            use: { ...require('@playwright/test').devices['Desktop Chrome'] },
        },
    ],
};
'''
    
    with open(os.path.join(test_dir, "playwright.config.js"), 'w') as f:
        f.write(playwright_config)
    print("✅ Created Playwright config")
    
    return test_dir

def run_playwright_test(test_dir):
    """Run the Playwright test and generate reports"""
    
    print(f"\n🎭 Running Playwright Test in {test_dir}")
    print("=" * 50)
    
    # Change to test directory
    original_dir = os.getcwd()
    os.chdir(test_dir)
    
    try:
        # Install dependencies
        print("📦 Installing Playwright...")
        result = subprocess.run(['npm', 'install'], 
                              capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"❌ npm install failed: {result.stderr}")
            return False
        print("✅ Dependencies installed")
        
        # Install browsers
        print("🌐 Installing browser binaries...")
        result = subprocess.run(['npx', 'playwright', 'install', 'chromium'], 
                              capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"⚠️ Browser install warning: {result.stderr}")
        
        # Run the test
        print("🚀 Executing Playwright test...")
        result = subprocess.run(['npx', 'playwright', 'test'], 
                              capture_output=True, text=True, timeout=120)
        
        print(f"📊 Test execution completed with exit code: {result.returncode}")
        
        # Show test output
        if result.stdout:
            print("📝 Test Output:")
            print(result.stdout)
        
        if result.stderr and result.returncode != 0:
            print("⚠️ Test Errors:")
            print(result.stderr)
        
        # Check generated files
        print("\n📊 Checking Generated Reports...")
        
        files_to_check = [
            ("playwright-report/index.html", "HTML Report"),
            ("test-results.json", "JSON Results"),
            ("junit-results.xml", "JUnit XML"),
            ("test-results/", "Screenshots/Videos")
        ]
        
        for file_path, description in files_to_check:
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    print(f"✅ {description}: {file_path} ({size} bytes)")
                else:
                    # Directory
                    files = os.listdir(file_path)
                    print(f"✅ {description}: {len(files)} files")
                    for f in files[:5]:  # Show first 5 files
                        print(f"   📄 {f}")
            else:
                print(f"❌ {description}: {file_path} not found")
        
        # Generate report summary
        if os.path.exists("test-results.json"):
            try:
                with open("test-results.json", 'r') as f:
                    results = json.load(f)
                    
                print(f"\n📈 Test Results Summary:")
                if 'stats' in results:
                    stats = results['stats']
                    print(f"   ✅ Passed: {stats.get('expected', 0)}")
                    print(f"   ❌ Failed: {stats.get('unexpected', 0)}")
                    print(f"   ⏰ Duration: {stats.get('duration', 0)}ms")
                
                if 'suites' in results:
                    for suite in results['suites']:
                        if 'specs' in suite:
                            for spec in suite['specs']:
                                print(f"   📋 {spec.get('title', 'Unknown')}: {spec.get('ok', False)}")
                                
            except Exception as e:
                print(f"⚠️ Could not parse results: {e}")
        
        # Show how to access reports
        report_path = os.path.abspath("playwright-report/index.html")
        if os.path.exists(report_path):
            print(f"\n🎉 SUCCESS! Access your Playwright report at:")
            print(f"   file://{report_path}")
            print(f"\n📊 Or run: npx playwright show-report")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Test execution timed out")
        return False
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    # Create and run the test
    test_dir = create_saucelabs_test()
    success = run_playwright_test(test_dir)
    
    if success:
        print("\n🎉 SauceLabs Playwright test completed successfully!")
        print(f"📁 All files available in: {os.path.abspath(test_dir)}")
    else:
        print("\n❌ SauceLabs Playwright test failed!")
    
    exit(0 if success else 1)