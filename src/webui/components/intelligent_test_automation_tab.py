import asyncio
import json
import logging
import os
import uuid
import re
import subprocess
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from datetime import datetime

import gradio as gr
from browser_use.agent.views import AgentHistoryList, AgentOutput
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.browser.views import BrowserState
from gradio.components import Component
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.browser_use.browser_use_agent import BrowserUseAgent
from src.browser.custom_browser import CustomBrowser
from src.controller.custom_controller import CustomController
from src.utils import llm_provider
from src.webui.webui_manager import WebuiManager

logger = logging.getLogger(__name__)


class TestCase:
    """Enhanced test case with agent-discovered locators"""
    def __init__(self, name: str, description: str, url: str, steps: List[str]):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.url = url
        self.steps = steps  # Natural language steps
        self.discovered_elements = {}  # Real locators found by agent
        self.playwright_script = ""
        self.test_results = {}
        self.status = "created"  # created -> exploring -> script_ready -> test_running -> completed
        self.exploration_log = []
        self.test_execution_log = []
        self.playwright_report_path = ""


class ElementDiscovery:
    """Tracks elements discovered by the agent during exploration"""
    
    @staticmethod
    def extract_locators_from_agent_output(agent_output: AgentOutput) -> Dict[str, str]:
        """Extract actual selectors from agent's actions"""
        discovered = {}
        
        if not agent_output or not agent_output.action:
            return discovered
            
        for action in agent_output.action:
            action_dict = action.model_dump() if hasattr(action, 'model_dump') else {}
            
            # Extract different types of locators
            if action_dict.get('action_type') == 'click':
                selector = action_dict.get('coordinate') or action_dict.get('element')
                if selector:
                    element_desc = action_dict.get('reasoning', 'clickable_element')
                    discovered[element_desc] = ElementDiscovery._normalize_selector(selector)
                    
            elif action_dict.get('action_type') == 'type':
                selector = action_dict.get('element') or action_dict.get('target')
                if selector:
                    element_desc = action_dict.get('reasoning', 'input_field')
                    discovered[element_desc] = ElementDiscovery._normalize_selector(selector)
                    
            elif action_dict.get('action_type') == 'select':
                selector = action_dict.get('element')
                if selector:
                    element_desc = action_dict.get('reasoning', 'dropdown')
                    discovered[element_desc] = ElementDiscovery._normalize_selector(selector)
        
        return discovered
    
    @staticmethod
    def _normalize_selector(selector_info) -> str:
        """Convert agent's selector info to valid CSS/XPath selector"""
        if isinstance(selector_info, dict):
            # If coordinate-based, try to extract text or role
            if 'text' in selector_info:
                return f"text={selector_info['text']}"
            elif 'role' in selector_info:
                return f"role={selector_info['role']}"
            elif 'id' in selector_info:
                return f"#{selector_info['id']}"
            elif 'class' in selector_info:
                return f".{selector_info['class']}"
            else:
                return str(selector_info)
        elif isinstance(selector_info, str):
            return selector_info
        else:
            return str(selector_info)


class IntelligentScriptGenerator:
    """Generate Playwright scripts using agent-discovered locators"""
    
    @staticmethod
    def generate_script_with_real_locators(test_case: TestCase) -> str:
        """Generate script using actual locators discovered by agent"""
        
        script_header = f'''// Test: {test_case.name}
// Description: {test_case.description}
// Generated with real locators discovered by AI agent
// Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

const {{ test, expect }} = require('@playwright/test');

test.describe('{test_case.name}', () => {{
    test('should complete {test_case.name.lower()}', async ({{ page }}) => {{
        console.log('Starting test: {test_case.name}');
        
'''
        
        script_body = ""
        
        # Generate steps based on discovered elements
        for i, step in enumerate(test_case.steps, 1):
            step_lower = step.lower()
            script_body += f"        // Step {i}: {step}\n"
            
            if "navigate" in step_lower or "go to" in step_lower:
                url = IntelligentScriptGenerator._extract_url_from_step(step) or test_case.url
                script_body += f"        await page.goto('{url}');\n"
                script_body += "        await page.waitForLoadState('networkidle');\n\n"
                
            elif "type" in step_lower or "enter" in step_lower or "fill" in step_lower:
                # Find relevant input field from discovered elements
                input_selector = IntelligentScriptGenerator._find_input_selector(step, test_case.discovered_elements)
                text_to_type = IntelligentScriptGenerator._extract_text_from_step(step)
                
                script_body += f"        await page.waitForSelector('{input_selector}', {{ visible: true }});\n"
                script_body += f"        await page.fill('{input_selector}', '{text_to_type}');\n\n"
                
            elif "click" in step_lower or "login" in step_lower or "submit" in step_lower:
                # Find relevant clickable element
                click_selector = IntelligentScriptGenerator._find_click_selector(step, test_case.discovered_elements)
                
                script_body += f"        await page.waitForSelector('{click_selector}', {{ visible: true }});\n"
                script_body += f"        await page.click('{click_selector}');\n"
                script_body += f"        await page.waitForLoadState('networkidle');\n\n"
                
            elif "verify" in step_lower or "check" in step_lower or "assert" in step_lower or "validate" in step_lower or "present" in step_lower:
                # Add verification
                verify_text = IntelligentScriptGenerator._extract_verification_text(step)
                
                if verify_text:
                    # Smart verification - try multiple selectors
                    script_body += f"        // Verification: {verify_text} should be present\n"
                    script_body += f"        const element = page.locator(':has-text(\"{verify_text}\")').first();\n"
                    script_body += f"        await expect(element).toBeVisible();\n"
                    script_body += f"        await expect(element).toContainText('{verify_text}');\n\n"
                else:
                    # Generic visibility check
                    verify_selector = IntelligentScriptGenerator._find_verification_selector(step, test_case.discovered_elements)
                    script_body += f"        // Verification step\n"
                    script_body += f"        await expect(page.locator('{verify_selector}').first()).toBeVisible();\n\n"
                
            elif "wait" in step_lower:
                wait_time = IntelligentScriptGenerator._extract_wait_time(step)
                script_body += f"        // Wait step\n"
                script_body += f"        await page.waitForTimeout({wait_time});\n\n"
                
            else:
                # Try to handle other common actions
                if any(word in step_lower for word in ['button', 'btn']):
                    button_selector = IntelligentScriptGenerator._find_button_selector(step, test_case.discovered_elements)
                    script_body += f"        await page.waitForSelector('{button_selector}', {{ visible: true }});\n"
                    script_body += f"        await page.click('{button_selector}');\n\n"
                else:
                    # Fallback - try to extract action intelligently
                    script_body += f"        // {step}\n"
                    script_body += f"        // TODO: Implement specific action for: {step}\n\n"
        
        script_footer = f'''        console.log('Test completed successfully: {test_case.name}');
    }});
}});
'''
        
        return script_header + script_body + script_footer
    
    @staticmethod
    def _find_input_selector(step: str, discovered_elements: Dict[str, str]) -> str:
        """Find the best input selector from discovered elements"""
        step_lower = step.lower()
        
        # Look for specific field types first
        if 'username' in step_lower or 'user name' in step_lower:
            # Look for username field in discovered elements
            for desc, selector in discovered_elements.items():
                if any(word in desc.lower() for word in ['username', 'user', 'name', 'login']):
                    return selector
            return '#user-name, #username, input[name*="user"], input[placeholder*="user"]'
            
        elif 'password' in step_lower:
            # Look for password field in discovered elements
            for desc, selector in discovered_elements.items():
                if 'password' in desc.lower():
                    return selector
            return '#password, input[type="password"], input[name*="password"]'
            
        elif 'email' in step_lower:
            # Look for email field in discovered elements
            for desc, selector in discovered_elements.items():
                if 'email' in desc.lower():
                    return selector
            return 'input[type="email"], input[name*="email"]'
        
        # Generic input field lookup
        for desc, selector in discovered_elements.items():
            desc_lower = desc.lower()
            if any(keyword in desc_lower for keyword in ['input', 'field', 'textbox']):
                return selector
        
        # Default fallback
        return 'input[type="text"]:first, input:not([type]):first'
    
    @staticmethod
    def _find_click_selector(step: str, discovered_elements: Dict[str, str]) -> str:
        """Find the best clickable selector from discovered elements"""
        step_lower = step.lower()
        
        for desc, selector in discovered_elements.items():
            desc_lower = desc.lower()
            if any(keyword in desc_lower for keyword in ['button', 'link', 'submit', 'login', 'click']):
                if any(keyword in step_lower for keyword in ['button', 'submit', 'login', 'sign in']):
                    return selector
        
        # Default fallback
        return 'button, [type="submit"], a'
    
    @staticmethod
    def _find_verification_selector(step: str, discovered_elements: Dict[str, str]) -> str:
        """Find selector for verification"""
        step_lower = step.lower()
        
        for desc, selector in discovered_elements.items():
            desc_lower = desc.lower()
            if any(keyword in desc_lower for keyword in ['message', 'text', 'title', 'content', 'welcome']):
                return selector
        
        return 'body, .content, .message, h1, h2'
    
    @staticmethod
    def _extract_text_from_step(step: str) -> str:
        """Extract text to type from step description"""
        # Look for quoted text
        import re
        quoted_text = re.search(r'["\']([^"\']+)["\']', step)
        if quoted_text:
            return quoted_text.group(1)
        
        # Look for common patterns
        if "email" in step.lower():
            return "test@example.com"
        elif "password" in step.lower():
            return "testpassword123"
        elif "username" in step.lower():
            return "testuser"
        
        return "test input"
    
    @staticmethod
    def _extract_verification_text(step: str) -> str:
        """Extract text to verify from step description"""
        import re
        quoted_text = re.search(r'["\']([^"\']+)["\']', step)
        if quoted_text:
            return quoted_text.group(1)
        return ""
    
    @staticmethod
    def _extract_wait_time(step: str) -> int:
        """Extract wait time from step"""
        import re
        time_match = re.search(r'(\d+)', step)
        if time_match:
            return int(time_match.group(1)) * 1000  # Convert to milliseconds
        return 2000  # Default 2 seconds
    
    @staticmethod
    def _extract_url_from_step(step: str) -> str:
        """Extract URL from step text"""
        import re
        url_pattern = r'https?://[^\s]+'
        match = re.search(url_pattern, step)
        return match.group(0) if match else None
    
    @staticmethod
    def _find_button_selector(step: str, discovered_elements: Dict[str, str]) -> str:
        """Find button selector from discovered elements"""
        step_lower = step.lower()
        
        # Look for button-related discovered elements
        for desc, selector in discovered_elements.items():
            desc_lower = desc.lower()
            if any(keyword in desc_lower for keyword in ['button', 'btn', 'submit', 'login', 'click']):
                return selector
        
        # Fallback selectors
        if 'login' in step_lower or 'submit' in step_lower:
            return 'button[type="submit"], input[type="submit"], .login-btn, #login-button'
        
        return 'button, input[type="button"], .btn'


async def _generate_script_with_ai(llm: BaseChatModel, test_case: TestCase) -> str:
    """Generate Playwright script using AI analysis of the test case"""
    
    # Prepare discovered elements summary
    elements_info = ""
    if test_case.discovered_elements:
        elements_info = "\n\nDiscovered Elements:\n"
        for desc, selector in test_case.discovered_elements.items():
            elements_info += f"- {desc}: {selector}\n"
    
    # Create AI prompt for script generation
    prompt = f"""You are an expert Playwright test automation engineer. 

Please analyze this test case and generate a complete, professional Playwright test script.

TEST CASE:
Name: {test_case.name}
URL: {test_case.url}
Steps:
{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(test_case.steps)])}

{elements_info}

REQUIREMENTS:
1. Generate a complete Playwright test script in JavaScript
2. Use proper selectors (IDs, CSS selectors, or text-based locators)
3. Include proper error handling and waits (use 30 second timeouts for all actions)
4. Use expect() assertions for validations
5. No screenshots needed (videos and traces are captured automatically)
6. Make the script robust and maintainable
7. Use waitForSelector with 30 second timeout: await page.waitForSelector('selector', {{ timeout: 30000 }})
8. For SauceLabs specifically, use these selectors if applicable:
   - Username field: #user-name
   - Password field: #password  
   - Login button: #login-button
   - Product elements: .inventory_item_name

Generate ONLY the JavaScript code, no explanations:"""

    try:
        response = await llm.ainvoke(prompt)
        script_content = response.content if hasattr(response, 'content') else str(response)
        
        # Clean up the response to extract just the code
        if '```javascript' in script_content:
            script_content = script_content.split('```javascript')[1].split('```')[0].strip()
        elif '```' in script_content:
            script_content = script_content.split('```')[1].split('```')[0].strip()
        
        return script_content
        
    except Exception as e:
        logger.error(f"AI script generation failed: {e}")
        # Fallback to basic template
        return f'''const {{ test, expect }} = require('@playwright/test');

test.describe('{test_case.name}', () => {{
    test('should complete {test_case.name.lower()}', async ({{ page }}) => {{
        await page.goto('{test_case.url}', {{ timeout: 30000 }});
        await page.waitForLoadState('networkidle', {{ timeout: 30000 }});
        
        // TODO: Implement test steps with 30 second timeouts
        {chr(10).join([f"        // {step}" for step in test_case.steps])}
        
        console.log('Test completed: {test_case.name}');
    }});
}});'''


async def _initialize_llm_for_intelligent_test(webui_manager: WebuiManager, components: Dict) -> Optional[BaseChatModel]:
    """Initialize LLM for intelligent test execution"""
    import os
    
    def get_setting(key, default=None):
        comp = webui_manager.id_to_component.get(f"agent_settings.{key}")
        return components.get(comp, default) if comp else default

    provider = get_setting("llm_provider")
    model = get_setting("llm_model_name")
    
    # If no UI settings available, try environment variables as fallback
    if not provider or not model:
        logger.info("No LLM settings found in UI components, using environment variables fallback")
        # Check for OpenAI API key
        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
            model = "gpt-4o-mini"  # Default model
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
            model = "claude-3-sonnet-20240229"
        else:
            logger.error("No LLM provider configured in UI or environment variables")
            return None
    
    try:
        # Use environment variables for credentials if not in UI
        api_key = get_setting("llm_api_key") or os.environ.get(f"{provider.upper()}_API_KEY")
        base_url = get_setting("llm_base_url") or os.environ.get(f"{provider.upper()}_ENDPOINT")
        
        logger.info(f"Initializing LLM with provider={provider}, model={model}, api_key_exists={bool(api_key)}, base_url={base_url}")
        
        llm = llm_provider.get_llm_model(
            provider=provider,
            model_name=model,
            temperature=get_setting("llm_temperature", 0.6),
            base_url=base_url,
            api_key=api_key,
            num_ctx=get_setting("ollama_num_ctx", 16000) if provider == "ollama" else None,
        )
        
        logger.info(f"LLM initialization successful: {type(llm)}")
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


async def _explore_page_and_discover_elements(
    webui_manager: WebuiManager,
    test_case: TestCase,
    components: Dict
) -> AsyncGenerator[Dict, None]:
    """Phase 1: Agent explores page and discovers real locators"""
    
    status_comp = webui_manager.get_component_by_id("test_automation.status")
    chatbot_comp = webui_manager.get_component_by_id("test_automation.agent_chatbot")
    
    test_case.status = "exploring"
    
    # Initialize chat history for this test (using messages format with type="messages")
    webui_manager.test_chat_history = [
        {"role": "assistant", "content": f"🔍 **Starting page exploration for:** {test_case.name}\n\n📍 Target URL: {test_case.url}\n\n🎯 **Test Steps to Discover:**\n" + "\n".join([f"• {step}" for step in test_case.steps])}
    ]
    
    yield {
        status_comp: gr.update(value="🔍 Exploring Page"),
        chatbot_comp: gr.update(value=webui_manager.test_chat_history)
    }
    
    try:
        # Initialize LLM and browser
        llm = await _initialize_llm_for_intelligent_test(webui_manager, components)
        if not llm:
            raise Exception("Failed to initialize LLM for exploration")
        
        # Ensure DISPLAY is set for VNC visibility
        os.environ['DISPLAY'] = ':99'
        logger.info(f"Set DISPLAY for VNC: {os.environ.get('DISPLAY')}")
        
        test_dir = os.path.abspath(os.path.join("./tmp/test_results", test_case.id))
        os.makedirs(test_dir, exist_ok=True)
        
        browser_config = BrowserConfig(
            headless=False,  # Show browser in action
            disable_security=True,
            new_context_config=BrowserContextConfig(
                window_width=1920,
                window_height=1080,
                save_recording_path=test_dir,
            )
        )
        
        browser = CustomBrowser(config=browser_config)
        context = await browser.new_context(config=BrowserContextConfig(
            save_recording_path=test_dir,
            window_width=1920,
            window_height=1080,
        ))
        
        # Step 1: Navigate and analyze page structure
        webui_manager.test_chat_history.append({
            "role": "assistant", 
            "content": "📍 **Initializing browser and starting exploration...**\n\n🖥️ **Live Browser View**: Open http://localhost:6080/vnc.html to watch the agent work!\n\n🌐 Navigating to target URL..."
        })
        yield {
            chatbot_comp: gr.update(value=webui_manager.test_chat_history)
        }
        
        exploration_task = f"""
        Navigate to {test_case.url} and carefully analyze the page structure.
        
        I need you to explore this page and identify all the interactive elements that would be needed for these test steps:
        {chr(10).join([f"- {step}" for step in test_case.steps])}
        
        Please:
        1. Navigate to the page
        2. Take a screenshot to see the page layout
        3. Identify all forms, input fields, buttons, and links
        4. Try to interact with key elements to understand their selectors
        5. Pay special attention to login forms, input fields, submit buttons
        6. Take note of any error messages or success indicators
        
        Focus on discovering the actual selectors and element properties that will be needed for the test automation.
        """
        
        controller = CustomController()
        
        # Track discovered elements during exploration
        discovered_elements = {}
        
        # Store the generator for updating UI during agent execution
        current_generator = None
        
        def track_elements(state: BrowserState, output: AgentOutput, step_num: int):
            """Callback to track discovered elements"""
            new_elements = ElementDiscovery.extract_locators_from_agent_output(output)
            discovered_elements.update(new_elements)
            test_case.discovered_elements.update(new_elements)
            
            # Extract action info for better logging
            action_desc = "Analyzing page structure"
            if output and output.action:
                for action in output.action:
                    if hasattr(action, 'model_dump'):
                        action_dict = action.model_dump()
                        action_type = action_dict.get('action_type', 'action')
                        reasoning = action_dict.get('reasoning', '')
                        action_desc = f"{action_type}: {reasoning}"
                        break
            
            # Add step to chat history like original agent
            step_content = f"**🤖 Agent Step {step_num}:**\n\n🎯 {action_desc}"
            if new_elements:
                step_content += f"\n\n🔍 **Discovered Elements:**\n"
                for desc, selector in new_elements.items():
                    step_content += f"• {desc}: `{selector}`\n"
            
            webui_manager.test_chat_history.append({
                "role": "assistant",
                "content": step_content
            })
            
            # Try to yield update if we have a generator context
            try:
                if hasattr(webui_manager, 'current_exploration_update'):
                    webui_manager.current_exploration_update = {
                        chatbot_comp: gr.update(value=webui_manager.test_chat_history)
                    }
            except Exception as e:
                logger.debug(f"Could not yield real-time update: {e}")
            
            logger.info(f"Agent step completed: Step {step_num} - {action_desc}")
        
        agent = BrowserUseAgent(
            task=exploration_task,
            llm=llm,
            browser=browser,
            browser_context=context,
            controller=controller,
            use_vision=True,
            max_actions_per_step=5,
            source="test_exploration",
            register_new_step_callback=track_elements,
        )
        
        # Run exploration
        webui_manager.test_chat_history.append({
            "role": "assistant",
            "content": "🤖 **Agent starting page exploration...**\n\n👀 **WATCH LIVE:** http://localhost:6080\n\n🔗 Click the link above to see the browser in action!"
        })
        yield {
            chatbot_comp: gr.update(value=webui_manager.test_chat_history)
        }
        
        try:
            webui_manager.test_chat_history.append({
                "role": "assistant",
                "content": "🚀 **Starting agent execution...**\n\nAgent will now navigate and discover elements on the page."
            })
            yield {
                chatbot_comp: gr.update(value=webui_manager.test_chat_history)
            }
            
            # Set environment variable for display
            os.environ['DISPLAY'] = ':99'
            
            await asyncio.wait_for(agent.run(max_steps=10), timeout=120.0)
            
            webui_manager.test_chat_history.append({
                "role": "assistant",
                "content": "🎯 **Agent execution completed successfully!**\n\nPage exploration finished. Elements discovered and ready for script generation."
            })
            
        except asyncio.TimeoutError:
            webui_manager.test_chat_history.append({
                "role": "assistant",
                "content": "⏰ **Agent execution timed out** after 2 minutes\n\n💡 This might be normal for complex pages. Proceeding with discovered elements..."
            })
        except Exception as agent_error:
            webui_manager.test_chat_history.append({
                "role": "assistant",
                "content": f"⚠️ **Agent execution error:** {str(agent_error)}\n\n🔄 Continuing with discovered elements..."
            })
        
        # Clean up browser
        await context.close()
        await browser.close()
        
        test_case.status = "script_ready"
        
        # Final summary
        elements_summary = f"🎉 **Exploration Complete!**\n\n🔍 **Discovered {len(test_case.discovered_elements)} elements:**\n"
        for desc, selector in test_case.discovered_elements.items():
            elements_summary += f"• {desc}: `{selector}`\n"
        elements_summary += f"\n📝 **Generating Playwright script with real locators...**"
        
        webui_manager.test_chat_history.append({
            "role": "assistant",
            "content": elements_summary
        })
        
        # Generate script with AI
        test_case.playwright_script = await _generate_script_with_ai(llm, test_case)
        
        yield {
            status_comp: gr.update(value="✅ Script Ready"),
            chatbot_comp: gr.update(value=webui_manager.test_chat_history)
        }
        
    except Exception as e:
        test_case.status = "failed"
        webui_manager.test_chat_history.append({
            "role": "assistant",
            "content": f"❌ **Exploration failed:** {str(e)}"
        })
        
        yield {
            status_comp: gr.update(value="❌ Exploration Failed"),
            chatbot_comp: gr.update(value=webui_manager.test_chat_history)
        }


async def _run_playwright_test(
    webui_manager: WebuiManager,
    test_case: TestCase
) -> AsyncGenerator[Dict, None]:
    """Phase 2: Run the generated Playwright test and get original reports"""
    
    status_comp = webui_manager.get_component_by_id("test_automation.status")
    execution_log_comp = webui_manager.get_component_by_id("test_automation.execution_log")
    # report_comp = webui_manager.get_component_by_id("test_automation.test_report")
    
    test_case.status = "test_running"
    test_case.test_execution_log = ["🎭 Running Playwright test with discovered locators..."]
    
    yield {
        status_comp: gr.update(value="🎭 Running Playwright Test"),
        execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log))
    }
    
    try:
        # Create test directory and files
        test_dir = os.path.abspath(os.path.join("./tmp/test_results", test_case.id))
        os.makedirs(test_dir, exist_ok=True)
        
        # Write the test script
        test_file = os.path.join(test_dir, f"{test_case.name.replace(' ', '_')}.spec.js")
        with open(test_file, 'w') as f:
            f.write(test_case.playwright_script)
        
        test_case.test_execution_log.append(f"📝 Created test file: {test_file}")
        
        # Create Playwright config
        config_file = os.path.join(test_dir, "playwright.config.js")
        playwright_config = f'''
module.exports = {{
    testDir: '.',
    timeout: 120000,
    expect: {{
        timeout: 30000
    }},
    use: {{
        headless: false,
        viewport: null,
        actionTimeout: 30000,
        navigationTimeout: 30000,
        launchOptions: {{
            args: [
                '--start-fullscreen',
                '--kiosk',
                '--window-size=1920,1080',
                '--window-position=0,0',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        }},
        screenshot: 'off',
        video: 'on',
        trace: 'on',
    }},
    reporter: [
        ['html', {{ outputFolder: 'playwright-report', open: 'never' }}],
        ['json', {{ outputFile: 'test-results.json' }}],
        ['junit', {{ outputFile: 'junit-results.xml' }}]
    ],
    outputDir: 'test-results',
    projects: [
        {{
            name: 'chromium',
            use: {{
                viewport: null,
                actionTimeout: 30000,
                navigationTimeout: 30000,
                launchOptions: {{
                    args: [
                        '--start-fullscreen',
                        '--kiosk',
                        '--window-size=1920,1080',
                        '--window-position=0,0',
                        '--no-sandbox',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                }},
                screenshot: 'off',
                video: 'on',
                trace: 'on',
            }},
        }},
    ],
}};
'''
        with open(config_file, 'w') as f:
            f.write(playwright_config)
        
        test_case.test_execution_log.append("⚙️ Created Playwright configuration")
        
        yield {
            execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log))
        }
        
        # Install Playwright if needed
        test_case.test_execution_log.append("📦 Installing Playwright dependencies...")
        
        install_cmd = ["npm", "init", "-y"]
        subprocess.run(install_cmd, cwd=test_dir, capture_output=True)
        
        install_cmd = ["npm", "install", "@playwright/test"]
        result = subprocess.run(install_cmd, cwd=test_dir, capture_output=True, text=True)
        
        if result.returncode != 0:
            test_case.test_execution_log.append(f"⚠️ npm install warning: {result.stderr}")
        else:
            test_case.test_execution_log.append("✅ Playwright installed successfully")
        
        # Install Playwright browsers
        test_case.test_execution_log.append("🌐 Installing Playwright browsers...")
        
        browsers_cmd = ["npx", "playwright", "install", "chromium"]
        result = subprocess.run(browsers_cmd, cwd=test_dir, capture_output=True, text=True)
        
        if result.returncode != 0:
            test_case.test_execution_log.append(f"⚠️ Browser install error: {result.stderr}")
        else:
            test_case.test_execution_log.append("✅ Chromium browser installed successfully")
        
        yield {
            execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log))
        }
        
        # Run the test
        test_case.test_execution_log.append("🚀 Executing Playwright test...")
        test_case.test_execution_log.append("🖥️ Test will be visible in the Live Agent Demonstration window above!")
        
        # Set environment for headed mode display
        test_env = os.environ.copy()
        test_env['DISPLAY'] = ':99'
        
        test_cmd = ["npx", "playwright", "test", "--config", "playwright.config.js"]
        result = subprocess.run(test_cmd, cwd=test_dir, capture_output=True, text=True, env=test_env)
        
        test_case.test_execution_log.append(f"📊 Test execution completed with exit code: {result.returncode}")
        
        # Capture test output
        if result.stdout:
            test_case.test_execution_log.append("📝 Test Output:")
            for line in result.stdout.split('\n')[:10]:  # Show first 10 lines
                if line.strip():
                    test_case.test_execution_log.append(f"   {line}")
        
        if result.stderr:
            test_case.test_execution_log.append("⚠️ Test Errors:")
            for line in result.stderr.split('\n')[:5]:  # Show first 5 error lines
                if line.strip():
                    test_case.test_execution_log.append(f"   {line}")
        
        # Check for HTML report
        report_dir = os.path.join(test_dir, "playwright-report")
        report_index = os.path.join(report_dir, "index.html")
        
        if os.path.exists(report_index):
            test_case.playwright_report_path = report_index
            test_case.test_execution_log.append(f"📊 HTML report generated: {report_index}")
        
        # Check for JSON results
        json_results = os.path.join(test_dir, "test-results.json")
        if os.path.exists(json_results):
            with open(json_results, 'r') as f:
                results_data = json.load(f)
                test_case.test_results = results_data
                
                # Extract summary
                if 'stats' in results_data:
                    stats = results_data['stats']
                    test_case.test_execution_log.append(f"📈 Test Results: {stats.get('expected', 0)} passed, {stats.get('unexpected', 0)} failed")
        
        test_case.status = "completed"
        test_case.test_execution_log.append("🎉 Test execution completed!")
        
        # Add web-accessible report link
        if os.path.exists(report_index):
            # Create a web-accessible URL for the report
            report_url = f"http://localhost:7789/reports/{test_case.id}/playwright-report/index.html"
            test_case.test_execution_log.append(f"🔗 Report URL: {report_url}")
            test_case.test_execution_log.append("💡 Click 'View Report' button below to open the full Playwright report with screenshots and videos")
        
        yield {
            status_comp: gr.update(value="🎉 Test Completed"),
            execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log))
        }
        
    except Exception as e:
        test_case.status = "failed"
        test_case.test_execution_log.append(f"💥 Test execution failed: {str(e)}")
        
        yield {
            status_comp: gr.update(value="❌ Test Failed"),
            execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log))
        }


def create_test_automation_tab(webui_manager: WebuiManager):
    """Create intelligent test automation interface"""
    
    webui_manager.test_cases = []
    webui_manager.test_chat_history = [
        {"role": "assistant", "content": "Welcome to Intelligent Test Automation! Create a test to get started."}
    ]  # Initialize with proper message format
    
    with gr.Column():
        gr.Markdown("# 🧪 Intelligent Test Automation", elem_classes=["tab-header-text"])
        gr.Markdown("*Agent explores page → Discovers real locators → Generates accurate script → Runs Playwright tests*")
        
        with gr.Row():
            # Left Panel - Test Creation & Control
            with gr.Column(scale=1):
                gr.Markdown("## 📝 Create Test")
                
                test_name = gr.Textbox(
                    label="Test Name",
                    placeholder="e.g., User Login Flow",
                    lines=1
                )
                
                test_url = gr.Textbox(
                    label="Starting URL", 
                    placeholder="https://example.com/login",
                    lines=1
                )
                
                test_steps = gr.Textbox(
                    label="Test Steps (Natural Language)",
                    placeholder="""Describe what the test should do:
Navigate to the login page
Type email address into email field
Type password into password field  
Click the login button
Verify welcome message appears
Check that user is redirected to dashboard""",
                    lines=8
                )
                
                gr.Markdown("## 🎯 Test Control")
                
                with gr.Row():
                    create_test_btn = gr.Button("🚀 Create Test & Explore", variant="primary")
                    run_test_btn = gr.Button("🎭 Run Playwright Test", variant="secondary")
                
                status = gr.Textbox(
                    label="Status",
                    value="Ready to create tests",
                    interactive=False
                )
            
            # Right Panel - Results & Script
            with gr.Column(scale=1):
                gr.Markdown("## 📋 Generated Script")
                
                playwright_script = gr.Code(
                    label="Playwright Test Script (AI Generated - Editable)",
                    language="javascript",
                    lines=20,
                    show_label=True,
                    container=True,
                    interactive=True,
                    elem_id="editable_script"
                )
                
                gr.Markdown("## 📊 Test Results & Reports")
                
                report_status = gr.HTML(
                    value='<div style="padding: 15px; background: #f8f9fa; border-radius: 8px; margin: 10px 0;"><p style="margin: 0; color: #666;">📊 After test completion, the report link will appear here with screenshots and videos</p></div>',
                    label="Report Access Info"
                )
        
        # Live Browser View Section
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🖥️ Live Agent Demonstration")
                
                # Embedded VNC viewer
                vnc_viewer = gr.HTML(
                    value='''
                    <div style="text-align: center; padding: 10px; background: #f8f9fa; border-radius: 8px; margin: 10px 0;">
                        <div style="background: #000; border-radius: 8px; padding: 10px; margin: 10px 0;">
                            <iframe 
                                src="http://localhost:6080/vnc.html?host=localhost&port=6080&autoconnect=true&resize=scale&show_dot=true"
                                width="100%" 
                                height="600"
                                style="border: none; border-radius: 8px;"
                                allow="camera; microphone; display-capture">
                            </iframe>
                        </div>
                        <p style="margin: 10px 0; color: #666; font-size: 14px;">
                            🎯 <strong>Live Browser View</strong> - Watch the AI agent work in real-time<br>
                            If the view doesn't load, <a href="http://localhost:6080/vnc.html?host=localhost&port=6080" target="_blank">click here to open in new tab</a>
                        </p>
                    </div>
                    ''',
                    label="Embedded VNC Viewer"
                )
                
                vnc_link = gr.HTML(
                    value='<div style="text-align: center; padding: 15px; background: #e8f4f8; border-radius: 8px; margin: 10px 0;"><p style="margin: 0; color: #333;"><strong>🔍 When you click "🚀 Create Test & Explore":</strong><br>• Agent opens browser automatically in the window above<br>• You see every click, type, and scroll<br>• Real-time element discovery and interaction</p></div>',
                    label="Live Demo Instructions"
                )
        
        # Logs Section
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🔍 Live Agent Steps")
                agent_chatbot = gr.Chatbot(
                    label="Agent Exploration Steps",
                    height=300,
                    show_label=True,
                    container=True,
                    show_copy_button=True,
                    type="messages",
                    value=[{"role": "assistant", "content": "Agent steps will appear here during exploration..."}]
                )
            
            with gr.Column():
                gr.Markdown("## 🎭 Test Execution Log")
                execution_log = gr.Textbox(
                    label="Playwright Test Execution",
                    lines=8,
                    interactive=False
                )
    
    # Store components
    tab_components = {
        "test_name": test_name,
        "test_url": test_url,
        "test_steps": test_steps,
        "create_test_btn": create_test_btn,
        "run_test_btn": run_test_btn,
        "status": status,
        "playwright_script": playwright_script,
        "report_status": report_status,
        "vnc_viewer": vnc_viewer,
        "vnc_link": vnc_link,
        "agent_chatbot": agent_chatbot,
        "execution_log": execution_log,
    }
    
    webui_manager.add_components("test_automation", tab_components)
    
    # Get all components for event handlers
    all_components = list(webui_manager.get_components())
    
    # Event handlers
    async def create_test_and_explore(name, url, steps_text, *components_values):
        """Create new test case and automatically start exploration"""
        if not name or not url or not steps_text:
            yield gr.update(value="❌ Please fill all fields"), gr.update(), gr.update()
            return
        
        steps = [line.strip() for line in steps_text.strip().split('\n') if line.strip()]
        
        if not steps:
            yield gr.update(value="❌ No valid steps found"), gr.update(), gr.update()
            return
        
        # Create test case
        test_case = TestCase(name=name, description="", url=url, steps=steps)
        webui_manager.test_cases.append(test_case)
        
        yield gr.update(value=f"✅ Created: {name} - Starting exploration..."), gr.update(), gr.update()
        
        # Start exploration automatically
        components_dict = dict(zip(all_components, components_values))
        async for update in _explore_page_and_discover_elements(webui_manager, test_case, components_dict):
            # Extract updates for each component
            status_update = update.get(status, gr.update())
            chatbot_update = update.get(agent_chatbot, gr.update())
            script_update = gr.update(value=test_case.playwright_script) if test_case.playwright_script else gr.update()
            yield status_update, chatbot_update, script_update
    
    async def explore_page(test_id, components_dict):
        """Start page exploration phase"""
        if not test_id:
            yield {status: gr.update(value="❌ No test selected")}
            return
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case:
            yield {status: gr.update(value="❌ Test not found")}
            return
        
        async for update in _explore_page_and_discover_elements(webui_manager, test_case, components_dict):
            # Also update the script display
            if test_case.playwright_script:
                update[playwright_script] = gr.update(value=test_case.playwright_script)
            yield update
    
    async def run_latest_playwright_test(current_script):
        """Run the Playwright test using the current script content"""
        if not webui_manager.test_cases:
            yield gr.update(value="❌ No test created. Please create a test first."), gr.update(), gr.update()
            return
        
        test_case = webui_manager.test_cases[-1]  # Get the latest test case
        
        if not current_script or current_script.strip() == "":
            yield gr.update(value="❌ No script available. Please create and explore a test first."), gr.update(), gr.update()
            return
        
        # Use the current script content from the UI (allows editing)
        test_case.playwright_script = current_script
        
        async for update in _run_playwright_test(webui_manager, test_case):
            # Extract updates for each component
            status_update = update.get(status, gr.update())
            log_update = update.get(execution_log, gr.update())
            
            # Check if test completed and update report status
            if test_case.status == "completed" and test_case.playwright_report_path:
                report_url = f"http://localhost:7789/reports/{test_case.id}/playwright-report/index.html"
                report_update = gr.update(value=f'<div style="padding: 15px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; margin: 10px 0;"><p style="margin: 0; color: #155724;"><strong>✅ Report Available!</strong><br>📊 Playwright report with screenshots and videos is ready.<br>🔗 <a href="{report_url}" target="_blank">Click here to open report</a> or use the button below.</p></div>')
            else:
                report_update = gr.update()
                
            yield status_update, log_update, report_update
    
    def update_script_display(test_id):
        """Update script display when test is selected"""
        if not test_id:
            return gr.update(value="")
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case:
            return gr.update(value="")
        
        return gr.update(value=test_case.playwright_script or "// Script will be generated after page exploration")
    
    def download_script(test_id):
        """Download the generated script"""
        if not test_id:
            return None
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case or not test_case.playwright_script:
            return None
        
        script_path = os.path.join("./tmp", f"{test_case.name.replace(' ', '_')}.spec.js")
        os.makedirs("./tmp", exist_ok=True)
        
        with open(script_path, 'w') as f:
            f.write(test_case.playwright_script)
        
        return script_path
    
    def view_report(test_id):
        """Generate web-accessible URL for the Playwright HTML report"""
        if not test_id:
            return None
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case or not test_case.playwright_report_path:
            return None
        
        # Return web-accessible URL instead of file path
        report_url = f"http://localhost:7789/reports/{test_case.id}/playwright-report/index.html"
        return report_url
    
    # Connect events
    create_test_btn.click(
        fn=create_test_and_explore,
        inputs=[test_name, test_url, test_steps] + list(all_components),
        outputs=[status, agent_chatbot, playwright_script]
    )
    
    run_test_btn.click(
        fn=run_latest_playwright_test,
        inputs=[playwright_script],
        outputs=[status, execution_log, report_status]
    )
    
    
