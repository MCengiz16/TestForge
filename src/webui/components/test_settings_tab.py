import gradio as gr
import json
import os
from src.webui.webui_manager import WebuiManager

# Global variables to store current settings
_current_ai_prompt = None
_current_playwright_config = None

# Enhanced AI prompt template for test script generation
DEFAULT_AI_PROMPT_TEMPLATE = """You are an expert Playwright test automation engineer specializing in creating robust, maintainable test scripts.

Generate a professional Playwright test script with semantic step names and business context.

TEST CASE:
Name: {test_case_name}
URL: {test_case_url}
Steps:
{test_case_steps}

{discovered_elements}

CRITICAL REQUIREMENTS:

1. **Test Structure & Organization:**
   - Use test.describe() for test grouping
   - Use test.step() for each logical business operation
   - Name steps semantically (e.g., "Enter user credentials" not "Fill input fields")
   - Organize into phases: Setup → Action → Verification → Cleanup

2. **Robust Selector Strategy:**
   - Priority: data-testid > id > aria-label > role > text > css
   - ALWAYS include fallback selectors: primary || fallback || 'generic'
   - Use element.locator() with multiple strategies
   - Avoid brittle text-based selectors when possible

3. **Step Comments & Context:**
   - Add business context comments explaining WHY each step matters
   - Connect steps to user stories and acceptance criteria
   - Include debugging hints for common failure points
   - Use semantic variable names that reflect business operations

4. **Error Handling & Robustness:**
   - Use proper waits: waitForLoadState, waitForSelector
   - Add retry mechanisms for flaky operations
   - Include meaningful error messages
   - Handle dynamic content and async operations

5. **Code Quality:**
   - Separate test data from test logic using variables
   - Use descriptive test and step names
   - Include proper assertions with meaningful messages
   - Follow Playwright best practices

EXAMPLE STRUCTURE:
```javascript
test.describe('User Authentication Journey', () => {{
  test('should authenticate valid user and access dashboard', async ({{ page }}) => {{
    
    await test.step('Navigate to application login portal', async () => {{
      // Business context: Start user authentication flow
      await page.goto(testUrl);
      await page.waitForLoadState('networkidle');
    }});
    
    await test.step('Enter user credentials for authentication', async () => {{
      // Business context: Provide valid credentials for access
      const usernameField = page.locator('[data-testid="username"]').or(page.locator('#username')).or(page.locator('input[name="username"]'));
      await usernameField.waitFor({{ state: 'visible' }});
      await usernameField.fill(testData.username);
    }});
    
    await test.step('Verify successful authentication and dashboard access', async () => {{
      // Business context: Confirm user can access protected area
      await expect(page.locator('[data-testid="welcome-message"]').or(page.locator('.welcome'))).toBeVisible();
    }});
  }});
}});
```

Generate ONLY the JavaScript code with this enhanced structure, no explanations:"""

# Simplified Playwright configuration template
DEFAULT_PLAYWRIGHT_CONFIG = """module.exports = {
    testDir: '.',
    timeout: 120000,
    expect: {
        timeout: 30000
    },
    use: {
        headless: false,
        viewport: { width: 1920, height: 1080 },
        actionTimeout: 30000,
        navigationTimeout: 30000,
        screenshot: 'off',
        video: 'on',
        trace: 'on'
    },
    reporter: [
        ['html', { outputFolder: 'playwright-report', open: 'never' }],
        ['json', { outputFile: 'test-results.json' }]
    ],
    outputDir: 'test-results'
};"""

def get_current_ai_prompt():
    """Get the current AI prompt from global variable or default"""
    return _current_ai_prompt if _current_ai_prompt is not None else DEFAULT_AI_PROMPT_TEMPLATE

def get_current_playwright_config():
    """Get the current Playwright config from global variable or default"""
    return _current_playwright_config if _current_playwright_config is not None else DEFAULT_PLAYWRIGHT_CONFIG

def update_global_settings(ai_prompt, playwright_config):
    """Update global settings variables"""
    global _current_ai_prompt, _current_playwright_config
    _current_ai_prompt = ai_prompt
    _current_playwright_config = playwright_config

def create_test_settings_tab(webui_manager: WebuiManager):
    """Create the test settings configuration tab"""
    
    def load_settings():
        """Load default settings (session-only, no file persistence)"""
        return DEFAULT_AI_PROMPT_TEMPLATE, DEFAULT_PLAYWRIGHT_CONFIG
    
    def save_settings(ai_prompt, playwright_config):
        """Update session settings (no permanent file saving)"""
        try:
            # Update global variables for current session only
            update_global_settings(ai_prompt, playwright_config)
            return "✅ Settings updated for current session!"
        except Exception as e:
            return f"❌ Error updating settings: {e}"
    
    def reset_to_defaults():
        """Reset settings to defaults"""
        return DEFAULT_AI_PROMPT_TEMPLATE, DEFAULT_PLAYWRIGHT_CONFIG, "🔄 Settings reset to defaults"
    
    def validate_config(config_text):
        """Validate JavaScript configuration syntax"""
        try:
            # Basic validation - check for common syntax issues
            if not config_text.strip():
                return "❌ Configuration cannot be empty"
            
            if "module.exports" not in config_text:
                return "⚠️ Warning: Configuration should start with 'module.exports = '"
            
            # Check for balanced braces
            open_braces = config_text.count('{')
            close_braces = config_text.count('}')
            if open_braces != close_braces:
                return f"⚠️ Warning: Unbalanced braces ({{ {open_braces}, }} {close_braces})"
            
            return "✅ Configuration syntax looks valid"
        except Exception as e:
            return f"❌ Validation error: {e}"
    
    # Load initial settings
    initial_prompt, initial_config = load_settings()
    
    with gr.Column():
        gr.Markdown("## ⚙️ Test Generation Settings")
        gr.Markdown("Configure how AI generates test scripts and Playwright behavior for your web application testing.")
        
        with gr.Row():
            # Left Column - AI Prompt Settings
            with gr.Column(scale=1):
                gr.Markdown("### 🤖 AI Script Generation Prompt")
                gr.Markdown("Customize how the AI generates Playwright test scripts from your test cases.")
                
                ai_prompt = gr.Textbox(
                    label="AI Prompt Template",
                    value=initial_prompt,
                    lines=15,
                    max_lines=20,
                    placeholder="Enter your custom AI prompt template...",
                    info="Use placeholders: {test_case_name}, {test_case_url}, {test_case_steps}, {discovered_elements}"
                )
                
                with gr.Row():
                    validate_prompt_btn = gr.Button("🔍 Validate Prompt", size="sm")
                    reset_prompt_btn = gr.Button("🔄 Reset to Default", size="sm")
                
                prompt_status = gr.Textbox(
                    label="Prompt Status",
                    value="Ready to use",
                    interactive=False,
                    lines=1
                )
            
            # Right Column - Playwright Configuration
            with gr.Column(scale=1):
                gr.Markdown("### 🎭 Playwright Configuration")
                gr.Markdown("Customize Playwright test execution settings, timeouts, and browser options.")
                
                playwright_config = gr.Code(
                    label="Playwright Config (JavaScript)",
                    value=initial_config,
                    language="javascript",
                    lines=15,
                    interactive=True
                )
                
                with gr.Row():
                    validate_config_btn = gr.Button("🔍 Validate Config", size="sm")
                    reset_config_btn = gr.Button("🔄 Reset to Default", size="sm")
                
                config_status = gr.Textbox(
                    label="Config Status",
                    value="Ready to use",
                    interactive=False,
                    lines=1
                )
        
        # Save Settings Section
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 🔄 Session Settings")
                gr.Markdown("*Settings are applied for the current session only and reset when you restart the application.*")
                
                with gr.Row():
                    save_btn = gr.Button("🔄 Apply Settings for Session", variant="primary", size="lg")
                    reset_all_btn = gr.Button("↩️ Reset to Defaults", size="lg")
                
                save_status = gr.Textbox(
                    label="Session Status",
                    value="Ready to apply changes",
                    interactive=False,
                    lines=1
                )
        
        # Help Section
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📖 Help & Documentation")
                
                gr.Markdown("""
                **AI Prompt Placeholders:**
                - `{test_case_name}` - Name of the test case
                - `{test_case_url}` - Starting URL for the test
                - `{test_case_steps}` - List of test steps (numbered)
                - `{discovered_elements}` - Real selectors discovered by the agent
                
                **Playwright Configuration:**
                - timeout: Global test timeout in milliseconds (120000 = 2 minutes)
                - actionTimeout: How long to wait for actions (30000 = 30 seconds)
                - navigationTimeout: How long to wait for page loads (30000 = 30 seconds)
                - headless: true/false - whether to show browser during tests
                - viewport: Browser window size
                - screenshot/video/trace: Enable/disable recording features
                
                **Tips:**
                - Keep the AI prompt focused and specific
                - Test your changes with simple test cases first
                - Apply settings before running tests
                - Use the validate buttons to check syntax
                - Settings are session-only and reset on app restart
                """)
    
    # Store components for webui_manager
    tab_components = {
        "ai_prompt": ai_prompt,
        "playwright_config": playwright_config,
        "prompt_status": prompt_status,
        "config_status": config_status,
        "save_status": save_status,
        "save_btn": save_btn,
        "reset_all_btn": reset_all_btn,
        "validate_prompt_btn": validate_prompt_btn,
        "validate_config_btn": validate_config_btn,
        "reset_prompt_btn": reset_prompt_btn,
        "reset_config_btn": reset_config_btn
    }
    
    webui_manager.add_components("test_settings", tab_components)
    
    # Initialize global settings with current values
    update_global_settings(initial_prompt, initial_config)
    
    # Event handlers
    def validate_prompt(prompt_text):
        """Validate AI prompt template"""
        try:
            if not prompt_text.strip():
                return "❌ Prompt cannot be empty"
            
            required_placeholders = ['{test_case_name}', '{test_case_url}', '{test_case_steps}']
            missing = [p for p in required_placeholders if p not in prompt_text]
            
            if missing:
                return f"⚠️ Warning: Missing placeholders: {', '.join(missing)}"
            
            if len(prompt_text) < 100:
                return "⚠️ Warning: Prompt seems very short"
            
            return "✅ Prompt template looks good"
        except Exception as e:
            return f"❌ Validation error: {e}"
    
    def on_prompt_change(prompt_text):
        """Update global settings when prompt changes"""
        update_global_settings(prompt_text, get_current_playwright_config())
        return prompt_text
    
    def on_config_change(config_text):
        """Update global settings when config changes"""
        update_global_settings(get_current_ai_prompt(), config_text)
        return config_text
    
    # Connect events
    save_btn.click(
        fn=save_settings,
        inputs=[ai_prompt, playwright_config],
        outputs=[save_status]
    )
    
    def reset_to_defaults_with_update():
        """Reset settings to defaults and update global variables"""
        update_global_settings(DEFAULT_AI_PROMPT_TEMPLATE, DEFAULT_PLAYWRIGHT_CONFIG)
        return DEFAULT_AI_PROMPT_TEMPLATE, DEFAULT_PLAYWRIGHT_CONFIG, "🔄 Settings reset to defaults for session"
    
    reset_all_btn.click(
        fn=reset_to_defaults_with_update,
        outputs=[ai_prompt, playwright_config, save_status]
    )
    
    validate_prompt_btn.click(
        fn=validate_prompt,
        inputs=[ai_prompt],
        outputs=[prompt_status]
    )
    
    validate_config_btn.click(
        fn=validate_config,
        inputs=[playwright_config],
        outputs=[config_status]
    )
    
    def reset_prompt_with_update():
        """Reset prompt to default and update global variables"""
        update_global_settings(DEFAULT_AI_PROMPT_TEMPLATE, get_current_playwright_config())
        return DEFAULT_AI_PROMPT_TEMPLATE, "🔄 Prompt reset to default"
    
    def reset_config_with_update():
        """Reset config to default and update global variables"""
        update_global_settings(get_current_ai_prompt(), DEFAULT_PLAYWRIGHT_CONFIG)
        return DEFAULT_PLAYWRIGHT_CONFIG, "🔄 Config reset to default"
    
    reset_prompt_btn.click(
        fn=reset_prompt_with_update,
        outputs=[ai_prompt, prompt_status]
    )
    
    reset_config_btn.click(
        fn=reset_config_with_update,
        outputs=[playwright_config, config_status]
    )
    
    # Connect change events to update global settings
    ai_prompt.change(
        fn=on_prompt_change,
        inputs=[ai_prompt],
        outputs=[]
    )
    
    playwright_config.change(
        fn=on_config_change,
        inputs=[playwright_config],
        outputs=[]
    )