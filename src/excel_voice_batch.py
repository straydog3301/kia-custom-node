import os
import re
import pandas as pd
import folder_paths
import soundfile as sf
import numpy as np
import torch

class ExcelBatchVoicePrompts:
    """
    讀取Excel文件並根據角色和情緒生成語音生成所需的批次列表。
    (包含防呆修正：確保回傳值永遠為列表)
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "excel_path": ("STRING", {"default": "D:/專案/故事.xlsx", "multiline": False}),
                "assets_root": ("STRING", {"default": "D:/專案/語音數據", "multiline": False}),
                "output_dir": ("STRING", {"default": "AI語音輸出", "multiline": False}),
                # --- 功能區 ---
                "process_all": ("BOOLEAN", {"default": True, "label_on": "處理全部", "label_off": "使用自訂範圍"}),
                "start_index": ("INT", {"default": 1, "min": 1, "max": 9999, "step": 1, "display": "number"}),
                "end_index": ("INT", {"default": 10, "min": 1, "max": 9999, "step": 1, "display": "number"}),
            },
            "optional": {
                "google_sheet_url": ("STRING", {"default": "", "multiline": False}),
            },
        }

    # 定義輸出的類型
    RETURN_TYPES = ("AUDIO", "STRING", "STRING")
    RETURN_NAMES = ("參考音頻", "儲存路徑", "台詞文本")
    OUTPUT_IS_LIST = (True, True, True)

    FUNCTION = "process_excel"
    CATEGORY = "🐊自訂"

    def process_excel(self, excel_path, assets_root, output_dir, process_all, start_index, end_index, google_sheet_url=""):
        # --- 1. 強制初始化輸出列表 (防止 NoneType 錯誤的核心) ---
        ref_audios = []
        save_paths = []
        text_prompts = []

        # 路徑清理
        excel_path = excel_path.replace('"', '').strip()
        assets_root = assets_root.replace('"', '').strip()
        output_dir = output_dir.replace('"', '').strip()
        google_sheet_url = google_sheet_url.strip()

        # --- 2. 讀取數據 ---
        try:
            if google_sheet_url:
                print(f"正在從 Google Sheet 讀取數據: {google_sheet_url}")
                match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", google_sheet_url)
                if not match:
                    raise ValueError("無效的 Google Sheet URL 格式")
                
                sheet_id = match.group(1)
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                df = pd.read_csv(csv_url)
            else:
                if not os.path.exists(excel_path):
                    raise FileNotFoundError(f"找不到 Excel 文件: {excel_path}")
                df = pd.read_excel(excel_path)
        except Exception as e:
            print(f"❌ 讀取數據發生錯誤: {e}")
            # 發生錯誤時回傳空列表，避免崩潰
            return ([], [], [])

        # 檢查必要欄位
        required_columns = ['ID', '角色名稱', '情緒', '台詞']
        for col in required_columns:
            if col not in df.columns:
                print(f"❌ Excel 缺少必要欄位: {col}")
                return ([], [], [])

        # --- 3. 處理範圍篩選邏輯 ---
        total_rows = len(df)
        print(f"📊 原始資料共 {total_rows} 筆")

        if not process_all:
            s_idx = max(0, start_index - 1) 
            e_idx = min(total_rows, end_index)

            if s_idx >= total_rows or s_idx >= e_idx:
                print(f"⚠️ 範圍設定無效或超出資料長度，將回傳空列表。")
                df = df.iloc[0:0] 
            else:
                df = df.iloc[s_idx:e_idx]
                print(f"✂️ 已裁切資料範圍: {start_index} ~ {end_index}")

        if df.empty:
            print("⚠️ 警告: 處理列表為空。")
            return ([], [], [])

        # --- 4. 遍歷數據 ---
        for index, row in df.iterrows():
            try:
                role = str(row['角色名稱']).strip()
                emotion = str(row['情緒']).strip()
                text = str(row['台詞']).strip()
                file_id = str(row['ID']).strip()

                # 邏輯 A: 參考語音路徑
                ref_path = os.path.join(assets_root, role, f"{emotion}.mp3")
                
                if not os.path.exists(ref_path):
                    ref_path_wav = os.path.join(assets_root, role, f"{emotion}.wav")
                    if os.path.exists(ref_path_wav):
                        ref_path = ref_path_wav
                    else:
                        print(f"⚠️ 找不到音檔跳過: {ref_path}")
                        continue

                # 讀取音訊
                data, sample_rate = sf.read(ref_path)
                waveform = torch.from_numpy(data).float()

                # 形狀處理 (Batch, Channels, Samples)
                if waveform.ndim == 1: 
                    waveform = waveform.unsqueeze(0) # (1, Samples)
                else:
                    waveform = waveform.permute(1, 0) # (Channels, Samples)
                
                waveform = waveform.unsqueeze(0) # (1, Channels, Samples)
                
                audio_data = {"waveform": waveform, "sample_rate": sample_rate}

                # 邏輯 B: 輸出路徑
                save_path = os.path.join(output_dir, f"{file_id}")

                ref_audios.append(audio_data)
                save_paths.append(save_path)
                text_prompts.append(text)

            except Exception as e:
                print(f"❌ 處理單行數據失敗 (ID: {row.get('ID', 'Unknown')}): {e}")
                continue

        print(f"✅ 批次處理完畢，共 {len(text_prompts)} 筆資料。")

        # --- 5. 最終防呆檢查 ---
        # 確保回傳的都不是 None
        if ref_audios is None: ref_audios = []
        if save_paths is None: save_paths = []
        if text_prompts is None: text_prompts = []

        return (ref_audios, save_paths, text_prompts)