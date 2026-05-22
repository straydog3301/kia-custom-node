import requests
import json
import re
import urllib.parse

class StoryboardInputter:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "shot_data_input": ("STRING", {"forceInput": True, "multiline": True}),
                "spreadsheet_id": ("STRING", {"default": "請填入你的試算表ID"}),
                "sheet_name": ("STRING", {"default": "Sheet1"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "process_and_send"
    CATEGORY = "🐊自訂"

    def process_and_send(self, shot_data_input, spreadsheet_id, sheet_name):
        api_url = "https://script.google.com/macros/s/AKfycbyj_2VJQFCl2kMVIHmD39kxbtYA_PHR0409-kuk8ML3zIV1vHuLICxGZfqbgqbmRIoSKw/exec"
        
        # --- 步驟 1: 字串清洗與解析 ---
        cleaned_input = shot_data_input.strip()
        
        # 移除 LLM 偶爾會加上的 Markdown 語法標籤 (```json ... ```)
        if cleaned_input.startswith("```"):
            cleaned_input = re.sub(r'^```json\s*|```$', '', cleaned_input, flags=re.MULTILINE).strip()
        
        try:
            # 嘗試解析為 JSON 物件
            data_list = json.loads(cleaned_input)
            
            # 確保解析出來的是列表，如果只是單個物件則包成列表
            if isinstance(data_list, dict):
                data_list = [data_list]
                
        except Exception as e:
            return (f"JSON 解析失敗: {str(e)}\n輸入內容的前50字: {cleaned_input[:50]}",)

        # --- 步驟 2: 發送資料 ---
        success_count = 0
        error_msg = ""
        returned_gid = None
        
        for shot in data_list:
            # 檢查必要欄位是否存在（避免發送空資料）
            if not isinstance(shot, dict): continue
            
            payload = {
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "data": shot
            }
            
            try:
                headers = {'Content-Type': 'application/json'}
                response = requests.post(
                    api_url, 
                    data=json.dumps(payload), 
                    headers=headers, 
                    timeout=30  # 稍微提高 timeout 防止 Google 伺服器偶爾超時
                )
                
                # 嘗試解析回傳的 JSON 資料
                try:
                    res_json = response.json()
                    if res_json.get("status") == "Success":
                        success_count += 1
                        returned_gid = res_json.get("gid")
                    else:
                        error_msg = res_json.get("message", response.text)
                except:
                    # 相容性備案：如果回傳不是 JSON，則檢查原始文字
                    if "Success" in response.text:
                        success_count += 1
                    else:
                        error_msg = response.text

            except Exception as e:
                error_msg = str(e)

        if success_count > 0:
            base_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            # 如果有拿到 gid 就用 #gid 定位，否則用工作表名稱定位
            sheet_url = f"{base_url}#gid={returned_gid}" if returned_gid is not None else f"{base_url}?range={urllib.parse.quote(sheet_name)}!A1"
            status = f"✅ 成功寫入 {success_count} 筆分鏡到工作表: {sheet_name} [開啟試算表]({sheet_url})"
        else:
            status = f"❌ 寫入失敗。錯誤原因: {error_msg}"
            
        return (status, )