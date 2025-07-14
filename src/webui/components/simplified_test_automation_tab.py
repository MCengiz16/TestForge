import asyncio
import json
import logging
import os
import uuid
import re
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
    """Simplified test case class"""
    def __init__(self, name: str, description: str, url: str, steps: List[Dict]):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.url = url
        self.steps = steps
        self.created_at = datetime.now()
        self.status = "pending"
        self.execution_log = []
        self.playwright_script = ""
        self.errors = []


class TestStepParser:
    """Parse natural language to test steps"""
    
    @staticmethod
    def parse_natural_language_step(step_text: str) -> Dict:
        """Convert natural language to structured step"""
        step_text = step_text.strip()
        
        patterns = {
            r"(?i)^(?:navigate|go)\s+to\s+(.+)": {"action": "navigate", "target": "url"},
            r"(?i)^(?:click|tap)\s+(?:on\s+)?(.+)": {"action": "click", "target": "element"},
            r"(?i)^(?:type|enter|input)\s+['\"]([^'\"]+)['\"](?:\s+in(?:to)?(?:\s+the)?\s+(.+))?": {"action": "type", "target": "input"},
            r"(?i)^(?:fill|enter)\s+(.+)\s+with\s+['\"]([^'\"]+)['\"]": {"action": "fill", "target": "input"},
            r"(?i)^(?:select|choose)\s+['\"]([^'\"]+)['\"](?:\s+from\s+(.+))?": {"action": "select", "target": "dropdown"},
            r"(?i)^(?:wait)\s+(?:for\s+)?(\d+)\s*(?:seconds?|ms|milliseconds?)": {"action": "wait", "target": "time"},
            r"(?i)^(?:verify|check|assert)\s+(?:that\s+)?(.+)\s+(?:contains|has|shows)\s+['\"]([^'\"]+)['\"]": {"action": "verify_text", "target": "element"},
            r"(?i)^(?:take\s+)?screenshot": {"action": "screenshot", "target": "page"},
        }
        
        for pattern, action_info in patterns.items():
            match = re.match(pattern, step_text)
            if match:
                groups = match.groups()
                if action_info["action"] == "navigate":
                    return {"action": "navigate", "url": groups[0].strip()}
                elif action_info["action"] == "click":
                    return {"action": "click", "selector": groups[0].strip()}
                elif action_info["action"] == "type":
                    text = groups[0]
                    selector = groups[1] if len(groups) > 1 and groups[1] else "input"
                    return {"action": "type", "selector": selector.strip(), "text": text}
                elif action_info["action"] == "fill":
                    selector = groups[0].strip()
                    text = groups[1]
                    return {"action": "fill", "selector": selector, "text": text}
                elif action_info["action"] == "select":
                    value = groups[0]
                    selector = groups[1] if len(groups) > 1 and groups[1] else "select"
                    return {"action": "select", "selector": selector.strip(), "value": value}
                elif action_info["action"] == "wait":
                    time_str = groups[0]
                    time_ms = int(time_str) * 1000 if "ms" not in step_text.lower() else int(time_str)
                    return {"action": "wait", "timeout": time_ms}
                elif action_info["action"] == "verify_text":
                    return {"action": "verify_text", "selector": groups[0].strip(), "expected": groups[1]}
                elif action_info["action"] == "screenshot":
                    return {"action": "screenshot"}
        
        return {"action": "manual", "description": step_text}


class PlaywrightGenerator:
    """Generate clean Playwright scripts"""
    
    @staticmethod
    def generate_script(test_case: TestCase) -> str:
        """Generate Playwright test script"""
        script = f'''// Test: {test_case.name}
// Description: {test_case.description}
// Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

const {{ test, expect }} = require('@playwright/test');

test('{test_case.name}', async ({{ page }}) => {{
    // Configure test
    await page.setViewportSize({{ width: 1280, height: 720 }});
    
'''
        
        for i, step in enumerate(test_case.steps, 1):
            script += f"    // Step {i}: {PlaywrightGenerator._get_step_description(step)}\n"
            script += PlaywrightGenerator._generate_step_code(step, i)
        
        script += '''
    // Final screenshot
    await page.screenshot({ path: 'test-complete.png', fullPage: true });
});
'''
        return script
    
    @staticmethod
    def _get_step_description(step: Dict) -> str:
        action = step.get("action", "unknown")
        if action == "navigate":
            return f"Navigate to {step.get('url', 'URL')}"
        elif action == "click":
            return f"Click {step.get('selector', 'element')}"
        elif action == "type":
            return f"Type '{step.get('text', '')}' into {step.get('selector', 'input')}"
        elif action == "fill":
            return f"Fill {step.get('selector', 'field')} with '{step.get('text', '')}'"
        elif action == "verify_text":
            return f"Verify {step.get('selector', 'element')} contains '{step.get('expected', '')}'"
        elif action == "screenshot":
            return "Take screenshot"
        elif action == "wait":
            return f"Wait {step.get('timeout', 1000)}ms"
        else:
            return step.get("description", "Manual step")
    
    @staticmethod
    def _generate_step_code(step: Dict, step_num: int) -> str:
        action = step.get("action")
        
        if action == "navigate":
            url = step.get("url", "")
            return f"    await page.goto('{url}');\n    await page.waitForLoadState('networkidle');\n\n"
        
        elif action == "click":
            selector = step.get("selector", "")
            clean_selector = PlaywrightGenerator._clean_selector(selector)
            return f"    await page.click('{clean_selector}');\n\n"
        
        elif action in ["type", "fill"]:
            selector = step.get("selector", "input")
            text = step.get("text", "")
            clean_selector = PlaywrightGenerator._clean_selector(selector)
            return f"    await page.fill('{clean_selector}', '{text}');\n\n"
        
        elif action == "verify_text":
            selector = step.get("selector", "")
            expected = step.get("expected", "")
            clean_selector = PlaywrightGenerator._clean_selector(selector)
            return f"    await expect(page.locator('{clean_selector}')).toContainText('{expected}');\n\n"
        
        elif action == "wait":
            timeout = step.get("timeout", 1000)
            return f"    await page.waitForTimeout({timeout});\n\n"
        
        elif action == "screenshot":
            return f"    await page.screenshot({{ path: 'step{step_num}.png' }});\n\n"
        
        else:
            return f"    // TODO: {step.get('description', 'Manual action')}\n\n"
    
    @staticmethod
    def _clean_selector(selector: str) -> str:
        selector = selector.strip().strip('"\'')
        if not any(char in selector for char in ['#', '.', '[', '>']):
            return f"text={selector}"
        return selector


async def _initialize_llm_for_test(webui_manager: WebuiManager, components: Dict) -> Optional[BaseChatModel]:
    """Initialize LLM for test execution"""
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


async def _execute_test_case(
    webui_manager: WebuiManager,
    test_case: TestCase,
    components: Dict
) -> AsyncGenerator[Dict, None]:
    """Execute test case with agent"""
    
    # Get components
    status_comp = webui_manager.get_component_by_id("test_automation.status")
    log_comp = webui_manager.get_component_by_id("test_automation.execution_log")
    
    test_case.status = "running"
    test_case.execution_log = ["🚀 Starting test execution..."]
    
    yield {
        status_comp: gr.update(value="🔄 Running Test"),
        log_comp: gr.update(value="\n".join(test_case.execution_log))
    }
    
    try:
        # Initialize LLM
        llm = await _initialize_llm_for_test(webui_manager, components)
        if not llm:
            raise Exception("Failed to initialize LLM")
        
        # Browser settings (using default values for testing)

        # Create test environment
        test_dir = os.path.join("./tmp/test_results", test_case.id)
        os.makedirs(test_dir, exist_ok=True)
        
        browser_config = BrowserConfig(
            headless=True,
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
        
        # Execute steps
        for i, step in enumerate(test_case.steps, 1):
            try:
                step_desc = PlaywrightGenerator._get_step_description(step)
                test_case.execution_log.append(f"Step {i}: {step_desc}")
                
                # Create agent task
                task = f"Execute: {step_desc}"
                if step.get("action") == "navigate":
                    task = f"Navigate to {step.get('url')}"
                
                controller = CustomController()
                agent = BrowserUseAgent(
                    task=task,
                    llm=llm,
                    browser=browser,
                    browser_context=context,
                    controller=controller,
                    use_vision=True,
                    max_actions_per_step=3,
                    source="test_automation",
                )
                
                # Execute with timeout
                await asyncio.wait_for(agent.run(max_steps=2), timeout=20.0)
                
                test_case.execution_log.append(f"✅ Step {i} completed")
                
                yield {
                    status_comp: gr.update(value=f"🔄 Running Step {i}/{len(test_case.steps)}"),
                    log_comp: gr.update(value="\n".join(test_case.execution_log))
                }
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                error_msg = f"❌ Step {i} failed: {str(e)}"
                test_case.execution_log.append(error_msg)
                test_case.errors.append(error_msg)
                
                yield {
                    log_comp: gr.update(value="\n".join(test_case.execution_log))
                }
                continue
        
        # Clean up
        await context.close()
        await browser.close()
        
        # Generate script
        test_case.playwright_script = PlaywrightGenerator.generate_script(test_case)
        
        # Save script
        script_path = os.path.join(test_dir, f"{test_case.name.replace(' ', '_')}.spec.js")
        with open(script_path, 'w') as f:
            f.write(test_case.playwright_script)
        
        test_case.status = "completed" if not test_case.errors else "failed"
        test_case.execution_log.append(f"🎉 Test {'completed' if not test_case.errors else 'failed'}")
        
        yield {
            status_comp: gr.update(value=f"{'✅ Completed' if not test_case.errors else '❌ Failed'}"),
            log_comp: gr.update(value="\n".join(test_case.execution_log))
        }
        
    except Exception as e:
        test_case.status = "failed"
        test_case.execution_log.append(f"💥 Test execution failed: {str(e)}")
        
        yield {
            status_comp: gr.update(value="❌ Failed"),
            log_comp: gr.update(value="\n".join(test_case.execution_log))
        }


def create_test_automation_tab(webui_manager: WebuiManager):
    """Create simplified test automation interface"""
    
    webui_manager.test_cases = []
    
    with gr.Column():
        gr.Markdown("# 🧪 Test Automation", elem_classes=["tab-header-text"])
        
        with gr.Row():
            # Left column - Test Creation
            with gr.Column(scale=1):
                gr.Markdown("## Create Test")
                
                test_name = gr.Textbox(
                    label="Test Name",
                    placeholder="e.g., Login Test",
                    lines=1
                )
                
                test_url = gr.Textbox(
                    label="Starting URL",
                    placeholder="https://example.com",
                    lines=1
                )
                
                test_steps = gr.Textbox(
                    label="Test Steps (Natural Language)",
                    placeholder="""Enter each step on a new line:
Navigate to https://example.com/login
Type "user@example.com" into email field
Type "password123" into password field
Click login button
Verify that dashboard contains "Welcome"
Take screenshot""",
                    lines=8
                )
                
                create_btn = gr.Button("🚀 Create Test", variant="primary")
                
                gr.Markdown("## Execute Test")
                
                test_selector = gr.Dropdown(
                    label="Select Test",
                    choices=[],
                    interactive=True
                )
                
                execute_btn = gr.Button("▶️ Execute Test", variant="primary")
                
                status = gr.Textbox(
                    label="Status",
                    value="Ready",
                    interactive=False
                )
            
            # Right column - Results
            with gr.Column(scale=1):
                gr.Markdown("## Test Script")
                
                playwright_script = gr.Code(
                    label="Generated Playwright Script",
                    language="javascript",
                    lines=12
                )
                
                download_btn = gr.Button("💾 Download Script", variant="secondary")
                
                gr.Markdown("## Execution Log")
                
                execution_log = gr.Textbox(
                    label="Test Execution",
                    lines=10,
                    interactive=False
                )
    
    # Store components
    tab_components = {
        "test_name": test_name,
        "test_url": test_url,
        "test_steps": test_steps,
        "create_btn": create_btn,
        "test_selector": test_selector,
        "execute_btn": execute_btn,
        "status": status,
        "playwright_script": playwright_script,
        "download_btn": download_btn,
        "execution_log": execution_log,
    }
    
    webui_manager.add_components("test_automation", tab_components)
    
    # Event handlers
    def create_test(name, url, steps_text):
        """Create test case from input"""
        if not name or not url or not steps_text:
            return {
                test_selector: gr.update(choices=[]),
                playwright_script: gr.update(value=""),
                status: gr.update(value="❌ Please fill all fields")
            }
        
        # Parse steps
        steps = []
        for line in steps_text.strip().split('\n'):
            if line.strip():
                step = TestStepParser.parse_natural_language_step(line.strip())
                steps.append(step)
        
        if not steps:
            return {
                test_selector: gr.update(choices=[]),
                playwright_script: gr.update(value=""),
                status: gr.update(value="❌ No valid steps found")
            }
        
        # Create test case
        test_case = TestCase(name=name, description="", url=url, steps=steps)
        test_case.playwright_script = PlaywrightGenerator.generate_script(test_case)
        
        webui_manager.test_cases.append(test_case)
        
        # Update UI
        choices = [(tc.name, tc.id) for tc in webui_manager.test_cases]
        
        return {
            test_selector: gr.update(choices=choices, value=test_case.id),
            playwright_script: gr.update(value=test_case.playwright_script),
            status: gr.update(value=f"✅ Created: {name}")
        }
    
    async def execute_test(test_id, components_dict):
        """Execute selected test"""
        if not test_id:
            yield {status: gr.update(value="❌ No test selected")}
            return
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case:
            yield {status: gr.update(value="❌ Test not found")}
            return
        
        async for update in _execute_test_case(webui_manager, test_case, components_dict):
            yield update
    
    def download_script(test_id):
        """Download script for selected test"""
        if not test_id:
            return None
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case:
            return None
        
        script_path = os.path.join("./tmp", f"{test_case.name.replace(' ', '_')}.spec.js")
        os.makedirs("./tmp", exist_ok=True)
        
        with open(script_path, 'w') as f:
            f.write(test_case.playwright_script)
        
        return script_path
    
    def update_script_display(test_id):
        """Update script display when test is selected"""
        if not test_id:
            return gr.update(value="")
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case:
            return gr.update(value="")
        
        return gr.update(value=test_case.playwright_script or "")
    
    # Connect events
    all_components = set(webui_manager.get_components())
    
    create_btn.click(
        fn=create_test,
        inputs=[test_name, test_url, test_steps],
        outputs=[test_selector, playwright_script, status]
    )
    
    async def execute_wrapper(test_id, *components_values):
        # Convert positional args back to components dict
        components_dict = dict(zip(all_components, components_values))
        async for update in execute_test(test_id, components_dict):
            yield update
    
    execute_btn.click(
        fn=execute_wrapper,
        inputs=[test_selector] + list(all_components),
        outputs=[status, execution_log]
    )
    
    test_selector.change(
        fn=update_script_display,
        inputs=[test_selector],
        outputs=[playwright_script]
    )
    
    download_btn.click(
        fn=download_script,
        inputs=[test_selector],
        outputs=[gr.File()]
    )