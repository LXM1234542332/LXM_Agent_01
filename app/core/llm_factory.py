"""LLM 工厂类

使用 LangChain ChatOpenAI 通过 OpenAI 兼容模式调用多个 LLM 提供商
支持的模型提供商（只需修改 base_url 和 api_key）：
- 阿里云 DashScope: https://dashscope.aliyuncs.com/compatible-mode/v1
- DeepSeek: https://api.deepseek.com/v1
- OpenAI: https://api.openai.com/v1
- Azure OpenAI: https://{resource}.openai.azure.com
- 其他兼容 OpenAI API 的服务
"""

from langchain_openai import ChatOpenAI
from app.config import config
from loguru import logger
import os


class LLMFactory:
    """LLM 工厂类 - 使用 OpenAI 兼容模式"""

    # 阿里云 DashScope OpenAI 兼容模式 URL
    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # DeepSeek OpenAI 兼容模式 URL
    DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

    @staticmethod
    def create_chat_model(
        model: str | None = None,
        temperature: float = 0.7,
        streaming: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
        provider: str = "dashscope",  # 新增参数：指定提供商
    ) -> ChatOpenAI:
        """
        创建聊天模型

        Args:
            model: 模型名称，如果为 None 则使用默认模型
            temperature: 温度参数
            streaming: 是否启用流式输出
            base_url: API 基础 URL，如果为 None 则根据 provider 选择
            api_key: API 密钥，如果为 None 则从环境变量读取
            provider: 提供商选择，支持 "dashscope" 或 "deepseek"
        """

        # 根据 provider 选择默认配置
        if provider == "deepseek":
            model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
            base_url = base_url or os.getenv("DEEPSEEK_API_BASE", LLMFactory.DEEPSEEK_BASE_URL)
            api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        else:  # 默认使用 dashscope
            model = model or config.dashscope_model
            base_url = base_url or LLMFactory.DASHSCOPE_BASE_URL
            api_key = api_key or config.dashscope_api_key

        extra_body = {}
        extra_body["stream"] = streaming

        # DeepSeek 需要禁用流式输出才能使用 response_format
        if provider == "deepseek" and streaming:
            streaming = False
            extra_body["stream"] = False

        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
            base_url=base_url,
            api_key=api_key,
            extra_body=extra_body if extra_body else None,
        )

        return llm

# 全局 LLM 工厂实例
llm_factory = LLMFactory()
