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
        // Test configuration
        await page.setViewportSize({{ width: 1280, height: 720 }});
        
        // Start test execution
        console.log('Starting test: {test_case.name}');
        
'''
        
        script_body = ""
        
        # Generate steps based on discovered elements
        for i, step in enumerate(test_case.steps, 1):
            step_lower = step.lower()
            script_body += f"        // Step {i}: {step}\n"
            
            if "navigate" in step_lower or "go to" in step_lower:
                script_body += f"        await page.goto('{test_case.url}');\n"
                script_body += "        await page.waitForLoadState('networkidle');\n"
                script_body += "        await page.screenshot({ path: 'step-1-navigate.png' });\n\n"
                
            elif "type" in step_lower or "enter" in step_lower or "fill" in step_lower:
                # Find relevant input field from discovered elements
                input_selector = IntelligentScriptGenerator._find_input_selector(step, test_case.discovered_elements)
                text_to_type = IntelligentScriptGenerator._extract_text_from_step(step)
                
                script_body += f"        // Wait for input field and type text\n"
                script_body += f"        await page.waitForSelector('{input_selector}', {{ visible: true }});\n"
                script_body += f"        await page.fill('{input_selector}', '{text_to_type}');\n"
                script_body += f"        await page.screenshot({{ path: 'step-{i}-input.png' }});\n\n"
                
            elif "click" in step_lower:
                # Find relevant clickable element
                click_selector = IntelligentScriptGenerator._find_click_selector(step, test_case.discovered_elements)
                
                script_body += f"        // Wait for element and click\n"
                script_body += f"        await page.waitForSelector('{click_selector}', {{ visible: true }});\n"
                script_body += f"        await page.click('{click_selector}');\n"
                script_body += f"        await page.waitForLoadState('networkidle');\n"
                script_body += f"        await page.screenshot({{ path: 'step-{i}-click.png' }});\n\n"
                
            elif "verify" in step_lower or "check" in step_lower or "assert" in step_lower:
                # Add verification
                verify_text = IntelligentScriptGenerator._extract_verification_text(step)
                verify_selector = IntelligentScriptGenerator._find_verification_selector(step, test_case.discovered_elements)
                
                script_body += f"        // Verification step\n"
                script_body += f"        await expect(page.locator('{verify_selector}').first()).toBeVisible();\n"
                if verify_text:
                    script_body += f"        await expect(page.locator('{verify_selector}').first()).toContainText('{verify_text}');\n"
                script_body += f"        await page.screenshot({{ path: 'step-{i}-verify.png' }});\n\n"
                
            elif "wait" in step_lower:
                wait_time = IntelligentScriptGenerator._extract_wait_time(step)
                script_body += f"        // Wait step\n"
                script_body += f"        await page.waitForTimeout({wait_time});\n\n"
                
            else:
                # Generic action
                script_body += f"        // Manual step - implement as needed\n"
                script_body += f"        // TODO: {step}\n"
                script_body += f"        await page.screenshot({{ path: 'step-{i}-manual.png' }});\n\n"
        
        script_footer = f'''        // Final verification screenshot
        await page.screenshot({{ path: 'test-completed.png', fullPage: true }});
        
        console.log('Test completed successfully: {test_case.name}');
    }});
}});
'''
        
        return script_header + script_body + script_footer
    
    @staticmethod
    def _find_input_selector(step: str, discovered_elements: Dict[str, str]) -> str:
        """Find the best input selector from discovered elements"""
        step_lower = step.lower()
        
        # Look for keywords that might match discovered elements
        for desc, selector in discovered_elements.items():
            desc_lower = desc.lower()
            if any(keyword in desc_lower for keyword in ['input', 'field', 'textbox', 'email', 'password', 'username']):
                if any(keyword in step_lower for keyword in ['email', 'username', 'password', 'name']):
                    return selector
        
        # Default fallback
        return 'input[type="text"], input[type="email"], input[type="password"]'
    
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


async def _initialize_llm_for_intelligent_test(webui_manager: WebuiManager, components: Dict) -> Optional[BaseChatModel]:
    """Initialize LLM for intelligent test execution"""
    def get_setting(key, default=None):
        comp = webui_manager.id_to_component.get(f"agent_settings.{key}")
        return components.get(comp, default) if comp else default

    provider = get_setting("llm_provider")
    model = get_setting("llm_model_name")
    
    if not provider or not model:
        return None
    
    try:
        return llm_provider.get_llm_model(
            provider=provider,
            model_name=model,
            temperature=get_setting("llm_temperature", 0.6),
            base_url=get_setting("llm_base_url"),
            api_key=get_setting("llm_api_key"),
            num_ctx=get_setting("ollama_num_ctx", 16000) if provider == "ollama" else None,
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return None


async def _explore_page_and_discover_elements(
    webui_manager: WebuiManager,
    test_case: TestCase,
    components: Dict
) -> AsyncGenerator[Dict, None]:
    """Phase 1: Agent explores page and discovers real locators"""
    
    status_comp = webui_manager.get_component_by_id("test_automation.status")
    log_comp = webui_manager.get_component_by_id("test_automation.exploration_log")
    
    test_case.status = "exploring"
    test_case.exploration_log = ["🔍 Starting page exploration to discover elements..."]
    
    yield {
        status_comp: gr.update(value="🔍 Exploring Page"),
        log_comp: gr.update(value="\n".join(test_case.exploration_log))
    }
    
    try:
        # Initialize LLM and browser
        llm = await _initialize_llm_for_intelligent_test(webui_manager, components)
        if not llm:
            raise Exception("Failed to initialize LLM for exploration")
        
        test_dir = os.path.join("./tmp/test_results", test_case.id)
        os.makedirs(test_dir, exist_ok=True)
        
        browser_config = BrowserConfig(
            headless=False,  # Show browser in action
            disable_security=True,
            new_context_config=BrowserContextConfig(
                window_width=1280,
                window_height=720,
                save_recording_path=test_dir,
            )
        )
        
        browser = CustomBrowser(config=browser_config)
        context = await browser.new_context(config=BrowserContextConfig(
            save_recording_path=test_dir,
            window_width=1280,
            window_height=720,
        ))
        
        # Step 1: Navigate and analyze page structure
        test_case.exploration_log.append("📍 Navigating to target URL...")
        yield {
            log_comp: gr.update(value="\n".join(test_case.exploration_log))
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
        
        def track_elements(state: BrowserState, output: AgentOutput, step_num: int):
            """Callback to track discovered elements"""
            new_elements = ElementDiscovery.extract_locators_from_agent_output(output)
            discovered_elements.update(new_elements)
            test_case.discovered_elements.update(new_elements)
            
            # Extract action info for better logging
            action_desc = "Unknown action"
            if output and output.action:
                for action in output.action:
                    if hasattr(action, 'model_dump'):
                        action_dict = action.model_dump()
                        action_type = action_dict.get('action_type', 'action')
                        reasoning = action_dict.get('reasoning', '')
                        action_desc = f"{action_type}: {reasoning}"
                        break
            
            step_desc = f"Step {step_num}: {action_desc}"
            if new_elements:
                step_desc += f" (Found {len(new_elements)} elements: {', '.join(new_elements.keys())})"
            
            test_case.exploration_log.append(f"✅ {step_desc}")
            logger.info(f"Agent step completed: {step_desc}")
        
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
        test_case.exploration_log.append("🤖 Agent is exploring the page...")
        test_case.exploration_log.append("🔗 Open VNC viewer to watch the agent work: http://localhost:6080")
        yield {
            log_comp: gr.update(value="\n".join(test_case.exploration_log))
        }
        
        try:
            test_case.exploration_log.append("🚀 Starting agent execution...")
            yield {
                log_comp: gr.update(value="\n".join(test_case.exploration_log))
            }
            
            # Set environment variable for display
            os.environ['DISPLAY'] = ':99'
            
            await asyncio.wait_for(agent.run(max_steps=10), timeout=120.0)
            
            test_case.exploration_log.append("🎯 Agent execution completed successfully")
            
        except asyncio.TimeoutError:
            test_case.exploration_log.append("⏰ Agent execution timed out after 2 minutes")
            test_case.exploration_log.append("💡 This might be normal for complex pages")
        except Exception as agent_error:
            test_case.exploration_log.append(f"⚠️ Agent execution error: {str(agent_error)}")
            test_case.exploration_log.append("🔄 Continuing with discovered elements...")
        
        # Clean up browser
        await context.close()
        await browser.close()
        
        test_case.status = "script_ready"
        test_case.exploration_log.append(f"🎉 Exploration complete! Discovered {len(test_case.discovered_elements)} elements")
        test_case.exploration_log.append(f"📋 Elements found: {', '.join(test_case.discovered_elements.keys())}")
        
        # Generate script with discovered locators
        test_case.playwright_script = IntelligentScriptGenerator.generate_script_with_real_locators(test_case)
        
        yield {
            status_comp: gr.update(value="✅ Script Ready"),
            log_comp: gr.update(value="\n".join(test_case.exploration_log))
        }
        
    except Exception as e:
        test_case.status = "failed"
        test_case.exploration_log.append(f"❌ Exploration failed: {str(e)}")
        
        yield {
            status_comp: gr.update(value="❌ Exploration Failed"),
            log_comp: gr.update(value="\n".join(test_case.exploration_log))
        }


async def _run_playwright_test(
    webui_manager: WebuiManager,
    test_case: TestCase
) -> AsyncGenerator[Dict, None]:
    """Phase 2: Run the generated Playwright test and get original reports"""
    
    status_comp = webui_manager.get_component_by_id("test_automation.status")
    execution_log_comp = webui_manager.get_component_by_id("test_automation.execution_log")
    report_comp = webui_manager.get_component_by_id("test_automation.test_report")
    
    test_case.status = "test_running"
    test_case.test_execution_log = ["🎭 Running Playwright test with discovered locators..."]
    
    yield {
        status_comp: gr.update(value="🎭 Running Playwright Test"),
        execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log))
    }
    
    try:
        # Create test directory and files
        test_dir = os.path.join("./tmp/test_results", test_case.id)
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
    timeout: 30000,
    use: {{
        headless: true,
        viewport: {{ width: 1280, height: 720 }},
        screenshot: 'on-failure',
        video: 'retain-on-failure',
    }},
    reporter: [
        ['html', {{ outputFolder: 'playwright-report' }}],
        ['json', {{ outputFile: 'test-results.json' }}],
        ['junit', {{ outputFile: 'junit-results.xml' }}]
    ],
    outputDir: 'test-results',
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
        
        yield {
            execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log))
        }
        
        # Run the test
        test_case.test_execution_log.append("🚀 Executing Playwright test...")
        
        test_cmd = ["npx", "playwright", "test", "--config", config_file]
        result = subprocess.run(test_cmd, cwd=test_dir, capture_output=True, text=True)
        
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
        
        yield {
            status_comp: gr.update(value="🎉 Test Completed"),
            execution_log_comp: gr.update(value="\n".join(test_case.test_execution_log)),
            report_comp: gr.File(value=report_index if os.path.exists(report_index) else None)
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
                
                create_btn = gr.Button("🚀 Create Test", variant="primary")
                
                gr.Markdown("## 🎯 Test Control")
                
                test_selector = gr.Dropdown(
                    label="Select Test",
                    choices=[],
                    interactive=True
                )
                
                with gr.Row():
                    explore_btn = gr.Button("🔍 Explore Page", variant="secondary")
                    run_test_btn = gr.Button("🎭 Run Playwright Test", variant="primary")
                
                status = gr.Textbox(
                    label="Status",
                    value="Ready to create tests",
                    interactive=False
                )
            
            # Right Panel - Results & Script
            with gr.Column(scale=1):
                gr.Markdown("## 📋 Generated Script")
                
                playwright_script = gr.Code(
                    label="Playwright Test Script (with Real Locators)",
                    language="javascript",
                    lines=15
                )
                
                download_script_btn = gr.Button("💾 Download Script", variant="secondary")
                
                gr.Markdown("## 📊 Test Results")
                
                test_report = gr.File(
                    label="Playwright HTML Report",
                    file_types=[".html"]
                )
                
                view_report_btn = gr.Button("👁️ View Report", variant="secondary")
        
        # Live Browser View Section
        with gr.Row():
            gr.Markdown("## 🖥️ Live Browser View")
            vnc_link = gr.HTML(
                value='<div style="text-align: center; padding: 20px;"><a href="http://localhost:6080/vnc.html?host=localhost&port=6080" target="_blank" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">🖥️ Open Live Browser View</a><br><br><small>Click to watch the agent work in real-time!</small></div>',
                label="Browser Access"
            )
        
        # Logs Section
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 🔍 Exploration Log")
                exploration_log = gr.Textbox(
                    label="Agent Page Exploration",
                    lines=8,
                    interactive=False
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
        "create_btn": create_btn,
        "test_selector": test_selector,
        "explore_btn": explore_btn,
        "run_test_btn": run_test_btn,
        "status": status,
        "playwright_script": playwright_script,
        "download_script_btn": download_script_btn,
        "test_report": test_report,
        "view_report_btn": view_report_btn,
        "vnc_link": vnc_link,
        "exploration_log": exploration_log,
        "execution_log": execution_log,
    }
    
    webui_manager.add_components("test_automation", tab_components)
    
    # Event handlers
    def create_test(name, url, steps_text):
        """Create new test case"""
        if not name or not url or not steps_text:
            return {
                test_selector: gr.update(choices=[]),
                status: gr.update(value="❌ Please fill all fields")
            }
        
        steps = [line.strip() for line in steps_text.strip().split('\n') if line.strip()]
        
        if not steps:
            return {
                test_selector: gr.update(choices=[]),
                status: gr.update(value="❌ No valid steps found")
            }
        
        test_case = TestCase(name=name, description="", url=url, steps=steps)
        webui_manager.test_cases.append(test_case)
        
        choices = [(tc.name, tc.id) for tc in webui_manager.test_cases]
        
        return {
            test_selector: gr.update(choices=choices, value=test_case.id),
            status: gr.update(value=f"✅ Created: {name} (Ready for exploration)")
        }
    
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
    
    async def run_playwright_test(test_id):
        """Run the generated Playwright test"""
        if not test_id:
            yield {status: gr.update(value="❌ No test selected")}
            return
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case:
            yield {status: gr.update(value="❌ Test not found")}
            return
        
        if test_case.status != "script_ready":
            yield {status: gr.update(value="❌ Must explore page first")}
            return
        
        async for update in _run_playwright_test(webui_manager, test_case):
            yield update
    
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
        """Open the Playwright HTML report"""
        if not test_id:
            return None
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case or not test_case.playwright_report_path:
            return None
        
        return test_case.playwright_report_path
    
    # Connect events
    all_components = set(webui_manager.get_components())
    
    create_btn.click(
        fn=create_test,
        inputs=[test_name, test_url, test_steps],
        outputs=[test_selector, status]
    )
    
    async def explore_wrapper(test_id, *components_values):
        components_dict = dict(zip(all_components, components_values))
        async for update in explore_page(test_id, components_dict):
            yield update
    
    explore_btn.click(
        fn=explore_wrapper,
        inputs=[test_selector] + list(all_components),
        outputs=[status, exploration_log, playwright_script]
    )
    
    async def run_test_wrapper(test_id):
        async for update in run_playwright_test(test_id):
            yield update
    
    run_test_btn.click(
        fn=run_test_wrapper,
        inputs=[test_selector],
        outputs=[status, execution_log, test_report]
    )
    
    test_selector.change(
        fn=update_script_display,
        inputs=[test_selector],
        outputs=[playwright_script]
    )
    
    download_script_btn.click(
        fn=download_script,
        inputs=[test_selector],
        outputs=[gr.File()]
    )
    
    view_report_btn.click(
        fn=view_report,
        inputs=[test_selector],
        outputs=[gr.File()]
    )