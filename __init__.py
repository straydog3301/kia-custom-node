from .src.call_gpt_node import CallGPTNode
from .src.lora_prompt_tidy import LoraPromptTidyNode
from .src.batch_image_server import BatchImageSaver
from .src.excel_voice_batch import ExcelBatchVoicePrompts
from .src.storyboard_inputter import StoryboardInputter
from .src.storyboard_reader import StoryboardReader
from .src.call_nano_banana import AuerBananaNode
from .src.auer_image_gen import AuerImageGenNode


NODE_CLASS_MAPPINGS = {
    "CallGPTNode": CallGPTNode,
    "LoraPromptTidyNode": LoraPromptTidyNode,
    "BatchImageSaver": BatchImageSaver,
    "AuerBananaNode" : AuerBananaNode,
    "ExcelBatchVoicePrompts": ExcelBatchVoicePrompts,
    "StoryboardInputter": StoryboardInputter,
    "StoryboardReader": StoryboardReader,
    "AuerImageGenNode": AuerImageGenNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CallGPTNode": "呼叫GPT",
    "LoraPromptTidyNode": "角色Lora提詞整理",
    "BatchImageSaver": "圖像批次儲存",
    "AuerBananaNode": "AuerBanana",
    "ExcelBatchVoicePrompts": "Excel語音批次",
    "StoryboardInputter": "AI分鏡入表",
    "StoryboardReader": "AI分鏡讀表",
    "AuerImageGenNode": "AuerGPT 圖像生成",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', "WEB_DIRECTORY"]

WEB_DIRECTORY = "./web"