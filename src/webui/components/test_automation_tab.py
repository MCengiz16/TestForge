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
    """Represents a test case with steps and validation"""
    def __init__(self, name: str, description: str, url: str, steps: List[Dict], expected_outcomes: List[str]):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.url = url
        self.steps = steps  # List of step dictionaries
        self.expected_outcomes = expected_outcomes
        self.created_at = datetime.now()
        self.status = "pending"  # pending, running, passed, failed
        self.execution_log = []
        self.playwright_script = ""
        self.screenshots = []
        self.errors = []


class TestStepParser:
    """Parses natural language and structured test steps"""
    
    @staticmethod
    def parse_natural_language_step(step_text: str) -> Dict:
        """Convert natural language to structured step"""
        step_text = step_text.strip()
        
        # Common patterns for test actions
        patterns = {
            r"(?i)^(?:navigate|go)\s+to\s+(.+)": {"action": "navigate", "target": "url"},
            r"(?i)^(?:click|tap)\s+(?:on\s+)?(.+)": {"action": "click", "target": "element"},
            r"(?i)^(?:type|enter|input)\s+['\"]([^'\"]+)['\"](?:\s+in(?:to)?(?:\s+the)?\s+(.+))?": {"action": "type", "target": "input"},
            r"(?i)^(?:fill|enter)\s+(.+)\s+with\s+['\"]([^'\"]+)['\"]": {"action": "fill", "target": "input"},
            r"(?i)^(?:select|choose)\s+['\"]([^'\"]+)['\"](?:\s+from\s+(.+))?": {"action": "select", "target": "dropdown"},
            r"(?i)^(?:wait)\s+(?:for\s+)?(\d+)\s*(?:seconds?|ms|milliseconds?)": {"action": "wait", "target": "time"},
            r"(?i)^(?:wait)\s+(?:for\s+)?(.+)\s+(?:to\s+(?:appear|be\s+visible|load))": {"action": "wait_for_element", "target": "element"},
            r"(?i)^(?:verify|check|assert)\s+(?:that\s+)?(.+)\s+(?:contains|has|shows)\s+['\"]([^'\"]+)['\"]": {"action": "verify_text", "target": "element"},
            r"(?i)^(?:verify|check|assert)\s+(?:that\s+)?(.+)\s+(?:is\s+)?(?:visible|displayed|present)": {"action": "verify_visible", "target": "element"},
            r"(?i)^(?:verify|check|assert)\s+(?:that\s+)?(?:page\s+)?title\s+(?:is|contains)\s+['\"]([^'\"]+)['\"]": {"action": "verify_title", "target": "text"},
            r"(?i)^(?:verify|check|assert)\s+(?:that\s+)?url\s+(?:is|contains)\s+['\"]([^'\"]+)['\"]": {"action": "verify_url", "target": "text"},
            r"(?i)^(?:take\s+)?screenshot": {"action": "screenshot", "target": "page"},
            r"(?i)^(?:scroll)\s+(?:down|up)": {"action": "scroll", "target": "direction"},
            r"(?i)^(?:hover|mouseover)\s+(?:on\s+)?(.+)": {"action": "hover", "target": "element"},
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
                    # Convert to milliseconds if needed
                    if "ms" in step_text.lower():
                        time_ms = int(time_str)
                    else:
                        time_ms = int(time_str) * 1000
                    return {"action": "wait", "timeout": time_ms}
                elif action_info["action"] == "wait_for_element":
                    return {"action": "wait_for_element", "selector": groups[0].strip()}
                elif action_info["action"] == "verify_text":
                    return {"action": "verify_text", "selector": groups[0].strip(), "expected": groups[1]}
                elif action_info["action"] == "verify_visible":
                    return {"action": "verify_visible", "selector": groups[0].strip()}
                elif action_info["action"] == "verify_title":
                    return {"action": "verify_title", "expected": groups[0]}
                elif action_info["action"] == "verify_url":
                    return {"action": "verify_url", "expected": groups[0]}
                elif action_info["action"] == "screenshot":
                    return {"action": "screenshot"}
                elif action_info["action"] == "scroll":
                    direction = "down" if "down" in step_text.lower() else "up"
                    return {"action": "scroll", "direction": direction}
                elif action_info["action"] == "hover":
                    return {"action": "hover", "selector": groups[0].strip()}
        
        # If no pattern matches, return a generic step
        return {"action": "manual", "description": step_text}

    @staticmethod
    def validate_step(step: Dict) -> Tuple[bool, str]:
        """Validate if a step has required fields"""
        required_fields = {
            "navigate": ["url"],
            "click": ["selector"],
            "type": ["selector", "text"],
            "fill": ["selector", "text"],
            "select": ["selector", "value"],
            "wait": ["timeout"],
            "wait_for_element": ["selector"],
            "verify_text": ["selector", "expected"],
            "verify_visible": ["selector"],
            "verify_title": ["expected"],
            "verify_url": ["expected"],
            "screenshot": [],
            "scroll": ["direction"],
            "hover": ["selector"],
            "manual": ["description"]
        }
        
        action = step.get("action")
        if not action:
            return False, "Step must have an 'action' field"
        
        if action not in required_fields:
            return False, f"Unknown action: {action}"
        
        for field in required_fields[action]:
            if field not in step:
                return False, f"Action '{action}' requires field: {field}"
        
        return True, "Valid step"


class PlaywrightScriptGenerator:
    """Generates Playwright JavaScript test scripts"""
    
    @staticmethod
    def generate_script(test_case: TestCase) -> str:
        """Generate complete Playwright test script"""
        script_header = f'''// Test: {test_case.name}
// Description: {test_case.description}
// Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

const {{ test, expect }} = require('@playwright/test');

test('{test_case.name}', async ({{ page }}) => {{
    // Enable video recording and screenshots
    await page.video().saveAs('{test_case.name.replace(" ", "_")}_video.webm');
    
    // Start test execution
'''
        
        script_body = ""
        step_num = 1
        
        for step in test_case.steps:
            script_body += f"\n    // Step {step_num}: {step.get('description', PlaywrightScriptGenerator._get_step_description(step))}\n"
            script_body += PlaywrightScriptGenerator._generate_step_code(step, step_num)
            step_num += 1
        
        # Add expected outcomes as assertions
        if test_case.expected_outcomes:
            script_body += "\n    // Final validations\n"
            for i, outcome in enumerate(test_case.expected_outcomes, 1):
                script_body += f"    // Expected outcome {i}: {outcome}\n"
                script_body += PlaywrightScriptGenerator._generate_assertion_from_text(outcome)
        
        script_footer = '''
    // Take final screenshot
    await page.screenshot({ path: 'final_screenshot.png', fullPage: true });
});
'''
        
        return script_header + script_body + script_footer
    
    @staticmethod
    def _get_step_description(step: Dict) -> str:
        """Get human readable description of step"""
        action = step.get("action", "unknown")
        if action == "navigate":
            return f"Navigate to {step.get('url', 'URL')}"
        elif action == "click":
            return f"Click on {step.get('selector', 'element')}"
        elif action == "type":
            return f"Type '{step.get('text', 'text')}' into {step.get('selector', 'input')}"
        elif action == "fill":
            return f"Fill {step.get('selector', 'field')} with '{step.get('text', 'text')}'"
        elif action == "select":
            return f"Select '{step.get('value', 'option')}' from {step.get('selector', 'dropdown')}"
        elif action == "wait":
            return f"Wait for {step.get('timeout', 0)} milliseconds"
        elif action == "wait_for_element":
            return f"Wait for {step.get('selector', 'element')} to be visible"
        elif action == "verify_text":
            return f"Verify {step.get('selector', 'element')} contains '{step.get('expected', 'text')}'"
        elif action == "verify_visible":
            return f"Verify {step.get('selector', 'element')} is visible"
        elif action == "verify_title":
            return f"Verify page title is '{step.get('expected', 'title')}'"
        elif action == "verify_url":
            return f"Verify URL contains '{step.get('expected', 'url')}'"
        elif action == "screenshot":
            return "Take screenshot"
        elif action == "scroll":
            return f"Scroll {step.get('direction', 'down')}"
        elif action == "hover":
            return f"Hover over {step.get('selector', 'element')}"
        else:
            return step.get("description", "Manual step")
    
    @staticmethod
    def _generate_step_code(step: Dict, step_num: int) -> str:
        """Generate Playwright code for a single step"""
        action = step.get("action")
        
        try:
            if action == "navigate":
                url = step.get("url", "")
                return f"    await page.goto('{url}');\n    await page.waitForLoadState('networkidle');\n"
            
            elif action == "click":
                selector = step.get("selector", "")
                # Try to make selector more specific
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await page.waitForSelector('{clean_selector}', {{ visible: true }});\n    await page.click('{clean_selector}');\n"
            
            elif action == "type":
                selector = step.get("selector", "input")
                text = step.get("text", "")
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await page.waitForSelector('{clean_selector}', {{ visible: true }});\n    await page.fill('{clean_selector}', '{text}');\n"
            
            elif action == "fill":
                selector = step.get("selector", "")
                text = step.get("text", "")
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await page.waitForSelector('{clean_selector}', {{ visible: true }});\n    await page.fill('{clean_selector}', '{text}');\n"
            
            elif action == "select":
                selector = step.get("selector", "select")
                value = step.get("value", "")
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await page.waitForSelector('{clean_selector}', {{ visible: true }});\n    await page.selectOption('{clean_selector}', '{value}');\n"
            
            elif action == "wait":
                timeout = step.get("timeout", 1000)
                return f"    await page.waitForTimeout({timeout});\n"
            
            elif action == "wait_for_element":
                selector = step.get("selector", "")
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await page.waitForSelector('{clean_selector}', {{ visible: true, timeout: 10000 }});\n"
            
            elif action == "verify_text":
                selector = step.get("selector", "")
                expected = step.get("expected", "")
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await expect(page.locator('{clean_selector}')).toContainText('{expected}');\n"
            
            elif action == "verify_visible":
                selector = step.get("selector", "")
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await expect(page.locator('{clean_selector}')).toBeVisible();\n"
            
            elif action == "verify_title":
                expected = step.get("expected", "")
                return f"    await expect(page).toHaveTitle(/{expected}/i);\n"
            
            elif action == "verify_url":
                expected = step.get("expected", "")
                return f"    await expect(page).toHaveURL(/{expected}/);\n"
            
            elif action == "screenshot":
                return f"    await page.screenshot({{ path: 'step_{step_num}_screenshot.png', fullPage: true }});\n"
            
            elif action == "scroll":
                direction = step.get("direction", "down")
                if direction == "down":
                    return f"    await page.mouse.wheel(0, 500);\n"
                else:
                    return f"    await page.mouse.wheel(0, -500);\n"
            
            elif action == "hover":
                selector = step.get("selector", "")
                clean_selector = PlaywrightScriptGenerator._clean_selector(selector)
                return f"    await page.waitForSelector('{clean_selector}', {{ visible: true }});\n    await page.hover('{clean_selector}');\n"
            
            else:
                return f"    // Manual step: {step.get('description', 'Perform manual action')}\n    // TODO: Implement this step manually\n"
        
        except Exception as e:
            logger.error(f"Error generating code for step {step}: {e}")
            return f"    // Error generating code for step: {step}\n"
    
    @staticmethod
    def _clean_selector(selector: str) -> str:
        """Clean and improve selector for Playwright"""
        # Remove quotes and extra spaces
        selector = selector.strip().strip('"\'')
        
        # If it looks like a text description, convert to CSS selector
        if not any(char in selector for char in ['#', '.', '[', '>', ' ']):
            # Likely plain text, convert to text-based selector
            return f"text={selector}"
        
        return selector
    
    @staticmethod
    def _generate_assertion_from_text(outcome_text: str) -> str:
        """Generate assertion code from expected outcome text"""
        # This is a simple implementation - could be enhanced with NLP
        outcome_lower = outcome_text.lower()
        
        if "visible" in outcome_lower or "displayed" in outcome_lower:
            return f"    // await expect(page.locator('element-selector')).toBeVisible();\n"
        elif "text" in outcome_lower or "contains" in outcome_lower:
            return f"    // await expect(page.locator('element-selector')).toContainText('expected-text');\n"
        elif "url" in outcome_lower:
            return f"    // await expect(page).toHaveURL(/expected-url/);\n"
        elif "title" in outcome_lower:
            return f"    // await expect(page).toHaveTitle(/expected-title/);\n"
        else:
            return f"    // Verify: {outcome_text}\n"


async def _initialize_llm_for_test(
        provider: Optional[str],
        model_name: Optional[str],
        temperature: float,
        base_url: Optional[str],
        api_key: Optional[str],
        num_ctx: Optional[int] = None,
) -> Optional[BaseChatModel]:
    """Initialize LLM for test execution"""
    if not provider or not model_name:
        logger.info("LLM Provider or Model Name not specified for test execution.")
        return None
    try:
        logger.info(f"Initializing Test LLM: Provider={provider}, Model={model_name}")
        llm = llm_provider.get_llm_model(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            base_url=base_url or None,
            api_key=api_key or None,
            num_ctx=num_ctx if provider == "ollama" else None,
        )
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize Test LLM: {e}", exc_info=True)
        gr.Warning(f"Failed to initialize LLM for test execution. Error: {e}")
        return None


async def _execute_test_case(
        webui_manager: WebuiManager,
        test_case: TestCase,
        components: Dict[gr.components.Component, Any]
) -> AsyncGenerator[Dict[gr.components.Component, Any], None]:
    """Execute a test case and generate Playwright script"""
    
    # Get UI components
    test_output_comp = webui_manager.get_component_by_id("test_automation.test_output")
    test_status_comp = webui_manager.get_component_by_id("test_automation.test_status")
    playwright_script_comp = webui_manager.get_component_by_id("test_automation.playwright_script")
    test_report_comp = webui_manager.get_component_by_id("test_automation.test_report")
    execution_video_comp = webui_manager.get_component_by_id("test_automation.execution_video")
    
    test_case.status = "running"
    test_case.execution_log = []
    test_case.errors = []
    
    yield {
        test_status_comp: gr.update(value=f"🔄 Running: {test_case.name}"),
        test_output_comp: gr.update(value=[]),
    }
    
    try:
        # Get settings from webui_manager
        def get_setting(key, default=None):
            comp = webui_manager.id_to_component.get(f"agent_settings.{key}")
            return components.get(comp, default) if comp else default

        # LLM settings
        llm_provider_name = get_setting("llm_provider", None)
        llm_model_name = get_setting("llm_model_name", None)
        llm_temperature = get_setting("llm_temperature", 0.6)
        llm_base_url = get_setting("llm_base_url") or None
        llm_api_key = get_setting("llm_api_key") or None
        ollama_num_ctx = get_setting("ollama_num_ctx", 16000)
        
        # Browser settings (using default values)
        headless = True  # Force headless for testing
        window_w = 1280
        window_h = 1100
        
        # Initialize LLM
        main_llm = await _initialize_llm_for_test(
            llm_provider_name,
            llm_model_name,
            llm_temperature,
            llm_base_url,
            llm_api_key,
            ollama_num_ctx if llm_provider_name == "ollama" else None,
        )
        
        # Create test directories
        test_dir = os.path.join("./tmp/test_results", test_case.id)
        os.makedirs(test_dir, exist_ok=True)
        
        video_path = os.path.join(test_dir, f"{test_case.name.replace(' ', '_')}_recording.webm")
        
        # Initialize browser for testing
        browser_config = BrowserConfig(
            headless=True,  # Always headless for testing
            disable_security=True,
            new_context_config=BrowserContextConfig(
                window_width=window_w,
                window_height=window_h,
                save_recording_path=test_dir,
            )
        )
        
        test_browser = CustomBrowser(config=browser_config)
        context_config = BrowserContextConfig(
            save_recording_path=test_dir,
            window_width=window_w,
            window_height=window_h,
        )
        test_context = await test_browser.new_context(config=context_config)
        
        # Execute test steps
        step_num = 1
        for step in test_case.steps:
            try:
                test_case.execution_log.append(f"Step {step_num}: {TestStepParser._get_step_description(step)}")
                
                # Convert step to AI agent task
                task_description = f"Execute this test step: {PlaywrightScriptGenerator._get_step_description(step)}"
                
                if step.get("action") == "navigate":
                    task_description = f"Navigate to {step.get('url')}"
                elif step.get("action") == "manual":
                    task_description = step.get("description", "Perform manual action")
                
                # Create agent for this step
                controller = CustomController()
                agent = BrowserUseAgent(
                    task=task_description,
                    llm=main_llm,
                    browser=test_browser,
                    browser_context=test_context,
                    controller=controller,
                    use_vision=True,
                    max_actions_per_step=5,
                    source="test_automation",
                )
                
                # Execute step with timeout
                await asyncio.wait_for(agent.run(max_steps=3), timeout=30.0)
                
                # Take screenshot after step
                screenshot = await test_context.take_screenshot()
                if screenshot:
                    test_case.screenshots.append({
                        "step": step_num,
                        "screenshot": screenshot,
                        "description": PlaywrightScriptGenerator._get_step_description(step)
                    })
                
                test_case.execution_log.append(f"✅ Step {step_num} completed successfully")
                
                # Update UI
                yield {
                    test_status_comp: gr.update(value=f"🔄 Running: {test_case.name} (Step {step_num}/{len(test_case.steps)})"),
                    test_output_comp: gr.update(value=[
                        {"role": "assistant", "content": f"**Step {step_num}**: {PlaywrightScriptGenerator._get_step_description(step)}\n✅ Completed"}
                        for i in range(step_num)
                    ]),
                }
                
                step_num += 1
                await asyncio.sleep(1)  # Brief pause between steps
                
            except asyncio.TimeoutError:
                error_msg = f"⏰ Step {step_num} timed out"
                test_case.errors.append(error_msg)
                test_case.execution_log.append(error_msg)
                
                # Try to fix and continue
                yield {
                    test_output_comp: gr.update(value=test_case.execution_log + [
                        {"role": "assistant", "content": f"**Step {step_num}**: {PlaywrightScriptGenerator._get_step_description(step)}\n⚠️ Timeout - attempting to continue"}
                    ]),
                }
                step_num += 1
                continue
                
            except Exception as e:
                error_msg = f"❌ Step {step_num} failed: {str(e)}"
                test_case.errors.append(error_msg)
                test_case.execution_log.append(error_msg)
                logger.error(f"Test step {step_num} failed: {e}", exc_info=True)
                
                # Try to continue with next step
                yield {
                    test_output_comp: gr.update(value=test_case.execution_log + [
                        {"role": "assistant", "content": f"**Step {step_num}**: {PlaywrightScriptGenerator._get_step_description(step)}\n❌ Failed: {str(e)}"}
                    ]),
                }
                step_num += 1
                continue
        
        # Generate Playwright script
        test_case.playwright_script = PlaywrightScriptGenerator.generate_script(test_case)
        
        # Save script to file
        script_path = os.path.join(test_dir, f"{test_case.name.replace(' ', '_')}.spec.js")
        with open(script_path, 'w') as f:
            f.write(test_case.playwright_script)
        
        # Generate test report
        report = f"""# Test Execution Report

**Test Name:** {test_case.name}
**Description:** {test_case.description}
**Execution Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** {'✅ PASSED' if not test_case.errors else '❌ FAILED'}

## Steps Executed
{chr(10).join([f"- {log}" for log in test_case.execution_log])}

## Errors
{chr(10).join([f"- {error}" for error in test_case.errors]) if test_case.errors else "No errors"}

## Generated Files
- Playwright Script: {script_path}
- Screenshots: {len(test_case.screenshots)} captured
- Video Recording: {video_path if os.path.exists(video_path) else 'Not available'}
"""
        
        report_path = os.path.join(test_dir, "test_report.md")
        with open(report_path, 'w') as f:
            f.write(report)
        
        # Determine final status
        test_case.status = "passed" if not test_case.errors else "failed"
        
        # Clean up browser
        await test_context.close()
        await test_browser.close()
        
        # Final UI update
        yield {
            test_status_comp: gr.update(value=f"{'✅ PASSED' if test_case.status == 'passed' else '❌ FAILED'}: {test_case.name}"),
            test_output_comp: gr.update(value=[
                {"role": "assistant", "content": log} for log in test_case.execution_log
            ]),
            playwright_script_comp: gr.update(value=test_case.playwright_script),
            test_report_comp: gr.File(value=report_path),
            execution_video_comp: gr.Video(value=video_path if os.path.exists(video_path) else None),
        }
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        test_case.status = "failed"
        test_case.errors.append(f"Test execution failed: {str(e)}")
        
        yield {
            test_status_comp: gr.update(value=f"❌ FAILED: {test_case.name}"),
            test_output_comp: gr.update(value=[
                {"role": "assistant", "content": f"**Test Execution Failed**: {str(e)}"}
            ]),
        }


def create_test_automation_tab(webui_manager: WebuiManager):
    """Create the test automation tab"""
    
    webui_manager.test_cases = []  # Store test cases
    
    with gr.Column():
        gr.Markdown("""
        # 🧪 Test Automation Tool
        Create, execute, and generate Playwright test scripts automatically.
        """, elem_classes=["tab-header-text"])
        
        with gr.Tabs():
            # Test Case Creation Tab
            with gr.TabItem("📝 Create Test Case"):
                with gr.Row():
                    with gr.Column(scale=1):
                        test_name = gr.Textbox(
                            label="Test Name",
                            placeholder="e.g., User Login Test",
                            lines=1
                        )
                        test_description = gr.Textbox(
                            label="Test Description",
                            placeholder="e.g., Test user login functionality with valid credentials",
                            lines=2
                        )
                        test_url = gr.Textbox(
                            label="Starting URL",
                            placeholder="e.g., https://example.com/login",
                            lines=1
                        )
                        
                        with gr.Tabs():
                            with gr.TabItem("Natural Language"):
                                nl_steps = gr.Textbox(
                                    label="Test Steps (Natural Language)",
                                    placeholder="""Enter each step on a new line, e.g.:
Navigate to https://example.com/login
Type "testuser" into username field  
Type "password123" into password field
Click on login button
Verify that welcome message contains "Hello"
Take screenshot""",
                                    lines=10
                                )
                                
                            with gr.TabItem("Structured JSON"):
                                json_steps = gr.Code(
                                    label="Test Steps (JSON)",
                                    language="json",
                                    value='''[
    {"action": "navigate", "url": "https://example.com/login"},
    {"action": "fill", "selector": "#username", "text": "testuser"},
    {"action": "fill", "selector": "#password", "text": "password123"},
    {"action": "click", "selector": "button[type='submit']"},
    {"action": "verify_text", "selector": ".welcome", "expected": "Hello"},
    {"action": "screenshot"}
]''',
                                    lines=15
                                )
                        
                        expected_outcomes = gr.Textbox(
                            label="Expected Outcomes",
                            placeholder="""Enter expected outcomes, one per line:
User should be redirected to dashboard
Welcome message should be visible
URL should contain '/dashboard'""",
                            lines=5
                        )
                        
                        create_test_btn = gr.Button("🚀 Create Test Case", variant="primary")
                        
                    with gr.Column(scale=1):
                        test_preview = gr.Code(
                            label="Test Preview",
                            language="javascript",
                            lines=20
                        )
                        
                        validation_output = gr.Markdown("### Validation will appear here")
            
            # Test Execution Tab  
            with gr.TabItem("▶️ Execute Tests"):
                with gr.Row():
                    with gr.Column(scale=1):
                        test_selector = gr.Dropdown(
                            label="Select Test Case",
                            choices=[],
                            interactive=True
                        )
                        
                        execute_test_btn = gr.Button("🎬 Execute Test", variant="primary")
                        stop_test_btn = gr.Button("⏹️ Stop Test", variant="stop", interactive=False)
                        
                        test_status = gr.Textbox(
                            label="Test Status",
                            value="Ready to execute tests",
                            interactive=False
                        )
                        
                        test_output = gr.Chatbot(
                            label="Test Execution Log",
                            height=400,
                            type="messages"
                        )
                    
                    with gr.Column(scale=1):
                        live_screenshot = gr.Image(
                            label="Live Test Execution",
                            height=400
                        )
                        
                        execution_progress = gr.Progress()
            
            # Results & Scripts Tab
            with gr.TabItem("📊 Results & Scripts"):
                with gr.Row():
                    with gr.Column(scale=1):
                        playwright_script = gr.Code(
                            label="Generated Playwright Script",
                            language="javascript",
                            lines=25
                        )
                        
                        download_script_btn = gr.Button("💾 Download Script", variant="secondary")
                        
                    with gr.Column(scale=1):
                        test_report = gr.File(
                            label="Test Report",
                            file_types=[".md", ".html", ".pdf"]
                        )
                        
                        execution_video = gr.Video(
                            label="Test Execution Recording"
                        )
                        
                        test_screenshots = gr.Gallery(
                            label="Test Screenshots",
                            height=300,
                            columns=2
                        )
    
    # Store components in manager
    tab_components = {
        "test_name": test_name,
        "test_description": test_description,
        "test_url": test_url,
        "nl_steps": nl_steps,
        "json_steps": json_steps,
        "expected_outcomes": expected_outcomes,
        "create_test_btn": create_test_btn,
        "test_preview": test_preview,
        "validation_output": validation_output,
        "test_selector": test_selector,
        "execute_test_btn": execute_test_btn,
        "stop_test_btn": stop_test_btn,
        "test_status": test_status,
        "test_output": test_output,
        "live_screenshot": live_screenshot,
        "playwright_script": playwright_script,
        "download_script_btn": download_script_btn,
        "test_report": test_report,
        "execution_video": execution_video,
        "test_screenshots": test_screenshots,
    }
    
    webui_manager.add_components("test_automation", tab_components)
    
    # Event handlers
    def create_test_case(name, description, url, nl_steps, json_steps, outcomes):
        """Create a new test case"""
        try:
            if not name or not url:
                return {
                    validation_output: gr.update(value="❌ **Error**: Test name and URL are required"),
                    test_preview: gr.update(value="")
                }
            
            # Parse steps from natural language or JSON
            steps = []
            if nl_steps.strip():
                for line in nl_steps.strip().split('\n'):
                    if line.strip():
                        step = TestStepParser.parse_natural_language_step(line.strip())
                        steps.append(step)
            elif json_steps.strip():
                try:
                    steps = json.loads(json_steps)
                except json.JSONDecodeError as e:
                    return {
                        validation_output: gr.update(value=f"❌ **JSON Error**: {str(e)}"),
                        test_preview: gr.update(value="")
                    }
            
            if not steps:
                return {
                    validation_output: gr.update(value="❌ **Error**: No test steps provided"),
                    test_preview: gr.update(value="")
                }
            
            # Validate all steps
            validation_errors = []
            for i, step in enumerate(steps, 1):
                is_valid, error_msg = TestStepParser.validate_step(step)
                if not is_valid:
                    validation_errors.append(f"Step {i}: {error_msg}")
            
            if validation_errors:
                return {
                    validation_output: gr.update(value="❌ **Validation Errors**:\n" + "\n".join([f"- {error}" for error in validation_errors])),
                    test_preview: gr.update(value="")
                }
            
            # Parse expected outcomes
            outcome_list = [line.strip() for line in outcomes.split('\n') if line.strip()] if outcomes else []
            
            # Create test case
            test_case = TestCase(
                name=name,
                description=description,
                url=url,
                steps=steps,
                expected_outcomes=outcome_list
            )
            
            # Generate preview script
            preview_script = PlaywrightScriptGenerator.generate_script(test_case)
            
            # Store test case
            webui_manager.test_cases.append(test_case)
            
            # Update test selector
            test_choices = [(f"{tc.name} ({tc.status})", tc.id) for tc in webui_manager.test_cases]
            
            return {
                validation_output: gr.update(value=f"✅ **Test Case Created Successfully**\n- Name: {name}\n- Steps: {len(steps)}\n- Expected Outcomes: {len(outcome_list)}"),
                test_preview: gr.update(value=preview_script),
                test_selector: gr.update(choices=test_choices, value=test_case.id)
            }
            
        except Exception as e:
            logger.error(f"Error creating test case: {e}", exc_info=True)
            return {
                validation_output: gr.update(value=f"❌ **Error**: {str(e)}"),
                test_preview: gr.update(value="")
            }
    
    async def execute_test_case(test_id, components_dict):
        """Execute selected test case"""
        if not test_id:
            yield {
                test_status: gr.update(value="❌ No test case selected"),
            }
            return
        
        # Find test case
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case:
            yield {
                test_status: gr.update(value="❌ Test case not found"),
            }
            return
        
        # Execute test
        async for update in _execute_test_case(webui_manager, test_case, components_dict):
            yield update
    
    def download_script(test_id):
        """Download the generated Playwright script"""
        if not test_id:
            return None
        
        test_case = next((tc for tc in webui_manager.test_cases if tc.id == test_id), None)
        if not test_case or not test_case.playwright_script:
            return None
        
        # Save script to temporary file
        script_filename = f"{test_case.name.replace(' ', '_')}.spec.js"
        script_path = os.path.join("./tmp", script_filename)
        os.makedirs("./tmp", exist_ok=True)
        
        with open(script_path, 'w') as f:
            f.write(test_case.playwright_script)
        
        return script_path
    
    # Connect event handlers
    all_components = list(webui_manager.get_components())
    
    create_test_btn.click(
        fn=create_test_case,
        inputs=[test_name, test_description, test_url, nl_steps, json_steps, expected_outcomes],
        outputs=[validation_output, test_preview, test_selector]
    )
    
    async def execute_test_wrapper(test_id, components_dict):
        async for update in execute_test_case(test_id, components_dict):
            yield update
    
    execute_test_btn.click(
        fn=execute_test_wrapper,
        inputs=[test_selector, all_components],
        outputs=[test_status, test_output, playwright_script, test_report, execution_video]
    )
    
    download_script_btn.click(
        fn=download_script,
        inputs=[test_selector],
        outputs=[gr.File()]
    )