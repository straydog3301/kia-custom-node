import os
import torch
import numpy as np
from PIL import Image
from pathlib import Path

class FolderImageStitcher:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "folder_path": ("STRING", {"multiline": False}),
                "max_dimension": ("INT", {"default": 2048, "min": 512, "max": 8192, "step": 256}),
                "stitch_direction": (["horizontal", "vertical"], {"default": "horizontal"}),
            },
            "optional": {
                "execution_trigger": ("STRING", {"forceInput": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("圖像", "圖像資訊")
    FUNCTION = "stitch_images"
    CATEGORY = "🐊自訂"

    def stitch_images(self, folder_path, max_dimension, stitch_direction, execution_trigger=""):
        # 驗證資料夾是否存在
        if not os.path.isdir(folder_path):
            raise ValueError(f"資料夾不存在: {folder_path}")

        # 支援的圖像格式
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff'}
        
        # 掃描資料夾中的所有圖像
        image_files = []
        for file in sorted(os.listdir(folder_path)):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in image_extensions:
                image_files.append(file_path)

        if not image_files:
            raise ValueError(f"資料夾中未找到圖像文件: {folder_path}")

        # 讀取所有圖像
        images = []
        for img_path in image_files:
            try:
                img = Image.open(img_path).convert('RGB')
                images.append(img)
            except Exception as e:
                print(f"無法讀取圖像 {img_path}: {str(e)}")
                continue

        if not images:
            raise ValueError(f"無法讀取任何圖像文件")

        # 拼接圖像
        if stitch_direction == "horizontal":
            stitched = self._stitch_horizontal(images)
        else:
            stitched = self._stitch_vertical(images)

        # 根據長邊自動縮小
        stitched = self._resize_by_max_dimension(stitched, max_dimension)

        # 轉換為 ComfyUI 格式 (torch.Tensor, 0-1 範圍, BHWC 格式)
        img_array = np.array(stitched).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_array)[None, ...]  # 添加 batch 維度

        # 生成圖像資訊
        info = f"圖像數量: {len(image_files)}, 拼接方向: {stitch_direction}, 最終尺寸: {stitched.width}x{stitched.height}"

        return (img_tensor, info)

    def _stitch_horizontal(self, images):
        """水平拼接圖像"""
        # 統一高度
        max_height = max(img.height for img in images)
        resized_images = [img.resize((int(img.width * max_height / img.height), max_height), Image.Resampling.LANCZOS) 
                         for img in images]
        
        # 計算總寬度
        total_width = sum(img.width for img in resized_images)
        
        # 建立新圖像
        stitched = Image.new('RGB', (total_width, max_height))
        
        # 拼接
        x_offset = 0
        for img in resized_images:
            stitched.paste(img, (x_offset, 0))
            x_offset += img.width
        
        return stitched

    def _stitch_vertical(self, images):
        """垂直拼接圖像"""
        # 統一寬度
        max_width = max(img.width for img in images)
        resized_images = [img.resize((max_width, int(img.height * max_width / img.width)), Image.Resampling.LANCZOS) 
                         for img in images]
        
        # 計算總高度
        total_height = sum(img.height for img in resized_images)
        
        # 建立新圖像
        stitched = Image.new('RGB', (max_width, total_height))
        
        # 拼接
        y_offset = 0
        for img in resized_images:
            stitched.paste(img, (0, y_offset))
            y_offset += img.height
        
        return stitched

    def _resize_by_max_dimension(self, image, max_dimension):
        """根據長邊自動縮小圖像"""
        width, height = image.size
        max_side = max(width, height)
        
        if max_side > max_dimension:
            scale = max_dimension / max_side
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return image
