import os
from PIL import Image

class BatchImageSaver:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "save_dir": ("STRING", {"default": "./ComfyUI/output"}),
                "start_index": ("INT", {"default": 1, "min": 0}),
                "padding": ("INT", {"default": 4, "min": 0}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("圖集目錄",)
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "🐊自訂"

    def save_images(self, images, save_dir, start_index, padding):
        os.makedirs(save_dir, exist_ok=True)
        saved_paths = []

        for idx, img_tensor in enumerate(images):
            img = Image.fromarray((img_tensor.cpu().numpy() * 255).astype("uint8"))
            filename = f"{str(start_index + idx).zfill(padding)}.png"
            path = os.path.join(save_dir, filename)
            img.save(path)
            saved_paths.append(path)

        print(f"Saved {len(saved_paths)} images to {save_dir}")
        return (f"{save_dir}",)