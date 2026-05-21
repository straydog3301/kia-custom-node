import urllib.request
import csv
import urllib.parse
import json

class StoryboardReader:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "spreadsheet_id": ("STRING", {"multiline": False}),
                "sheet_name": ("STRING", {"multiline": False}),
                "skip_header": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "execution_trigger": ("STRING", {"forceInput": True, "default": ""}),
            }
        }

    # 🌟 關鍵改動：將角色的返回型態改為 "STRING"，讓 ComfyUI 把它當成普通批次字串運送
    RETURN_TYPES = ("STRING", "FLOAT", "STRING", "STRING", "STRING", "STRING", "STRING")
    
    RETURN_NAMES = (
        "鏡號", 
        "秒數", 
        "角色(JSON字串)", # 每一鏡會輸出如 '["西奧多", "艾戴爾"]' 的字串
        "場景", 
        "中文說明", 
        "seedance提詞", 
        "完整JSON"
    )
    
    OUTPUT_IS_LIST = (True, True, True, True, True, True, False)
    
    FUNCTION = "read_sheet_to_arrays"
    CATEGORY = "utils/GoogleSheets"

    def read_sheet_to_arrays(self, spreadsheet_id, sheet_name, skip_header, execution_trigger=""):
        encoded_sheet_name = urllib.parse.quote(sheet_name)
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req)
            lines = [l.decode('utf-8') for l in response.readlines()]
            reader = csv.reader(lines)
            data = list(reader)

            if not data:
                return ([], [], [], [], [], [], "[]")

            if skip_header and len(data) > 1:
                data = data[1:]

            col_id, col_sec, col_char, col_scene, col_desc, col_seedance = [], [], [], [], [], []
            json_data = []

            for row in data:
                row = row + [""] * (6 - len(row))

                # 秒數處理
                raw_sec = str(row[1]).replace('s', '').replace('S', '')
                try:
                    sec_float = float(raw_sec) if raw_sec.strip() else 0.0
                except ValueError:
                    sec_float = 0.0

                # 角色處理
                raw_char = str(row[2]).strip()
                if raw_char.startswith("'"):
                    raw_char = raw_char[1:]
                
                # 清洗 Google Sheets CSV 轉義的雙引號
                if raw_char.startswith('"') and raw_char.endswith('"'):
                    unescaped = raw_char[1:-1].replace('""', '"')
                else:
                    unescaped = raw_char.replace('""', '"')

                # 驗證是否為合法的 JSON 格式，如果不是就幫它包裝，確保它是一串標準的 JSON 陣列字串
                try:
                    parsed = json.loads(unescaped)
                    if isinstance(parsed, list):
                        char_str_to_send = json.dumps(parsed, ensure_ascii=False)
                    else:
                        char_str_to_send = json.dumps([str(parsed)], ensure_ascii=False)
                except:
                    if unescaped:
                        if ',' in unescaped:
                            char_str_to_send = json.dumps([c.strip() for c in unescaped.split(',')], ensure_ascii=False)
                        elif '，' in unescaped:
                            char_str_to_send = json.dumps([c.strip() for c in unescaped.split('，')], ensure_ascii=False)
                        else:
                            char_str_to_send = json.dumps([unescaped], ensure_ascii=False)
                    else:
                        char_str_to_send = "[]"

                col_id.append(row[0])
                col_sec.append(sec_float)
                col_char.append(char_str_to_send) # 🌟 壓入清洗完畢的 JSON 字串，例如 '["潔西卡"]'
                col_scene.append(row[3])
                col_desc.append(row[4])
                col_seedance.append(row[5])

                json_data.append({
                    "鏡號": row[0], "秒數": sec_float, "角色": json.loads(char_str_to_send),
                    "場景": row[3], "中文說明": row[4], "seedance提詞": row[5]
                })

            return (col_id, col_sec, col_char, col_scene, col_desc, col_seedance, json.dumps(json_data, ensure_ascii=False))

        except Exception as e:
            return ([], [], [], [], [], [], f'{{"error": "{str(e)}"}}')