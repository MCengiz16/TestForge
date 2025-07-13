# 🧪 Test Automation Platform - Usage Guide

## Clean & Simple Interface

The platform now has a streamlined interface with just **2 tabs**:

### 1. ⚙️ Agent Settings
- **LLM Configuration**: Choose your AI provider (OpenAI, Anthropic, etc.)
- **Browser Settings**: Configure browser behavior
- **All settings in one place** - no need to navigate multiple tabs

### 2. 🧪 Test Automation
- **Left Panel**: Create and manage tests
- **Right Panel**: View scripts and execution results

## How to Use

### Step 1: Configure Agent Settings
1. Go to **Agent Settings** tab
2. Set your **LLM Provider** (e.g., OpenAI)
3. Enter your **API Key**
4. Configure **Browser Settings** if needed

### Step 2: Create a Test
1. Go to **Test Automation** tab
2. Enter **Test Name** (e.g., "Login Test")
3. Enter **Starting URL** (e.g., "https://example.com/login")
4. Write **Test Steps** in natural language:
   ```
   Navigate to https://example.com/login
   Type "user@example.com" into email field
   Type "password123" into password field
   Click login button
   Verify that dashboard contains "Welcome"
   Take screenshot
   ```
5. Click **🚀 Create Test**

### Step 3: View Generated Script
- The **Playwright script** appears automatically on the right
- It's a complete JavaScript test file ready to use
- Includes proper waits, assertions, and error handling

### Step 4: Execute Test
1. Select your test from the **dropdown**
2. Click **▶️ Execute Test**
3. Watch the **execution log** in real-time
4. See status updates as each step runs

### Step 5: Download Results
- Click **💾 Download Script** to get the `.spec.js` file
- Use it directly in your Playwright test suite
- All screenshots and videos are saved automatically

## Example Test

**Test Name:** Login Test
**URL:** https://example.com/login
**Steps:**
```
Navigate to https://example.com/login
Type "testuser" into username field
Type "password123" into password field
Click login button
Verify that welcome message contains "Hello"
```

**Generated Script:**
```javascript
const { test, expect } = require('@playwright/test');

test('Login Test', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    
    // Step 1: Navigate to https://example.com/login
    await page.goto('https://example.com/login');
    await page.waitForLoadState('networkidle');

    // Step 2: Type 'testuser' into username field
    await page.fill('text=username field', 'testuser');

    // Step 3: Type 'password123' into password field
    await page.fill('text=password field', 'password123');

    // Step 4: Click login button
    await page.click('text=login button');

    // Step 5: Verify welcome message contains 'Hello'
    await expect(page.locator('text=welcome message')).toContainText('Hello');

    // Final screenshot
    await page.screenshot({ path: 'test-complete.png', fullPage: true });
});
```

## Benefits

✅ **Simple Interface** - Only what you need, nothing extra
✅ **Natural Language** - Write tests in plain English
✅ **Instant Scripts** - Get Playwright code immediately
✅ **Live Execution** - Watch tests run in real-time
✅ **Complete Results** - Scripts, logs, screenshots, videos
✅ **Ready to Use** - Download and run in your CI/CD

## Access

Navigate to: **http://localhost:7788**

The platform is running in Docker with all dependencies included!