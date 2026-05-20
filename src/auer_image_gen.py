import requests
import json
import torch
import numpy as np
from PIL import Image
from io import BytesIO
import base64

def tensor_to_b64(img_tensor):
    """將 ComfyUI 的 Tensor 圖像轉換為 Base64 字串"""
    # ComfyUI Tensor 格式為 [B, H, W, C]，取第一張圖 [0]
    i = 255. * img_tensor[0].cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return "data:image/png;base64," + img_str

class AuerImageGenNode:
    """
    根據 Postman Collection 實作的 AuerGPT 圖像生成節點
    Endpoint: /api/v1/images/generations
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "username": ("STRING", {
                    "multiline": False,
                    "placeholder": "AuerGPT 帳號",
                    "help": "用於登入的帳號"
                }),
                "password": ("STRING", {
                    "multiline": False,
                    "password": True,
                    "placeholder": "AuerGPT 密碼",
                    "help": "用於登入的密碼"
                }),
                "prompt": ("STRING", {
                    "multiline": True, 
                    "placeholder": "生成提示詞",
                    "help": "圖像生成的文字提示"
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

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "image_url")
    FUNCTION = "call_api"
    CATEGORY = "🐊自訂"

    @classmethod
    def IS_CHANGED(cls, **kwargs) -> bool:
        # 強制節點在每次執行時重新評估，確保登入狀態與隨機性
        return True

    def call_api(self, username, password, prompt, image_1=None, image_2=None, image_3=None, image_4=None, image_5=None):
        session = requests.Session()
        
        # 1. 透過 LDAP 登入取得 JWT Token
        login_url = "https://auergpt.auer.com.tw/api/v1/auths/ldap"
        login_payload = {
            "user": username,
            "password": password
        }

        # 安全記錄：比照 AuerBananaNode 遮罩敏感資訊
        masked_user = username[:2] + "***" if len(username) > 2 else "***"
        masked_pwd = "*" * 8
        print(f"[AuerImageGen] 嘗試登入帳號: {masked_user} / 密碼: {masked_pwd}")
        
        try:
            login_resp = session.post(login_url, json=login_payload, timeout=15)
            if login_resp.status_code != 200:
                raise Exception(f"登入失敗 ({login_resp.status_code}): {login_resp.text}")
            
            login_data = login_resp.json()
            # 從回傳 JSON 中提取 token (優先尋找 token 或 access_token 欄位)
            token = login_data.get("token") or login_data.get("access_token")
            
            if not token:
                raise Exception("登入成功，但回傳資料中找不到有效的 Token")
                
        except Exception as e:
            print(f"❌ AuerImageGen 登入階段錯誤: {str(e)}")
            # 登入失敗時回傳黑色占位圖與錯誤訊息
            return (torch.zeros((1, 512, 512, 3)), f"Login Error: {str(e)}")

        # 2. 使用取得的 Token 發送生成請求
        gen_url = "https://auergpt.auer.com.tw/api/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 處理參考圖像
        ref_images = []
        for img in [image_1, image_2, image_3, image_4, image_5]:
            if img is not None:
                ref_images.append(tensor_to_b64(img))

        payload = {"prompt": prompt, "images": ref_images}

        try:
            # 將超時時間增加到 300 秒，給予伺服器足夠的時間生成圖像
            response = session.post(gen_url, headers=headers, json=payload, timeout=300)

            if response.status_code != 200:
                raise Exception(f"API 請求失敗 ({response.status_code}): {response.text}")

            data = response.json()
            
            # 2. 解析回傳資料 (預期為列表，取第一個元素)
            if not isinstance(data, list) or len(data) == 0:
                raise Exception("API 回傳資料格式不正確或列表為空")

            # 3. 取得圖片 URL 並拼接完整路徑
            img_rel_url = data[0].get("url")
            if not img_rel_url:
                raise Exception("找不到圖片 URL")
                
            base_url = "https://auergpt.auer.com.tw"
            full_img_url = base_url + img_rel_url
            # print(f"[AuerImageGen] 正在下載圖片: {full_img_url}")

            # 3. 下載並轉換圖片 (使用相同 session 以保留可能的 cookie)
            img_resp = session.get(full_img_url, timeout=60)
            img_resp.raise_for_status()
            
            img = Image.open(BytesIO(img_resp.content)).convert("RGB")
            
            # 轉換為 ComfyUI 要求的 Tensor 格式: [B, H, W, C], Float32, 0-1
            img_np = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np)[None,] # 增加 Batch 維度 [1, H, W, 3]

            return (img_tensor, full_img_url)

        except Exception as e:
            print(f"❌ AuerImageGen 發生錯誤: {str(e)}")
            # 發生錯誤時回傳一個空的黑色張量，避免 workflow 中斷
            empty_image = torch.zeros((1, 512, 512, 3))
            return (empty_image, str(e))