import os
import json

class DatabasePathReader:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "database_root": ("STRING", {"multiline": False}),
            },
            "optional": {
                "scenes": ("STRING", {"forceInput": True, "default": ""}),
                "characters": ("STRING", {"forceInput": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("場景路徑", "角色路徑")
    OUTPUT_IS_LIST = (True, True)
    
    FUNCTION = "build_paths"
    CATEGORY = "🐊自訂"

    def build_paths(self, database_root, scenes="", characters=""):
        # helper: 把一個 cell 解析成名稱列表（可能為空列表）
        def parse_cell(cell):
            if cell is None:
                return []
            # 已經是 list（可能來自 ComfyUI 的 list 輸入）
            if isinstance(cell, list):
                return [str(x).strip() for x in cell if x is not None and str(x).strip() != ""]
            # 字串情況
            if isinstance(cell, str):
                s = cell.strip()
                # 空或明確的空陣列表示無項目
                if s == "" or s == "[]":
                    return []
                # 嘗試解析 JSON（例如 '["A","B"]'）
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip() != ""]
                    else:
                        p = str(parsed).strip()
                        return [p] if p != "" else []
                except:
                    # 移除開頭的單引號（Google sheet 的情況）
                    if s.startswith("'"):
                        s = s[1:]
                    # 處理被雙引號包覆且內部有雙雙引號的情況
                    if s.startswith('"') and s.endswith('"'):
                        s = s[1:-1].replace('""', '"')
                    # 以逗號或全形逗號分割
                    if ',' in s or '，' in s:
                        parts = [p.strip() for p in s.replace('，', ',').split(',')]
                        return [p for p in parts if p != ""]
                    # 單一名稱
                    return [s] if s != "" else []
            # 其他型態轉字串
            p = str(cell).strip()
            return [p] if p != "" else []

        # helper: 保證 input 變成 list（每個元素對應一列）
        def to_list(inp):
            if isinstance(inp, list):
                return inp
            if isinstance(inp, str):
                return [inp]
            if inp is None:
                return []
            return [inp]

        scenes_in = to_list(scenes)
        chars_in = to_list(characters)

        # 讓兩邊長度一致（短的補空字串）以維持對齊
        max_len = max(len(scenes_in), len(chars_in))
        while len(scenes_in) < max_len:
            scenes_in.append("")
        while len(chars_in) < max_len:
            chars_in.append("")

        scene_paths = []
        character_paths = []

        for sc_cell, ch_cell in zip(scenes_in, chars_in):
            # 場景：若有多個名稱，回傳以 ", " 串接的多個絕對路徑；若無則為空字串
            sc_names = parse_cell(sc_cell)
            if sc_names:
                sc_paths = [os.path.join(database_root, "場景", name) for name in sc_names]
                scene_paths.append(", ".join(sc_paths))
            else:
                scene_paths.append("")

            # 角色：同上處理（支援 storyboard_role_parser 的 "A, B" 平面字串）
            ch_names = parse_cell(ch_cell)
            if ch_names:
                ch_paths = [os.path.join(database_root, "角色", name) for name in ch_names]
                character_paths.append(", ".join(ch_paths))
            else:
                character_paths.append("")

        return (scene_paths, character_paths)
