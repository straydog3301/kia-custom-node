from openai import OpenAI
import os
import torch
import numpy as np
from PIL import Image
from io import BytesIO
import base64

def tensor_to_b64(img_tensor):
    if isinstance(img_tensor, Image.Image): # 已經是 PIL Image
        pil_image = img_tensor
    else:
        pil_image = Image.fromarray(np.clip(255. * img_tensor.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))
    buffered = BytesIO()
    pil_image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()
    base64_str = base64.b64encode(image_bytes).decode("utf-8")
    return "data:image/png;base64," + base64_str

class CallGPTNode:

    # 暫存的訊息
    TEMP_INPUTS = []

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "ai_type": (["AuerGPT", "GitHub", "Google"],),
                "model": (["gpt-4.1-mini", "gpt-5-mini", "gpt-5.2-chat-latest", "gemma-4-26b-a4b-it", "gemma-4-31b-it"],),
                "api_key": ("STRING", {
                    "password": True,
                    "tooltip": "🔐 API 金鑰"
                }),
                "system_msg": ("STRING", {"default": ""}),
                "user_input": ("STRING", {"help": "請描述您的問題。"}),
                "history": ("INT", {"default": 5, "min": 0, "max": 20}),
                "max_tokens": ("INT", {"default": 4096, "min": 512, "max": 8192}),
            },
            "optional": {
                "image_1": ("IMAGE",),
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
                "image_4": ("IMAGE",),
                "image_5": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("生成的回覆",)
    FUNCTION = "generate_prompt"
    CATEGORY = "🐊自訂"

    def generate_prompt(self, ai_type, model, api_key, system_msg, user_input, history, max_tokens, 
                        image_1=None, image_2=None, image_3=None, image_4=None, image_5=None):
        # 驗證 API key
        if not api_key or not isinstance(api_key, str) or len(api_key.strip()) == 0:
            raise ValueError("❌ API Key 不能為空")
    
        endpoint = {
            "AuerGPT":  "https://auergpt.auer.com.tw/api",
            "OpenAI":   "https://api.openai.com/v1",
            "GitHub":   "https://models.github.ai/inference",
            "Google":   "https://generativelanguage.googleapis.com/v1beta/openai"
        }.get(ai_type, "https://auergpt.auer.com.tw/api")

        client = OpenAI(base_url=endpoint, api_key=api_key)
        
        _model = {
            "GitHub":   f"openai/{model}",
            "OpenAI":   model,
            "AuerGPT":  model,
            "Google":  model,
        }.get(ai_type, model)

        # 使用者輸入
        _content = [{ "type": "text", "text": user_input }]

        # 處理多張影像輸入
        for img in [image_1, image_2, image_3, image_4, image_5]:
            if img is not None:
                _content.append({ "type": "image_url", "image_url": {"url": tensor_to_b64(img)} })

        self.TEMP_INPUTS.append({
                        "role": "user",
                        "content": _content
                    })

        if history > 0:
            self.TEMP_INPUTS = self.TEMP_INPUTS[-(history * 2 + 1):]
        else:
            self.TEMP_INPUTS = self.TEMP_INPUTS[-1:]

        _messages = [{"role": "system", "content": system_msg}] + self.TEMP_INPUTS

        try:
            response = client.chat.completions.create(
                messages = _messages,
                model = _model,
                max_tokens = max_tokens,
                top_p = 1,
            )

            print(f"{model}模型回傳：{response}")

            gpt_response = response.choices[0].message.content
            self.TEMP_INPUTS.append({"role": "assistant", "content": gpt_response})
            if history > 0:
                self.TEMP_INPUTS = self.TEMP_INPUTS[-(history * 2):]  # 保留歷史訊息
            else:
                self.TEMP_INPUTS = []
            return (gpt_response,)

        except Exception as e:
            print(f"Error: {e}")
            return ("",)