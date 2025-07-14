import json
import os

import gradio as gr
from gradio.components import Component
from typing import Any, Dict, Optional
from src.webui.webui_manager import WebuiManager
from src.utils import config
import logging
from functools import partial

logger = logging.getLogger(__name__)


def update_model_dropdown(llm_provider):
    """
    Update the model name dropdown with predefined models for the selected provider.
    """
    # Use predefined models for the selected provider
    if llm_provider in config.model_names:
        return gr.Dropdown(choices=config.model_names[llm_provider], value=config.model_names[llm_provider][0],
                           interactive=True)
    else:
        return gr.Dropdown(choices=[], value="", interactive=True, allow_custom_value=True)




def create_agent_settings_tab(webui_manager: WebuiManager):
    """
    Creates an agent settings tab with file-based persistence.
    """
    input_components = set(webui_manager.get_components())
    tab_components = {}
    
    # Settings persistence functions
    def save_agent_settings(provider, model, api_key, base_url, temperature, max_steps, max_actions, max_input_tokens, tool_calling_method):
        """Save settings to a JSON file"""
        settings = {
            'llm_provider': provider,
            'llm_model_name': model,
            'llm_api_key': api_key,
            'llm_base_url': base_url,
            'llm_temperature': temperature,
            'max_steps': max_steps,
            'max_actions': max_actions,
            'max_input_tokens': max_input_tokens,
            'tool_calling_method': tool_calling_method,
        }
        try:
            settings_file = os.path.join(os.path.expanduser('~'), '.webui_agent_settings.json')
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            return "✅ Settings saved successfully!"
        except Exception as e:
            return f"❌ Error saving settings: {e}"
    
    def load_agent_settings():
        """Load settings from JSON file"""
        try:
            settings_file = os.path.join(os.path.expanduser('~'), '.webui_agent_settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                return (
                    settings.get('llm_provider', 'openai'),
                    settings.get('llm_model_name', 'gpt-4o-mini'),
                    settings.get('llm_api_key', ''),
                    settings.get('llm_base_url', ''),
                    settings.get('llm_temperature', 0.6),
                    settings.get('max_steps', 10),
                    settings.get('max_actions', 10),
                    settings.get('max_input_tokens', 128000),
                    settings.get('tool_calling_method', 'auto'),
                    "✅ Settings loaded successfully!"
                )
            else:
                return ('openai', 'gpt-4o-mini', '', '', 0.6, 10, 10, 128000, 'auto', "ℹ️ No saved settings found")
        except Exception as e:
            return ('openai', 'gpt-4o-mini', '', '', 0.6, 10, 10, 128000, 'auto', f"❌ Error loading settings: {e}")
    
    def clear_agent_settings():
        """Clear saved settings"""
        try:
            settings_file = os.path.join(os.path.expanduser('~'), '.webui_agent_settings.json')
            if os.path.exists(settings_file):
                os.remove(settings_file)
                return ('openai', 'gpt-4o-mini', '', '', 0.6, 10, 10, 128000, 'auto', "✅ Settings cleared successfully!")
            else:
                return ('openai', 'gpt-4o-mini', '', '', 0.6, 10, 10, 128000, 'auto', "ℹ️ No settings file to clear")
        except Exception as e:
            return ('openai', 'gpt-4o-mini', '', '', 0.6, 10, 10, 128000, 'auto', f"❌ Error clearing settings: {e}")
    
    # Try to load initial settings
    initial_provider, initial_model, initial_key, initial_url, initial_temp, initial_max_steps, initial_max_actions, initial_max_input_tokens, initial_tool_calling_method, load_msg = load_agent_settings()


    with gr.Group():
        with gr.Row():
            llm_provider = gr.Dropdown(
                choices=[provider for provider, model in config.model_names.items()],
                label="LLM Provider",
                value=initial_provider,
                info="Select LLM provider for LLM",
                interactive=True,
                elem_id="llm_provider"
            )
            llm_model_name = gr.Dropdown(
                label="LLM Model Name",
                choices=config.model_names.get(initial_provider, config.model_names["openai"]),
                value=initial_model,
                interactive=True,
                allow_custom_value=True,
                info="Select a model in the dropdown options or directly type a custom model name",
                elem_id="llm_model_name"
            )
        with gr.Row():
            llm_temperature = gr.Slider(
                minimum=0.0,
                maximum=2.0,
                value=initial_temp,
                step=0.1,
                label="LLM Temperature",
                info="Controls randomness in model outputs",
                interactive=True,
                elem_id="llm_temperature"
            )
        with gr.Row():
            llm_base_url = gr.Textbox(
                label="Base URL",
                value=initial_url,
                info="API endpoint URL (if required)",
                elem_id="llm_base_url"
            )
            llm_api_key = gr.Textbox(
                label="API Key",
                type="password",
                value=initial_key,
                info="Your API key (required for LLM functionality)",
                elem_id="llm_api_key"
            )

        # Agent behavior controls
        with gr.Group():
            gr.Markdown("### 🤖 Agent Behavior")
            with gr.Row():
                max_steps = gr.Slider(
                    minimum=1,
                    maximum=50,
                    value=initial_max_steps,
                    step=1,
                    label="Max Steps",
                    info="Maximum number of agent steps to perform",
                    interactive=True
                )
                max_actions = gr.Slider(
                    minimum=1,
                    maximum=20,
                    value=initial_max_actions,
                    step=1,
                    label="Max Actions",
                    info="Maximum number of actions per step",
                    interactive=True
                )
            with gr.Row():
                max_input_tokens = gr.Slider(
                    minimum=100000,
                    maximum=200000,
                    value=initial_max_input_tokens,
                    step=1000,
                    label="Max Input Tokens",
                    info="Maximum input token limit for LLM",
                    interactive=True
                )
                tool_calling_method = gr.Dropdown(
                    choices=["auto", "direct", "function_calling"],
                    value=initial_tool_calling_method,
                    label="Tool Calling Method",
                    info="How the agent should call tools",
                    interactive=True
                )

    # Settings persistence controls (at bottom)
    with gr.Group():
        gr.Markdown("### 💾 Settings Persistence")
        gr.Markdown("*Save all agent settings above to persist across application restarts.*")
        with gr.Row():
            save_settings_btn = gr.Button("💾 Save Settings", variant="primary", size="lg")
            clear_settings_btn = gr.Button("🔄 Reset Settings", variant="secondary", size="lg")
        settings_status = gr.Textbox(
            label="Settings Status",
            value=load_msg,
            interactive=False,
            lines=1
        )

    tab_components.update(dict(
        llm_provider=llm_provider,
        llm_model_name=llm_model_name,
        llm_temperature=llm_temperature,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        max_steps=max_steps,
        max_actions=max_actions,
        max_input_tokens=max_input_tokens,
        tool_calling_method=tool_calling_method,
        save_settings_btn=save_settings_btn,
        clear_settings_btn=clear_settings_btn,
        settings_status=settings_status,
    ))
    webui_manager.add_components("agent_settings", tab_components)

    # Settings persistence event handlers
    save_settings_btn.click(
        fn=save_agent_settings,
        inputs=[llm_provider, llm_model_name, llm_api_key, llm_base_url, llm_temperature, max_steps, max_actions, max_input_tokens, tool_calling_method],
        outputs=[settings_status]
    )
    
    clear_settings_btn.click(
        fn=clear_agent_settings,
        outputs=[llm_provider, llm_model_name, llm_api_key, llm_base_url, llm_temperature, max_steps, max_actions, max_input_tokens, tool_calling_method, settings_status]
    )

    llm_provider.change(
        lambda provider: update_model_dropdown(provider),
        inputs=[llm_provider],
        outputs=[llm_model_name]
    )

