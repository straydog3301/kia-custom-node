import requests
import json
import torch
import numpy as np
from PIL import Image, ImageDraw
from io import BytesIO
import time
import re
import uuid


def tensor_to_png_bytes(img_tensor):
    """Tensor → PNG bytes（用於上傳）"""
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
    BASE_URL = "https://auergpt.auer.com.tw"

    # 類別變數：跨執行保留上一次的 chat_id 和 parent_id
    _last_chat_id   = None
    _last_parent_id = None

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "username":   ("STRING",  {"multiline": False, "placeholder": "AuerGPT 帳號"}),
                "password":   ("STRING",  {"multiline": False, "password": True, "placeholder": "AuerGPT 密碼"}),
                "prompt":     ("STRING",  {"multiline": True,  "placeholder": "生成提示詞"}),
                "reuse_chat": ("BOOLEAN", {"default": False,
                                           "label_on":  "續用同一聊天室",
                                           "label_off": "每次新開聊天室"}),
                "dry_run":    ("BOOLEAN", {"default": False,
                                           "label_on":  "DRY RUN（不送封包）",
                                           "label_off": "正常送出"}),
            },
            "optional": {
                "image_1": ("IMAGE",),
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
                "image_4": ("IMAGE",),
                "image_5": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE",  "STRING",    "STRING",       "IMAGE")
    RETURN_NAMES = ("image",  "image_url", "preview_text", "preview_image")
    FUNCTION     = "call_api"
    CATEGORY     = "🐊自訂"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return True

    # ── preview_text ───────────────────────────────────────────
    def _build_preview_text(self, username, prompt, input_tensors,
                            file_metas=None, chat_id=None, reuse_chat=False):
        chat_label = f"續用 {chat_id}" if (reuse_chat and chat_id) else "新建聊天室"
        lines = [
            "=== PREVIEW ===",
            f"Chat 模式 : {chat_label}",
            "",
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
            f"Step 3  POST /api/chat/completions",
            f"        model  : gpt-5",
            f"        feature: image_generation = true",
            f"        prompt : {prompt}",
            f"        files  : {len(input_tensors)} 個 file_id",
            "",
            "Step 4  GET /api/v1/chats/{chat_id}  (輪詢等待生圖完成)",
            "Step 5  GET /api/v1/files/{生成圖id}/content  (下載圖片)",
        ]
        return "\n".join(lines)

    # ── Step 1：登入 ───────────────────────────────────────────
    def _login(self, session, username, password):
        resp = session.post(
            f"{self.BASE_URL}/api/v1/auths/ldap",
            json={"user": username, "password": password},
            timeout=30
        )
        if resp.status_code != 200:
            raise Exception(f"登入失敗 ({resp.status_code}): {resp.text}")
        data  = resp.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            raise Exception("登入成功但找不到 Token")
        return token

    # ── Step 2：上傳單張圖片 ───────────────────────────────────
    def _upload_file(self, session, token, img_tensor, filename):
        png_bytes = tensor_to_png_bytes(img_tensor)
        resp = session.post(
            f"{self.BASE_URL}/api/v1/files/",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, png_bytes, "image/png")},
            timeout=60
        )
        if resp.status_code != 200:
            raise Exception(f"上傳失敗 ({resp.status_code}): {resp.text}")
        data    = resp.json()
        file_id = data.get("id")
        if not file_id:
            raise Exception(f"找不到 file_id: {data}")
        return file_id, len(png_bytes), data

    # ── 建立新聊天室 ───────────────────────────────────────────
    def _create_chat(self, session, token):
        resp = session.post(
            f"{self.BASE_URL}/api/v1/chats/new",
            headers={
                "Authorization":  f"Bearer {token}",
                "Content-Type":   "application/json"
            },
            json={"chat": {
                "id": "", "title": "", "models": ["gpt-5"],
                "messages": [],
                "history": {"messages": {}, "currentId": None},
                "tags": [],
                "timestamp": int(time.time() * 1000)
            }},
            timeout=15
        )
        if resp.status_code != 200:
            raise Exception(f"建立 chat 失敗 ({resp.status_code}): {resp.text}")
        chat_id = resp.json().get("id")
        if not chat_id:
            raise Exception("建立 chat 成功但找不到 id")
        return chat_id

    # ── Step 3：送出生圖請求 ───────────────────────────────────
    def _submit_generation(self, session, token, prompt, file_metas,
                           chat_id, parent_id):
        message_id = str(uuid.uuid4())

        payload = {
            "stream": True,
            "model":  "gpt-5",
            "params": {},
            "tool_servers": [],
            "features": {
                "voice":            False,
                "image_generation": True,
                "code_interpreter": False,
                "web_search":       False
            },
            "id":         str(uuid.uuid4()),
            "chat_id":    chat_id,
            "parent_id":  parent_id,
            "session_id": str(uuid.uuid4()),
            "background_tasks": {
                "follow_up_generation": False
            },
            "model_item": {
                "id":              "gpt-5",
                "object":          "model",
                "owned_by":        "openai",
                "connection_type": "external"
            },
            "variables": {},
            "user_message": {
                "id":       message_id,
                "parentId": parent_id,
                "role":     "user",
                "content":  prompt,
                "files":    file_metas,
                "models":   ["gpt-5"]
            }
        }

        resp = session.post(
            f"{self.BASE_URL}/api/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json"
            },
            json=payload,
            timeout=30
        )
        if resp.status_code != 200:
            raise Exception(f"生圖請求失敗 ({resp.status_code}): {resp.text}")

        data             = resp.json()
        chat_id_returned = data.get("chat_id", chat_id)
        print(f"📨 chat_id: {chat_id_returned}, task_ids: {data.get('task_ids')}")

        # 回傳 chat_id 和這次的 message_id（下次續用時當 parent_id）
        return chat_id_returned, message_id

    # ── Step 4：輪詢等待生圖完成 ──────────────────────────────
    def _poll_for_image_file_id(self, token, chat_id, user_message_id,
                            poll_interval=5, timeout=600):
        url      = f"{self.BASE_URL}/api/v1/chats/{chat_id}"
        headers  = {"Authorization": f"Bearer {token}"}
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                resp = requests.get(url, headers=headers, timeout=60)
                if resp.status_code != 200:
                    raise Exception(f"輪詢失敗 ({resp.status_code}): {resp.text}")

                messages = (resp.json()
                            .get("chat", {})
                            .get("history", {})
                            .get("messages", {}))

                # 只找 parentId == 這次 user_message_id 的 assistant 回覆
                for msg in messages.values():
                    if msg.get("role") != "assistant":
                        continue
                    if msg.get("parentId") != user_message_id:  # ← 關鍵過濾
                        continue

                    for f in msg.get("files", []):
                        if f.get("type") == "image" and f.get("url"):
                            match = re.search(
                                r"/api/v1/files/([^/]+)/content", f["url"])
                            if match:
                                return match.group(1)

                    content = msg.get("content", "")
                    if "/api/v1/files/" in content:
                        match = re.search(
                            r"/api/v1/files/([^/]+)/content", content)
                        if match:
                            return match.group(1)

            except requests.exceptions.Timeout:
                print("  ⏳ 輪詢 timeout，繼續等待...")
            except Exception as e:
                print(f"  ⚠️ 輪詢錯誤: {e}，繼續等待...")

            print("  ⏳ 等待生圖中...")
            time.sleep(poll_interval)

        raise Exception(f"生圖逾時（>{timeout}s），chat_id: {chat_id}")

    # ── Step 5：下載生成圖 ─────────────────────────────────────
    def _download_image(self, session, token, file_id):
        url  = f"{self.BASE_URL}/api/v1/files/{file_id}/content"
        resp = session.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60
        )
        resp.raise_for_status()
        img    = Image.open(BytesIO(resp.content)).convert("RGB")
        img_np = np.array(img).astype(np.float32) / 255.0
        return torch.from_numpy(img_np)[None,], url

    # ── 主入口 ─────────────────────────────────────────────────
    def call_api(self, username, password, prompt,
                 reuse_chat=False, dry_run=False,
                 image_1=None, image_2=None, image_3=None,
                 image_4=None, image_5=None):

        input_tensors = [t for t in [image_1, image_2, image_3, image_4, image_5]
                         if t is not None]
        preview_image = make_preview_image(input_tensors, prompt, dry_run)
        empty         = torch.zeros((1, 512, 512, 3))

        if dry_run:
            preview_text = self._build_preview_text(
                username, prompt, input_tensors,
                chat_id=AuerImageGenNode._last_chat_id,
                reuse_chat=reuse_chat
            )
            print("🟡 AuerImageGen [DRY RUN] 跳過所有 HTTP 請求")
            print(preview_text)
            return (empty, "DRY RUN – 未送出請求", preview_text, preview_image)

        session = requests.Session()
        try:
            # Step 1: 登入
            token = self._login(session, username, password)
            print("✅ 登入成功")

            # Step 2: 上傳所有參考圖
            file_metas = []
            for i, t in enumerate(input_tensors):
                fname = f"reference_{i+1}.png"
                file_id, size, file_data = self._upload_file(session, token, t, fname)
                file_metas.append({
                    "type":         "file",
                    "file":         file_data,
                    "id":           file_id,
                    "url":          file_id,
                    "name":         fname,
                    "status":       "uploaded",
                    "size":         size,
                    "error":        "",
                    "content_type": "image/png"
                })
                print(f"✅ 圖片 {i+1} 上傳完成 file_id: {file_id}")

            preview_text = self._build_preview_text(
                username, prompt, input_tensors, file_metas,
                chat_id=AuerImageGenNode._last_chat_id,
                reuse_chat=reuse_chat
            )

            # 決定 chat_id 和 parent_id
            if reuse_chat and AuerImageGenNode._last_chat_id:
                chat_id   = AuerImageGenNode._last_chat_id
                parent_id = AuerImageGenNode._last_parent_id or str(uuid.uuid4())
                print(f"♻️  續用聊天室 chat_id: {chat_id}")
            else:
                chat_id   = self._create_chat(session, token)
                parent_id = str(uuid.uuid4())
                print(f"✅ 新建聊天室 chat_id: {chat_id}")

            # Step 3: 送出生圖請求
            chat_id, new_message_id = self._submit_generation(
                session, token, prompt, file_metas, chat_id, parent_id)

            # 儲存供下次續用
            AuerImageGenNode._last_chat_id   = chat_id
            AuerImageGenNode._last_parent_id = new_message_id

            # Step 4: 輪詢等待生圖完成
            result_file_id = self._poll_for_image_file_id(token, chat_id, new_message_id)
            print(f"✅ 生圖完成 file_id: {result_file_id}")

            # Step 5: 下載生成圖
            img_tensor, img_url = self._download_image(session, token, result_file_id)
            print(f"✅ 圖片下載完成: {img_url}")

            return (img_tensor, img_url, preview_text, preview_image)

        except Exception as e:
            print(f"❌ AuerImageGen 錯誤: {str(e)}")
            preview_text = self._build_preview_text(
                username, prompt, input_tensors,
                chat_id=AuerImageGenNode._last_chat_id,
                reuse_chat=reuse_chat
            )
            return (empty, str(e), preview_text, preview_image)