# 🚀 Live Agent Demo & Report Access Guide

## 🎯 **What You Asked For:**

### 1. 👀 **Live Agent Following Steps**
- **VNC Browser View:** http://localhost:6080
- **Main Platform:** http://localhost:7788

### 2. 🔗 **Direct Report Links**
- Report links appear in the **Test Execution Log** after test completion
- Click the `file://` links to open Playwright reports directly

---

## 📋 **Quick Demo Steps:**

### Step 1: Open Both Views
1. **Main Platform:** http://localhost:7788
2. **Live Browser:** http://localhost:6080 (in new tab/window)

### Step 2: Set Up Test
1. Go to **Agent Settings** tab → Configure API key
2. Go to **Test Automation** tab
3. Create test:
   - **Name:** `SauceLabs Demo`
   - **URL:** `https://www.saucedemo.com/v1/`
   - **Steps:**
     ```
     Navigate to https://www.saucedemo.com/v1/
     Type "standard_user" into username field
     Type "secret_sauce" into password field
     Click login button
     Verify that "Sauce Labs Backpack" text is present on page
     ```

### Step 3: Watch Agent Live
1. **IMPORTANT:** Keep VNC tab open: http://localhost:6080
2. Click **🔍 Explore Page**
3. **Watch the magic:** You'll see:
   - Browser opening in VNC
   - Agent navigating to SauceLabs
   - Agent typing in fields
   - Agent clicking buttons
   - Element discovery in real-time

### Step 4: Get Report Link
1. After exploration, click **🎭 Run Playwright Test**
2. In **Test Execution Log** you'll see:
   ```
   🔗 Direct Report Link: file:///app/tmp/test_results/[test-id]/playwright-report/index.html
   💡 Click the link above to open the full Playwright report
   ```
3. **Click that file:// link** to open the complete Playwright report

---

## 🎥 **What You'll See in VNC:**

1. **Virtual Desktop** appears at http://localhost:6080
2. **Browser automatically opens** when you click "Explore Page"
3. **Agent performs actions:**
   - Navigates to SauceLabs
   - Analyzes the login form
   - Types username and password
   - Clicks login button
   - Explores products page
   - Discovers element selectors

4. **Real-time feedback** in the main platform logs

---

## 🎯 **Expected Results:**

### Exploration Log Will Show:
```
🔍 Starting page exploration to discover elements...
📍 Navigating to target URL...
🤖 Agent is exploring the page...
👀 WATCH AGENT LIVE: http://localhost:6080
🔗 Click the link above to see the browser in action!
🚀 Starting agent execution...
✅ Step 1: action: reasoning (Found X elements)
✅ Step 2: action: reasoning (Found Y elements)
🎯 Agent execution completed successfully
🎉 Exploration complete! Discovered 6 elements
```

### Test Execution Log Will Show:
```
🎭 Running Playwright test with discovered locators...
📝 Created test file: /app/tmp/test_results/.../test.spec.js
⚙️ Created Playwright configuration
📦 Installing Playwright dependencies...
✅ Playwright installed successfully
🚀 Executing Playwright test...
📊 Test execution completed with exit code: 0
📈 Test Results: 1 passed, 0 failed
🎉 Test execution completed!
🔗 Direct Report Link: file:///app/tmp/test_results/.../playwright-report/index.html
💡 Click the link above to open the full Playwright report
```

---

## 🔧 **If Agent Doesn't Show:**

1. **Check VNC is open:** http://localhost:6080
2. **Wait 30-60 seconds** after clicking "Explore Page"
3. **Look for browser window** in VNC desktop
4. **Check exploration log** for "Starting agent execution..."

---

## 🎉 **You'll Get:**

✅ **Live agent demonstration** in VNC browser  
✅ **Direct clickable report links** in execution log  
✅ **Complete Playwright reports** with screenshots and videos  
✅ **Real element selectors** discovered by AI agent  

Your intelligent test automation platform is ready to demonstrate real AI-powered testing with live visual feedback!