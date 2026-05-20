import json
import cv2
import torch
import numpy as np
from openai import OpenAI
from PIL import Image
from io import BytesIO
from pathlib import Path
import base64
import requests
import re
from typing import Optional, List, Tuple, Dict, Any
import time
import ast  # 用於解析單引號的字典字串

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
    #歷史訊息
    TEMP_INPUTS = []

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("STRING", {
                    "tooltip": "AuerGPT的模型名稱"
                }),
                "user": ("STRING", {
                    "tooltip": "AuerGPT的使用者帳號"
                }),
                "password": ("STRING", {
                    "password": True,
                    "tooltip": "AuerGPT的使用者密碼"
                }),
                "api_key": ("STRING", {
                    "password": True,
                    "tooltip": "請使用AuerGPT的api key"
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
                "ratio": (["自動", "正方形 - 1024x1024(1:1)", "橫式 - 1152x896(4:3)", "橫式 - 1216x832(3:2)", "橫式 - 1344x768(16:9)", "橫式 - 1536x640(21:9)", "直式 - 896x1152(3:4)", "直式 - 1216x832(2:3)", "直式 - 1344x768(9:16)", "直式 - 1536x640(9:21)"], {
                    "tooltip": "控制生成圖像的比例"
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

    def call_api(self, model, user, password, api_key, prompt, batch_size, seed, ratio, clean_history, image_1=None, image_2=None, image_3=None, image_4=None, image_5=None):
        
        client = OpenAI(base_url="https://auergpt.auer.com.tw/api", api_key=api_key)
        
        session = requests.Session()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        login_payload = {
            "user": user,
            "password": password
        }

        login_resp = session.post(
            "https://auergpt.auer.com.tw/api/v1/auths/ldap",
            json=login_payload
        )

        if login_resp.status_code != 200:
            raise Exception(f"登入失敗: {login_resp.text}")

        if ratio != "自動":
            prompt = f"{prompt}，使用{ratio}比例輸出圖像"

        parts = [{ "type": "text", "text": prompt }]

        # 依順序將所有圖像加入 parts
        for img in [image_1, image_2, image_3, image_4, image_5]:
            if img != None:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": tensor_to_b64(img)}
                })

        # 清空歷史訊息
        if clean_history:
            self.TEMP_INPUTS[:] = []

        self.TEMP_INPUTS.append({"role": "user", "content": parts})

        out_texts, out_tensors = [], []
        temp_content = ""

        for i in range(batch_size):
            current_seed = seed + i
            print(f"[Auer Banana] 執行批次 {i + 1} | 使用種子 {current_seed}")
            # payload = {
            #     "temperature": 1,
            #     "seed": current_seed,
            #     "top_p": 0.9,
            #     "model": "gemini_manifold_google_genai.gemini-3-pro-image-preview",
            #     "messages": self.TEMP_INPUTS,
            # }

            response = client.chat.completions.create(
                messages = self.TEMP_INPUTS,
                model = model,
                temperature = 1,
                max_tokens = 4096,
                top_p = 1,
            )
            
            # resp = post_with_retry(
            #     "https://auergpt.auer.com.tw/api/chat/completions",
            #     headers=headers,
            #     data=json.dumps(payload)
            # )

            gpt_response = response.choices[0].message.content

            print(f"[Auer Banana] 回傳：{response}")

            if response.status_code != 200:
                raise Exception(f"API Error {response.status_code}: {response.text}")

            choices = response.get("choices", [])

            all_image_urls = []
            all_texts = []

            # ==========================================
            # STEP 1：解析 markdown + 純文字
            # ==========================================
            for ch in choices:
                # 修正 1: 優先嘗試讀取 message (非串流)，如果沒有再試 delta (串流)
                msg_obj = ch.get("message") or ch.get("delta") or {}
                raw_content = msg_obj.get("content", "")

                match = re.search(r'!\[.*?\]\((.*?)\)', raw_content)
                if match:
                    # 組合完整 URL
                    img_url = f"https://auergpt.auer.com.tw{match.group(1)}"
                    all_image_urls.append(img_url)

                clean_text = raw_content
                try:
                    if "data: [DONE]" in raw_content or "{'choices':" in raw_content:
                        temp_str = raw_content.replace("data: [DONE]", "").strip()
                        inner_data = ast.literal_eval(temp_str)
                        clean_text = inner_data['choices'][0]['delta']['content']
                except Exception as e:
                    print(f"內層解析跳過: {e}")
                    pass

                # 移除圖片標籤，只留純文字
                text_only = re.sub(r'!\[[^\]]*\]\([^)]+\)', "", clean_text).strip()
                if text_only:
                    all_texts.append(text_only)

            # 批次只保留第一次文字
            if current_seed == seed and all_texts:
                temp_content = "\n".join(all_texts)

            # ==========================================
            # STEP 2：下載每張圖片 → base64 → tensor
            # ==========================================
            for img_url in all_image_urls:
                print(f"圖片路徑：{img_url}")
                img_resp = session.get(img_url)
                if "image" in img_resp.headers.get("Content-Type", ""):
                    b64_data = base64.b64encode(img_resp.content).decode("utf-8")
                    img_tensor = b64_to_tensor(b64_data)
                    out_tensors.append(img_tensor)
                else:
                    print(f"⚠ 無法下載圖片：{img_url}")


            # ==========================================
            # STEP 3：紀錄文字
            # ==========================================
            for t in all_texts:
                out_texts.append(t)
        
            if i < batch_size - 1:
                time.sleep(0.5)  # 每個請求之間等待 0.5 秒

        self.TEMP_INPUTS.append({"role": "assistant", "content": temp_content})
        print(f"總回傳圖像數量 {len(out_tensors)}")        
        
        # 組裝回傳結果
        final_text = "\n ========= \n".join(out_texts)
        batch = torch.stack(out_tensors, dim=0) if out_tensors else torch.zeros((1, 1024, 1024, 4))

        return (final_text, batch, )
