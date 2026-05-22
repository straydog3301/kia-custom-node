import json

class StoryboardRoleParser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "role_input": ("STRING", {"multiline": False}),
                "input_mode": (["role_json", "full_json"], {"default": "role_json"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("角色列表(JSON字串)", "角色扁平字串")
    OUTPUT_IS_LIST = (True, False)
    FUNCTION = "parse_role_data"
    CATEGORY = "🐊自訂"

    def parse_role_data(self, role_input, input_mode="role_json"):
        role_items = []

        if input_mode == "full_json":
            try:
                rows = json.loads(role_input) if isinstance(role_input, str) else role_input
            except:
                rows = []

            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        role_items.append(row.get("角色", "[]"))
                    else:
                        role_items.append("[]")
        else:
            if isinstance(role_input, list):
                role_items = role_input
            else:
                role_items = [role_input]

        parsed = []
        flat_lines = []

        for item in role_items:
            try:
                roles = json.loads(item) if isinstance(item, str) and item else item
            except:
                roles = []

            if not isinstance(roles, list):
                roles = [roles] if roles != "" else []

            clean = [str(r) for r in roles]
            parsed.append(json.dumps(clean, ensure_ascii=False))
            flat_lines.append(", ".join(clean))

        return parsed, "\n".join(flat_lines)