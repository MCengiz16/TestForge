# Settings Configuration

This application uses persistent settings stored in the `settings/` directory. This directory is automatically created and **excluded from git** to protect user privacy.

## 🔧 Agent Settings (LLM Configuration)

Settings saved to: `settings/.webui_agent_settings.json`

**Configure via UI**: 🔧 Agent Settings tab

- **LLM Provider**: OpenAI, Anthropic, etc.
- **Model Name**: gpt-4o-mini, claude-3-sonnet, etc.
- **API Key**: Your API key (encrypted storage)
- **Base URL**: API endpoint URL
- **Temperature**: Randomness control (0.0-2.0)

**Usage**:
1. Configure settings in the UI
2. Click "💾 Save Settings" 
3. Settings persist across restarts

## ⚙️ Test Settings (AI Prompt & Playwright Config)

Settings saved to: `settings/.webui_test_settings.json`

**Configure via UI**: ⚙️ Test Settings tab

- **AI Prompt Template**: Custom prompt for test generation
- **Playwright Configuration**: Browser and test execution settings

**Usage**:
1. Customize AI prompt and Playwright config
2. Click "💾 Save to File"
3. Settings persist across restarts

## 🔒 Privacy & Security

- **Not tracked by git**: Settings directory is in `.gitignore`
- **Local storage only**: Settings stored in Docker volume
- **No sharing**: Each user maintains their own settings
- **API keys protected**: Stored locally, never committed to repo

## 📁 File Structure

```
settings/
├── .webui_agent_settings.json     # LLM configuration
├── .webui_test_settings.json      # Test generation settings
└── ... (other user-specific files)
```

## 🚀 For Public Repositories

This setup ensures:
- ✅ No API keys or sensitive data in git
- ✅ No user settings committed to repo
- ✅ Clean public repository
- ✅ Each user maintains private settings
- ✅ Easy setup for new users

## 🔄 Resetting Settings

To reset all settings:
1. Stop the application: `docker-compose down`
2. Remove settings: `rm -rf settings/`
3. Restart: `docker-compose up -d`
4. Reconfigure in UI

## 🐛 Troubleshooting

**Settings not loading?**
- Check if `settings/` directory exists
- Verify Docker volume mount is working
- Check file permissions

**Settings not saving?**
- Ensure Docker container has write permissions
- Check Docker logs for errors
- Verify buttons are clicked after changes