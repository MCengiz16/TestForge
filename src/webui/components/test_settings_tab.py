import gradio as gr
import json
import os
from src.webui.webui_manager import WebuiManager

# Global variables to store current settings
_current_ai_prompt = None
_current_playwright_config = None

# Default AI prompt template for test script generation
DEFAULT_AI_PROMPT_TEMPLATE = """You are an expert Playwright test automation engineer. 

Please analyze this test case and generate a complete, professional Playwright test script.

TEST CASE:
Name: {test_case_name}
URL: {test_case_url}
Steps:
{test_case_steps}

{discovered_elements}

REQUIREMENTS:
1. Generate a complete Playwright test script in JavaScript
2. Use proper selectors (IDs, CSS selectors, or text-based locators)
3. Include proper error handling and waits (timeouts are configured globally)
4. Use expect() assertions for validations
5. No screenshots needed (videos and traces are captured automatically)
6. Make the script robust and maintainable
7. Use standard Playwright methods: waitForSelector, click, fill, etc. (timeouts handled by config)

Generate ONLY the JavaScript code, no explanations:"""

# Default Playwright configuration template
DEFAULT_PLAYWRIGHT_CONFIG = """module.exports = {
    testDir: '.',
    timeout: 120000,
    expect: {
        timeout: 30000
    },
    use: {
        headless: false,
        viewport: null,
        actionTimeout: 30000,
        navigationTimeout: 30000,
        waitForSelectorTimeout: 30000,
        waitForTimeout: 30000,
        launchOptions: {
            args: [
                '--start-fullscreen',
                '--kiosk',
                '--window-size=1920,1080',
                '--window-position=0,0',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        },
        screenshot: 'off',
        video: 'on',
        trace: 'on',
    },
    reporter: [
        ['html', { outputFolder: 'playwright-report', open: 'never' }],
        ['json', { outputFile: 'test-results.json' }],
        ['junit', { outputFile: 'junit-results.xml' }]
    ],
    outputDir: 'test-results',
    projects: [
        {
            name: 'chromium',
            use: {
                viewport: null,
                actionTimeout: 30000,
                navigationTimeout: 30000,
                waitForSelectorTimeout: 30000,
                waitForTimeout: 30000,
                launchOptions: {
                    args: [
                        '--start-fullscreen',
                        '--kiosk',
                        '--window-size=1920,1080',
                        '--window-position=0,0',
                        '--no-sandbox',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                },
                screenshot: 'off',
                video: 'on',
                trace: 'on',
            },
        },
    ],
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
    
    # Load saved settings or use defaults
    settings_file = "./tmp/test_settings.json"
    
    def load_settings():
        """Load settings from file or return defaults"""
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    return (
                        settings.get('ai_prompt', DEFAULT_AI_PROMPT_TEMPLATE),
                        settings.get('playwright_config', DEFAULT_PLAYWRIGHT_CONFIG)
                    )
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        return DEFAULT_AI_PROMPT_TEMPLATE, DEFAULT_PLAYWRIGHT_CONFIG
    
    def save_settings(ai_prompt, playwright_config):
        """Save settings to file and update global variables"""
        try:
            # Update global variables first
            update_global_settings(ai_prompt, playwright_config)
            
            # Save to file
            os.makedirs("./tmp", exist_ok=True)
            settings = {
                'ai_prompt': ai_prompt,
                'playwright_config': playwright_config
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            return "✅ Settings saved successfully!"
        except Exception as e:
            return f"❌ Error saving settings: {e}"
    
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
                gr.Markdown("### 💾 Save Settings")
                
                with gr.Row():
                    save_btn = gr.Button("💾 Save All Settings", variant="primary", size="lg")
                    reset_all_btn = gr.Button("🔄 Reset All to Defaults", size="lg")
                
                save_status = gr.Textbox(
                    label="Save Status",
                    value="Ready to save",
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
                - Modify timeouts, browser settings, reporting options
                - All timeouts are in milliseconds (30000 = 30 seconds)
                - Browser args control how Chrome/Chromium launches
                - Reporters determine output format (HTML, JSON, JUnit)
                
                **Tips:**
                - Keep the AI prompt focused and specific
                - Test your changes with simple test cases first
                - Save settings before running tests
                - Use the validate buttons to check syntax
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
        return DEFAULT_AI_PROMPT_TEMPLATE, DEFAULT_PLAYWRIGHT_CONFIG, "🔄 Settings reset to defaults"
    
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