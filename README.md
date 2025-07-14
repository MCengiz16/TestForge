# 🧪 TestForge - Intelligent Test Automation Platform

AI-powered test automation that converts natural language into accurate Playwright scripts using real browser interaction and element discovery.

## ✨ Features

- **🤖 Natural Language to Code**: Write test cases in plain English, get professional Playwright scripts
- **🔍 AI Element Discovery**: Real browser interaction finds the most reliable selectors
- **🎭 Live Browser View**: Watch the AI agent work in real-time through VNC
- **📊 Complete Test Reports**: HTML reports with screenshots, videos, and traces
- **⚡ 1:1 Step Mapping**: Each natural language step becomes one test.step() for clear reporting

## 🚀 Quick Start

### 1. Clone & Start
```bash
git clone https://github.com/MCengiz16/TestForge.git
cd TestForge
docker-compose up --build
```

### 2. Configure Settings
1. **Access WebUI**: http://localhost:7788
2. **Go to "🔧 Agent Settings" tab**
3. **Configure your LLM**:
   - Provider: `openai`
   - Model: `gpt-4o-mini`
   - API Key: Your OpenAI API key
   - Base URL: `https://api.openai.com/v1`
4. **Click "💾 Save Settings"**

### 3. Create Your First Test
1. **Go to "🧪 Test Automation" tab**
2. **Fill in test details**:
   - Test Name: `User Login Flow`
   - URL: `https://www.saucedemo.com`
   - Steps:
     ```
     Navigate to the login page
     Type "standard_user" into username field
     Type "secret_sauce" into password field
     Click the login button
     Verify that welcome message contains "Products"
     ```
3. **Click "🚀 Create Test & Explore"**
4. **Watch the magic happen** in the Live Browser View!

## 🎯 How It Works

1. **AI Agent Exploration**: Browser agent navigates your site and discovers real element selectors
2. **Smart Script Generation**: AI converts your natural language into professional Playwright code
3. **Test Execution**: Generated scripts run with full reporting and error handling
4. **Results & Reports**: Get detailed HTML reports with screenshots and videos

## 🖥️ Interface

- **WebUI**: http://localhost:7788 - Main application interface
- **VNC Viewer**: http://localhost:6080 - Watch live browser interactions
- **Reports**: http://localhost:7789 - Access test execution reports

## 📋 Example Generated Script

From this natural language:
```
Navigate to login page
Enter username and password
Click login button
Verify dashboard appears
```

Gets this professional Playwright script:
```javascript
test.describe('User Login Flow', () => {
  test('should complete user login flow', async ({ page }) => {
    
    await test.step('Navigate to login page', async () => {
      await page.goto('https://www.saucedemo.com');
      await page.waitForLoadState('networkidle');
    });
    
    await test.step('Enter username and password', async () => {
      const usernameField = page.locator('[data-test="username"]')
        .or(page.locator('#user-name'))
        .or(page.locator('input[name="user-name"]'));
      await usernameField.fill('standard_user');
    });
    
    await test.step('Verify dashboard appears', async () => {
      await expect(page.locator('.title')).toContainText('Products');
    });
  });
});
```

## 🔧 Requirements

- Docker & Docker Compose
- OpenAI API key (or other supported LLM provider)

### Platform Support
- ✅ **Linux**: Full support with native X11
- ✅ **macOS**: Full support via VNC (recommended)
- ✅ **Windows**: Full support via VNC (recommended)

> **Note**: Live browser viewing works through VNC on all platforms at http://localhost:6080

## 💾 Settings

Settings are stored locally in a `settings/` directory and persist across restarts. Your API keys and configuration are never committed to git.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

---

Transform your manual testing into automated scripts with the power of AI! 🚀