from pathlib import Path
from openai import OpenAI
import json
import shutil

class LoraPromptTidyNode:
    SKIP_MIRROR_IMG_NAMES = {"007": "001", "008": "002", "009": "003", "010": "004", "011": "005", "012": "006", "017": "013", "018": "014", "019": "015", "020": "016"}

    EXTRA_PROMPT_MAP = {
        "001": "portrait", "002": "portrait", "007": "portrait", "008": "portrait",
        "003": "upper body", "009": "upper body",
        "004": "arms at sides, upper body", "010": "arms at sides, upper body",
        "005": "arms at sides, standing", "011": "arms at sides, standing",
        "006": "arms at sides, full body, standing", "012": "arms at sides, full body, standing",
        "013": "from side, profile, upper body", "014": "from side, profile, upper body",
        "017": "from side, profile, upper body", "018": "from side, profile, upper body",
        "015": "from side, profile, half body, standing", "019": "from side, profile, half body, standing",
        "016": "from side, profile, full body, standing", "020": "from side, profile, full body, standing",
        "021": "upper body, from behind, back", "022": "upper body, from behind, back",
        "023": "half body, from behind, back, standing",
        "024": "full body, from behind, back, standing"
    }

    # 暫存的訊息
    TEMP_INPUTS = []
    TEMP_RESULTS = {}
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ai_type": (["AuerGPT", "GitHub", "OpenAI"],),
                "model": (["gpt-4.1", "gpt-4.1-mini", "gpt-5", "gpt-5-mini", "chatgpt-4o-latest"],),
                "api_key": ("STRING", {"default": ""}),
                "trigger_word": ("STRING", {"default": ""}),
                "img_path": ("STRING", ),
                "img_base64": ("STRING", ),
                "system_msg": ("STRING", {"default": ""}),
                "prompt": ("STRING",),
                "history": ("INT", {"default": 5, "min": 1, "max": 25}),
                "skip_mirror": ("BOOLEAN", {"default": True}),
                "use_template": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("整理後的題詞",)
    FUNCTION = "generate_prompt"
    CATEGORY = "🐊自訂"

    def generate_prompt(self, ai_type, model, api_key, trigger_word, img_path, img_base64, system_msg, prompt, history, skip_mirror, use_template):
        img_path = Path(img_path)
        img_name = img_path.stem
        log_path = Path(img_path.parent / 'log.txt')
        template_path = Path(img_path.parent / 'template.json')

        if not template_path.exists(): # 使用預置範本
            script_dir = Path(__file__).parent
            default_template = script_dir / 'template.json'
            shutil.copy(default_template, template_path)
            print(f"已將預置範本複製到 {template_path}")
        
        if img_name in ["001"]: 
            self.TEMP_INPUTS = []
            self.TEMP_RESULTS = {}

        if not self.TEMP_INPUTS: # 首次執行紀錄指令和參數
            self.write_log(log_path, f"使用{ai_type} | {model} | 保留歷史：{history} | 略過鏡射圖：{skip_mirror} | 使用範本：{use_template} \n\n~~~\n{system_msg}\n~~~\n")

        if skip_mirror and img_name in self.SKIP_MIRROR_IMG_NAMES:
            content = self.SKIP_MIRROR_IMG_NAMES.get(img_name)
            print(f"[{img_name}] 同 [{content}]")
            self.write_log(log_path, f"[{img_name}] 同 [{content}]")
            return (self.TEMP_RESULTS[content], )
    
        endpoint = {
            "AuerGPT":  "https://auergpt.auer.com.tw/api",
            "OpenAI":   "https://api.openai.com/v1",
            "GitHub":   "https://models.github.ai/inference",
        }.get(ai_type, "https://auergpt.auer.com.tw/api")

        client = OpenAI(base_url=endpoint, api_key=api_key)

        extra = self.EXTRA_PROMPT_MAP.get(img_name, "")
        if extra:
            user_input = ", ".join(filter(None, [trigger_word, prompt, extra]))
        else:
            user_input = ", ".join(filter(None, [prompt]))

        system_msg = system_msg.format(trigger_word=trigger_word)

        _model = {
            "GitHub":   f"openai/{model}",
            "OpenAI":   model,
            "AuerGPT":  model,
        }.get(ai_type, model)

        img_data_url = "data:image/png;base64," + img_base64

        self.TEMP_INPUTS.append({
                        "role": "user",
                        "content": [
                            { "type": "text", "text": user_input },
                            { "type": "image_url", "image_url": {"url": img_data_url} }
                        ]
                    })
        
        _messages = [{"role": "system", "content": system_msg}]

        if use_template: # 加入範本到歷史訊息裡
            with open(template_path, 'r', encoding='utf-8') as f:
                _messages.extend(json.load(f))

        _messages.extend(self.TEMP_INPUTS)

        try:
            response = client.chat.completions.create(
                messages = _messages,
                temperature = 1,
                top_p = 1,
                model = _model
            )

            gpt_response = response.choices[0].message.content
            self.TEMP_RESULTS[img_name] = gpt_response
            self.TEMP_INPUTS.append({"role": "assistant", "content": gpt_response})
            self.TEMP_INPUTS = self.TEMP_INPUTS[-(history*2):] # 保留歷史訊息
            self.write_char_log(img_path.parent / 'char_log.txt', self.TEMP_INPUTS) # 輸出對話紀錄
            print(f"[{img_name}] {gpt_response}")
            self.write_log(log_path, f"[{img_name}] {gpt_response}")
            return (gpt_response,)

        except Exception as e:
            print(f"[{img_name}] Error: {e}")
            return ("",)

    def write_log(self, log_path, log_str):
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_str + '\n')
            
    def write_char_log(self, log_path, log_lst):
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(log_lst, ensure_ascii=False, indent=2))
