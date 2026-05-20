import json
import cv2
import torch
import numpy as np
from PIL import Image
from io import BytesIO
from pathlib import Path
import base64
import requests
import re
from typing import Optional, List, Tuple, Dict, Any
import time

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

def b64_to_tensor(b64_str):
    nparr = np.frombuffer(base64.b64decode(b64_str), np.uint8)
    result = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    result = convert_color(result)
    result = result.astype(np.float32) / 255.0
    return torch.from_numpy(result)

def convert_color(image,):
    if len(image.shape) > 2 and image.shape[2] >= 4:
      return cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

def post_with_retry(*args, retries=3, wait=1, **kwargs):
    for attempt in range(retries):
        resp = requests.post(*args, **kwargs)
        if resp.status_code == 200:
            return resp
        time.sleep(wait)
    raise Exception(f"API Error {resp.status_code}: {resp.text}")

class AuerBananaNode:
    """
    使用AuerGPT的gemini-3-pro-image模型算圖或修圖
    """
    
    #歷史訊息
    TEMP_INPUTS = []
    # 緩存比例參照圖
    _RATIO_CACHE = {}

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "api_key": ("STRING", {
                    "password": True,
                    "multiline": False,
                    "tooltip": "🔐 請輸入AuerGPT的API金鑰（密碼模式隱藏，導出工作流時不會保存）"
                }),
                "prompt": ("STRING", {
                    "multiline": True,
                    "tooltip": "圖像生成的文字提示"
                }),
                "batch_size": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 4,
                    "display": "number",
                    "tooltip": "生成的圖像數量（1-4）"
                }),
                "seed": ("INT", {
                    "default": 42,
                    "min": 0,
                    "max": 2147483647,  # Max value for 32-bit signed integer
                    "control_after_generate": "randomize",
                    "tooltip": "用於生成的基礎種子。用於批次處理的順序種子（seed、seed+1、seed+2…）"
                }),
                "clean_history": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "是否清理歷史訊息（True時開啟一則新對話，False時繼續當前對話）"
                }),
            },
            "optional": {
                "image_1": ("IMAGE",),
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
                "image_4": ("IMAGE",),
                "image_5": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE",)
    RETURN_NAMES = ("text_out", "images_out",)
    FUNCTION = "call_api"
    CATEGORY = "🐊自訂"

    def _get_ratio_reference_image(self, ratio_key: str):
        """取得或緩存比例參照圖"""
        if ratio_key not in self._RATIO_CACHE:
            root = Path(__file__).parent
            ref_image = Image.open(root / f"ratio_refer/{ratio_key}.png")
            self._RATIO_CACHE[ratio_key] = tensor_to_b64(ref_image)
        return self._RATIO_CACHE[ratio_key]

    def _extract_images_from_response(self, content: str) -> Tuple[List[str], str]:
        """從回應中提取圖像 base64 和純文字"""
        matches = re.findall(r"data:image/[a-zA-Z]+;base64,([A-Za-z0-9+/=]+)", content)
        text_only = re.sub(r"!\[[^\]]*\]\(data:image/.+?;base64,[A-Za-z0-9+/=]+\)", "", content).strip()
        return matches, text_only

    @classmethod
    def IS_CHANGED(cls, **kwargs) -> bool:
        """檢測是否有實質改變（排除敏感字段）"""
        return True

    def get_sanitized_data(self):
        """返回不包含敏感信息的節點數據（用於導出）"""
        return {
            "sanitized": True,
            "warning": "API Key 已過濾，導出時不會保存敏感信息"
        }

    def call_api(self, api_key, prompt, batch_size, seed, clean_history, image_1=None, image_2=None, image_3=None, image_4=None, image_5=None):
        # 驗證 API key
        if not api_key or not isinstance(api_key, str) or len(api_key.strip()) == 0:
            raise ValueError("❌ API Key 不能為空，請提供有效的 AuerGPT API 金鑰")
        
        # 安全記錄 (只顯示前後各4位字符)
        api_key_display = api_key[:2] + "*" * (len(api_key) - 8) + api_key[-2:] if len(api_key) > 8 else "***"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        parts = [{ "type": "text", "text": prompt }]
        
        # 依順序將所有圖像加入 parts
        for img in [image_1, image_2, image_3, image_4, image_5]:
            if img is not None:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": tensor_to_b64(img)}
                })

        # 清空歷史訊息
        if clean_history:
            self.TEMP_INPUTS.clear()

        self.TEMP_INPUTS.append({"role": "user", "content": parts})

        out_texts, out_tensors = [], []
        temp_content = ""

        for i in range(batch_size):
            current_seed = seed + i
            print(f"[Auer Banana] 執行批次 {i + 1} | 使用種子 {current_seed}")
            payload = {
                "temperature": 1,
                "seed": current_seed,
                "top_p": 0.9,
                "model": "google_gemini.gemini-3-pro-image-preview",
                "messages": self.TEMP_INPUTS,
            }

            resp = post_with_retry("https://auergpt.auer.com.tw/api/chat/completions", headers=headers, data=json.dumps(payload))
            
            if resp.status_code != 200:
                raise Exception(f"API Error {resp.status_code}: {resp.text}")

            data = resp.json()

            for choice in data.get("choices", []):
                content = choice.get("message", {}).get("content", "")
                if current_seed == seed: # 批次生成時只保留第一次的訊息紀錄
                    temp_content = content

                # 提取圖像和文字
                matches, text_only = self._extract_images_from_response(content)
                
                if text_only:
                    out_texts.append(text_only)

                print(f"批次 {i + 1} 回傳 {text_only} | 圖像數量 {len(matches)}")  

                for b64 in matches:
                    img_tensor = b64_to_tensor(b64)
                    out_tensors.append(img_tensor)
  
            if i < batch_size - 1:
                time.sleep(0.5)  # 每個請求之間等待 0.5 秒

        self.TEMP_INPUTS.append({"role": "assistant", "content": temp_content})
        print(f"總回傳圖像數量 {len(out_tensors)}")        
        
        # 組裝回傳結果
        final_text = "\n========= \n".join(out_texts) if out_texts else ""
        batch = torch.stack(out_tensors, dim=0) if out_tensors else torch.zeros((1, 1024, 1024, 3))

        return (final_text, batch)
