import requests
import json
import torch
import numpy as np
from PIL import Image, ImageDraw
from io import BytesIO
import base64


def tensor_to_png_bytes(img_tensor):
    """將 ComfyUI 的 Tensor 圖像轉換為 PNG bytes（用於上傳）"""
    i = 255. * img_tensor[0].cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def make_preview_image(input_tensors, prompt, dry_run):
    THUMB_SIZE = 256
    HEADER_H = 48
    BG_COLOR = (30, 30, 30)
    TEXT_COLOR = (255, 220, 50) if dry_run else (100, 220, 100)

    pil_imgs = []
    for t in input_tensors:
        i = 255. * t[0].cpu().numpy()
        pil = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8)).convert("RGB")
        pil.thumbnail((THUMB_SIZE, THUMB_SIZE))
        canvas = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), BG_COLOR)
        canvas.paste(pil, ((THUMB_SIZE - pil.width) // 2, (THUMB_SIZE - pil.height) // 2))
        pil_imgs.append(canvas)

    n = max(len(pil_imgs), 1)
    preview = Image.new("RGB", (THUMB_SIZE * n, THUMB_SIZE + HEADER_H), BG_COLOR)
    for idx, pil in enumerate(pil_imgs):
        preview.paste(pil, (idx * THUMB_SIZE, HEADER_H))

    draw = ImageDraw.Draw(preview)
    tag = "[DRY RUN] " if dry_run else ""
    short_prompt = prompt[:60] + ("…" if len(prompt) > 60 else "")
    draw.text((8, 8), f"{tag}{short_prompt}", fill=TEXT_COLOR)

    arr = np.array(preview).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None,]


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
                }),
                "password": ("STRING", {
                    "multiline": False,
                    "password": True,
                    "placeholder": "AuerGPT 密碼",
                }),
                "prompt": ("STRING", {
                    "multiline": True,
                    "placeholder": "生成提示詞",
                }),
                "dry_run": ("BOOLEAN", {
                    "default": False,
                    "label_on": "DRY RUN（不送封包）",
                    "label_off": "正常送出",
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

    RETURN_TYPES  = ("IMAGE",  "STRING",    "STRING",       "IMAGE")
    RETURN_NAMES  = ("image",  "image_url", "preview_text", "preview_image")
    FUNCTION      = "call_api"
    CATEGORY      = "🐊自訂"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return True

    def _build_preview_text(self, username, prompt, input_tensors, file_metas=None):
        lines = [
            "=== PREVIEW ===",
            f"Step 1  POST /api/v1/auths/ldap",
            f"        user: {username} / password: ********",
            "",
            f"Step 2  POST /api/v1/files/  (×{len(input_tensors)} 張)",
        ]
        for i, t in enumerate(input_tensors):
            h, w = t.shape[1], t.shape[2]
            fid = file_metas[i]["id"] if file_metas and i < len(file_metas) else "（尚未上傳）"
            lines.append(f"        [{i+1}] {w}×{h} px  file_id: {fid}")
        lines += [
            "",
            f"Step 3  POST /api/v1/images/generations",
            f"        prompt : {prompt}",
            f"        files  : {len(input_tensors)} 個 file_id",
        ]
        return "\n".join(lines)

    def call_api(self, username, password, prompt, dry_run=False,
                 image_1=None, image_2=None, image_3=None, image_4=None, image_5=None):

        input_tensors = [t for t in [image_1, image_2, image_3, image_4, image_5] if t is not None]
        preview_image = make_preview_image(input_tensors, prompt, dry_run)
        empty = torch.zeros((1, 512, 512, 3))

        if dry_run:
            preview_text = self._build_preview_text(username, prompt, input_tensors)
            print("🟡 AuerImageGen [DRY RUN] 跳過所有 HTTP 請求")
            print(preview_text)
            return (empty, "DRY RUN – 未送出請求", preview_text, preview_image)

        session = requests.Session()

        # Step 1: 登入
        try:
            login_resp = session.post(
                "https://auergpt.auer.com.tw/api/v1/auths/ldap",
                json={"user": username, "password": password},
                timeout=60
            )
            if login_resp.status_code != 200:
                raise Exception(f"登入失敗 ({login_resp.status_code}): {login_resp.text}")
            login_data = login_resp.json()
            token = login_data.get("token") or login_data.get("access_token")
            if not token:
                raise Exception("登入成功，但找不到 Token")
        except Exception as e:
            print(f"❌ 登入錯誤: {e}")
            preview_text = self._build_preview_text(username, prompt, input_tensors)
            return (empty, f"Login Error: {e}", preview_text, preview_image)

        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: 上傳參考圖，收集 file metadata
        file_metas = []
        for i, t in enumerate(input_tensors):
            try:
                png_bytes = tensor_to_png_bytes(t)
                up_resp = session.post(
                    "https://auergpt.auer.com.tw/api/v1/files/",
                    headers=headers,
                    files={"file": (f"reference_{i+1}.png", png_bytes, "image/png")},
                    timeout=60
                )
                if up_resp.status_code != 200:
                    raise Exception(f"上傳失敗 ({up_resp.status_code}): {up_resp.text}")
                file_data = up_resp.json()
                file_id = file_data.get("id")
                if not file_id:
                    raise Exception(f"找不到 file id: {file_data}")

                file_metas.append({
                    "type": "file",
                    "file": file_data,
                    "id":   file_id,
                    "url":  file_id,
                    "name": f"reference_{i+1}.png",
                    "status": "uploaded",
                    "size": len(png_bytes),
                    "error": "",
                    "content_type": "image/png"
                })
                print(f"✅ 圖片 {i+1} 上傳完成 file_id: {file_id}")

            except Exception as e:
                print(f"⚠️ 圖片 {i+1} 上傳失敗，略過: {e}")

        preview_text = self._build_preview_text(username, prompt, input_tensors, file_metas)

        # Step 3: 生圖
        try:
            payload = {
                "prompt": prompt,
                "files": file_metas
            }
            response = session.post(
                "https://auergpt.auer.com.tw/api/v1/images/generations",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=600
            )
            if response.status_code != 200:
                raise Exception(f"生圖失敗 ({response.status_code}): {response.text}")

            data = response.json()
            if not isinstance(data, list) or len(data) == 0:
                raise Exception(f"回傳格式不正確: {data}")

            img_rel_url = data[0].get("url")
            if not img_rel_url:
                raise Exception("找不到圖片 URL")

            full_img_url = "https://auergpt.auer.com.tw" + img_rel_url
            img_resp = session.get(full_img_url, timeout=60)
            img_resp.raise_for_status()

            img = Image.open(BytesIO(img_resp.content)).convert("RGB")
            img_np = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np)[None,]

            return (img_tensor, full_img_url, preview_text, preview_image)

        except Exception as e:
            print(f"❌ 生圖錯誤: {e}")
            return (empty, str(e), preview_text, preview_image)