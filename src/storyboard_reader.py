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
                "spreadsheet_id": ("STRING", {
                    "multiline": False,
                }),
                "sheet_name": ("STRING", {
                    "multiline": False,
                }),
                "skip_header": ("BOOLEAN", {
                    "default": True, # 預設開啟，跳過第一行的標題
                    "label_on": "Yes (略過標題)",
                    "label_off": "No (讀取標題)"
                }),
            },
        }

    # 1. 為了讓 ComfyUI 知道「角色」輸出的是陣列物件，將其型態指定為 "LIST" 或是通用 "JSON"
    # 這裡推薦使用 "JSON" 型態，因為 ComfyUI 的基礎字串類型不支援巢狀陣列，傳出 JSON 物件最為安全通用
    RETURN_TYPES = ("STRING", "FLOAT", "JSON", "STRING", "STRING", "STRING", "STRING", "STRING")
    
    # 2. 更新圓點標籤
    RETURN_NAMES = (
        "鏡號 (陣列)", 
        "秒數 (陣列)", 
        "角色 (巢狀陣列)", # 這裡會輸出如：[["西奧多", "艾戴爾"], [], ["潔西卡"]] 這樣的結構
        "場景 (陣列)", 
        "台詞 (陣列)", 
        "中文說明 (陣列)", 
        "seedance提詞 (陣列)", 
        "完整JSON字串"
    )
    
    # 3. 前 7 個依然宣告為 True (讓 ComfyUI 觸發 Batch 批次執行機制)
    OUTPUT_IS_LIST = (True, True, True, True, True, True, True, False)
    
    FUNCTION = "read_sheet_to_arrays"
    CATEGORY = "utils/GoogleSheets"

    def read_sheet_to_arrays(self, spreadsheet_id, sheet_name, skip_header):
        encoded_sheet_name = urllib.parse.quote(sheet_name)
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req)
            lines = [l.decode('utf-8') for l in response.readlines()]
            reader = csv.reader(lines)
            data = list(reader)

            if not data:
                return ([], [], [], [], [], [], [], "[]")

            if skip_header and len(data) > 1:
                data = data[1:]

            col_id, col_sec, col_char, col_scene, col_lines, col_desc, col_seedance = [], [], [], [], [], [], []
            json_data = []

            for row in data:
                # 安全補齊機制，確保至少有 7 個欄位
                row = row + [""] * (7 - len(row))

                # 處理秒數轉換
                raw_sec = str(row[1]).strip()
                raw_sec = raw_sec.replace('s', '').replace('S', '')
                try:
                    sec_float = float(raw_sec) if raw_sec else 0.0
                except ValueError:
                    sec_float = 0.0

                # 🌟 核心魔法：解析角色欄位
                raw_char = str(row[2]).strip()
                # 如果開頭是單引號（先前為了防轉型加的），先拔掉它
                if raw_char.startswith("'"):
                    raw_char = raw_char[1:]
                
                try:
                    # 嘗試將字串 '["西奧多", "艾戴爾"]' 還原成 Python 的 list 物件 []
                    char_list = json.loads(raw_char)
                    if not isinstance(char_list, list):
                        char_list = [str(char_list)] if raw_char else []
                except:
                    # 如果萬一試算表裡面填的不是標準 JSON 陣列（例如手動填了普通的 "西奧多"），則自動幫它包成陣列
                    char_list = [raw_char] if raw_char else []

                col_id.append(row[0])
                col_sec.append(sec_float)
                col_char.append(char_list)     # 🌟 存入真正的 list 物件
                col_scene.append(row[3])
                col_lines.append(row[4])
                col_desc.append(row[5])
                col_seedance.append(row[6])

                # 同時打包一份新版 JSON 格式備用
                json_data.append({
                    "鏡號": row[0], 
                    "秒數": sec_float, 
                    "角色": char_list, # 這裡也是標準陣列
                    "場景": row[3],
                    "台詞": row[4],
                    "中文說明": row[5],
                    "seedance提詞": row[6]
                })

            json_string = json.dumps(json_data, ensure_ascii=False)

            return (col_id, col_sec, col_char, col_scene, col_lines, col_desc, col_seedance, json_string)

        except Exception as e:
            print(f"[GoogleSheetArrayReader] 錯誤: {e}")
            return ([], [], [], [], [], [], [], f'{{"error": "{str(e)}"}}')