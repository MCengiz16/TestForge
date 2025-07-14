# Settings Directory

When you run `docker-compose up`, a `settings/` directory will be automatically created here to store your personal configuration.

## 📁 Directory Structure (Auto-created)

```
settings/
├── .webui_agent_settings.json     # Your LLM configuration (API keys, provider, model)
├── .webui_test_settings.json      # Your test generation settings
└── ... (other user-specific files)
```

## 🔧 First-Time Setup

1. **Start the application:**
   ```bash
   docker-compose up -d
   ```

2. **Access the WebUI:** http://localhost:7788

3. **Configure your settings:**
   - Go to "🔧 Agent Settings" tab
   - Set your LLM provider and API key
   - Click "💾 Save Settings"

4. **Your settings will be saved to the `settings/` directory**

## 🔒 Privacy & Security

- ✅ **Private to you**: Settings are stored locally
- ✅ **Not in git**: The `settings/` directory is in `.gitignore`
- ✅ **No sharing**: Your API keys stay on your machine
- ✅ **Persistent**: Settings survive container restarts

## 🆕 For New Users

When you clone this repository:
1. The `settings/` directory doesn't exist yet
2. Run `docker-compose up -d` to create it
3. Configure your settings in the WebUI
4. Settings files are created automatically when you save

## 🔄 Resetting Settings

To start fresh:
```bash
docker-compose down
rm -rf settings/
docker-compose up -d
```

Then reconfigure in the WebUI.