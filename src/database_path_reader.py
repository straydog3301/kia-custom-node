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
        scene_paths = []
        character_paths = []

        # 處理場景路徑
        if scenes:
            try:
                scene_list = json.loads(scenes) if isinstance(scenes, str) else scenes
                if isinstance(scene_list, list):
                    for scene in scene_list:
                        if scene and scene.strip():
                            path = os.path.join(database_root, "場景", str(scene).strip())
                            scene_paths.append(path)
                        else:
                            scene_paths.append("")
                else:
                    if scene_list and str(scene_list).strip():
                        path = os.path.join(database_root, "場景", str(scene_list).strip())
                        scene_paths.append(path)
                    else:
                        scene_paths.append("")
            except:
                if scenes.strip():
                    path = os.path.join(database_root, "場景", str(scenes).strip())
                    scene_paths.append(path)
                else:
                    scene_paths.append("")

        # 處理角色路徑
        if characters:
            try:
                char_list = json.loads(characters) if isinstance(characters, str) else characters
                if isinstance(char_list, list):
                    for char in char_list:
                        if char and char.strip():
                            path = os.path.join(database_root, "角色", str(char).strip())
                            character_paths.append(path)
                        else:
                            character_paths.append("")
                else:
                    if char_list and str(char_list).strip():
                        path = os.path.join(database_root, "角色", str(char_list).strip())
                        character_paths.append(path)
                    else:
                        character_paths.append("")
            except:
                if characters.strip():
                    path = os.path.join(database_root, "角色", str(characters).strip())
                    character_paths.append(path)
                else:
                    character_paths.append("")

        return (scene_paths, character_paths)
