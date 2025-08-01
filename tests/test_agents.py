import pdb

from dotenv import load_dotenv

load_dotenv()
import sys

sys.path.append(".")
import asyncio
import os
import sys
from pprint import pprint

from browser_use import Agent
from browser_use.agent.views import AgentHistoryList

from src.utils import utils


async def test_browser_use_agent():
    from browser_use.browser.browser import Browser, BrowserConfig
    from browser_use.browser.context import (
        BrowserContextConfig
    )
    from browser_use.agent.service import Agent

    from src.browser.custom_browser import CustomBrowser
    from src.controller.custom_controller import CustomController
    from src.utils import llm_provider
    from src.agent.browser_use.browser_use_agent import BrowserUseAgent

    llm = llm_provider.get_llm_model(
        provider="openai",
        model_name="gpt-4o",
        temperature=0.8,
    )

    # llm = llm_provider.get_llm_model(
    #     provider="google",
    #     model_name="gemini-2.0-flash",
    #     temperature=0.6,
    #     api_key=os.getenv("GOOGLE_API_KEY", "")
    # )

    # llm = utils.get_llm_model(
    #     provider="deepseek",
    #     model_name="deepseek-reasoner",
    #     temperature=0.8
    # )

    # llm = utils.get_llm_model(
    #     provider="deepseek",
    #     model_name="deepseek-chat",
    #     temperature=0.8
    # )

    # llm = utils.get_llm_model(
    #     provider="ollama", model_name="qwen2.5:7b", temperature=0.5
    # )

    # llm = utils.get_llm_model(
    #     provider="ollama", model_name="deepseek-r1:14b", temperature=0.5
    # )

    window_w, window_h = 1280, 1100

    # llm = llm_provider.get_llm_model(
    #     provider="azure_openai",
    #     model_name="gpt-4o",
    #     temperature=0.5,
    #     base_url=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    #     api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
    # )

    mcp_server_config = {
        "mcpServers": {
            # "markitdown": {
            #     "command": "docker",
            #     "args": [
            #         "run",
            #         "--rm",
            #         "-i",
            #         "markitdown-mcp:latest"
            #     ]
            # },
            "desktop-commander": {
                "command": "npx",
                "args": [
                    "-y",
                    "@wonderwhy-er/desktop-commander"
                ]
            },
        }
    }
    controller = CustomController()
    await controller.setup_mcp_client(mcp_server_config)
    use_own_browser = True
    use_vision = True  # Set to False when using DeepSeek

    max_actions_per_step = 10
    browser = None
    browser_context = None

    try:
        extra_browser_args = []
        if use_own_browser:
            browser_binary_path = os.getenv("BROWSER_PATH", None)
            if browser_binary_path == "":
                browser_binary_path = None
            browser_user_data = os.getenv("BROWSER_USER_DATA", None)
            if browser_user_data:
                extra_browser_args += [f"--user-data-dir={browser_user_data}"]
        else:
            browser_binary_path = None
        browser = CustomBrowser(
            config=BrowserConfig(
                headless=False,
                browser_binary_path=browser_binary_path,
                extra_browser_args=extra_browser_args,
                new_context_config=BrowserContextConfig(
                    window_width=window_w,
                    window_height=window_h,
                )
            )
        )
        browser_context = await browser.new_context(
            config=BrowserContextConfig(
                trace_path=None,
                save_recording_path=None,
                save_downloads_path="./tmp/downloads",
                window_height=window_h,
                window_width=window_w,
            )
        )
        agent = BrowserUseAgent(
            # task="download pdf from https://arxiv.org/pdf/2311.16498 and rename this pdf to 'mcp-test.pdf'",
            task="give me nvidia stock price",
            llm=llm,
            browser=browser,
            browser_context=browser_context,
            controller=controller,
            use_vision=use_vision,
            max_actions_per_step=max_actions_per_step,
            generate_gif=True
        )
        history: AgentHistoryList = await agent.run(max_steps=100)

        print("Final Result:")
        pprint(history.final_result(), indent=4)

        print("\nErrors:")
        pprint(history.errors(), indent=4)

    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        if browser_context:
            await browser_context.close()
        if browser:
            await browser.close()
        if controller:
            await controller.close_mcp_client()


async def test_browser_use_parallel():
    from browser_use.browser.browser import Browser, BrowserConfig
    from browser_use.browser.context import (
        BrowserContextConfig,
    )
    from browser_use.agent.service import Agent

    from src.browser.custom_browser import CustomBrowser
    from src.controller.custom_controller import CustomController
    from src.utils import llm_provider
    from src.agent.browser_use.browser_use_agent import BrowserUseAgent

    # llm = utils.get_llm_model(
    #     provider="openai",
    #     model_name="gpt-4o",
    #     temperature=0.8,
    #     base_url=os.getenv("OPENAI_ENDPOINT", ""),
    #     api_key=os.getenv("OPENAI_API_KEY", ""),
    # )

    # llm = utils.get_llm_model(
    #     provider="google",
    #     model_name="gemini-2.0-flash",
    #     temperature=0.6,
    #     api_key=os.getenv("GOOGLE_API_KEY", "")
    # )

    # llm = utils.get_llm_model(
    #     provider="deepseek",
    #     model_name="deepseek-reasoner",
    #     temperature=0.8
    # )

    # llm = utils.get_llm_model(
    #     provider="deepseek",
    #     model_name="deepseek-chat",
    #     temperature=0.8
    # )

    # llm = utils.get_llm_model(
    #     provider="ollama", model_name="qwen2.5:7b", temperature=0.5
    # )

    # llm = utils.get_llm_model(
    #     provider="ollama", model_name="deepseek-r1:14b", temperature=0.5
    # )

    window_w, window_h = 1280, 1100

    llm = llm_provider.get_llm_model(
        provider="azure_openai",
        model_name="gpt-4o",
        temperature=0.5,
        base_url=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
    )

    mcp_server_config = {
        "mcpServers": {
            # "markitdown": {
            #     "command": "docker",
            #     "args": [
            #         "run",
            #         "--rm",
            #         "-i",
            #         "markitdown-mcp:latest"
            #     ]
            # },
            "desktop-commander": {
                "command": "npx",
                "args": [
                    "-y",
                    "@wonderwhy-er/desktop-commander"
                ]
            },
            # "filesystem": {
            #     "command": "npx",
            #     "args": [
            #         "-y",
            #         "@modelcontextprotocol/server-filesystem",
            #         "/Users/xxx/ai_workspace",
            #     ]
            # },
        }
    }
    controller = CustomController()
    await controller.setup_mcp_client(mcp_server_config)
    use_own_browser = True
    use_vision = True  # Set to False when using DeepSeek

    max_actions_per_step = 10
    browser = None
    browser_context = None

    try:
        extra_browser_args = []
        if use_own_browser:
            browser_binary_path = os.getenv("BROWSER_PATH", None)
            if browser_binary_path == "":
                browser_binary_path = None
            browser_user_data = os.getenv("BROWSER_USER_DATA", None)
            if browser_user_data:
                extra_browser_args += [f"--user-data-dir={browser_user_data}"]
        else:
            browser_binary_path = None
        browser = CustomBrowser(
            config=BrowserConfig(
                headless=False,
                browser_binary_path=browser_binary_path,
                extra_browser_args=extra_browser_args,
                new_context_config=BrowserContextConfig(
                    window_width=window_w,
                    window_height=window_h,
                )
            )
        )
        browser_context = await browser.new_context(
            config=BrowserContextConfig(
                trace_path=None,
                save_recording_path=None,
                save_downloads_path="./tmp/downloads",
                window_height=window_h,
                window_width=window_w,
                force_new_context=True
            )
        )
        agents = [
            BrowserUseAgent(task=task, llm=llm, browser=browser, controller=controller)
            for task in [
                'Search Google for weather in Tokyo',
                # 'Check Reddit front page title',
                # 'Find NASA image of the day',
                # 'Check top story on CNN',
                # 'Search latest SpaceX launch date',
                # 'Look up population of Paris',
                'Find current time in Sydney',
                'Check who won last Super Bowl',
                # 'Search trending topics on Twitter',
            ]
        ]

        history = await asyncio.gather(*[agent.run() for agent in agents])
        print("Final Result:")
        pprint(history.final_result(), indent=4)

        print("\nErrors:")
        pprint(history.errors(), indent=4)

        pdb.set_trace()

    except Exception:
        import traceback

        traceback.print_exc()
    finally:
        if browser_context:
            await browser_context.close()
        if browser:
            await browser.close()
        if controller:
            await controller.close_mcp_client()




if __name__ == "__main__":
    asyncio.run(test_browser_use_agent())
    # asyncio.run(test_browser_use_parallel())
