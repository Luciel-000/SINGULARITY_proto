import json
import os
from typing import Tuple

SAVE_DIR = "save_data"
DEFAULT_SLOT = "save_slot_1.json"


def ensure_save_dir():
    if not os.path.isdir(SAVE_DIR):
        os.makedirs(SAVE_DIR, exist_ok=True)


def _full_path(filepath: str) -> str:
    if os.path.isabs(filepath):
        return filepath
    return os.path.join(SAVE_DIR, filepath)


def save_game(
    player, filepath: str = DEFAULT_SLOT, world_data: dict | None = None
) -> bool:
    """プレイヤーのセーブデータを JSON に書き出す。成功時 True。"""
    try:
        ensure_save_dir()
        path = _full_path(filepath)
        data = {
            "version": "0.9.0",
            "player": player.to_save_dict(),
        }
        if isinstance(world_data, dict) and world_data:
            data["world"] = world_data
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_game(player, filepath: str = DEFAULT_SLOT, game=None) -> Tuple[bool, str]:
    """セーブデータを読み込み、player に反映する。

    戻り値: (成功フラグ, reason)
      - (True, "ok")
      - (False, "no_file")  ファイルが存在しない
      - (False, "error")    読み込み/復元に失敗
    """
    try:
        path = _full_path(filepath)
        if not os.path.isfile(path):
            return False, "no_file"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        player_data = data.get("player")
        if not player_data:
            return False, "error"
        player.load_from_save_dict(player_data)
        if game is not None and hasattr(game, "load_save_data"):
            try:
                game.load_save_data(data)
            except Exception:
                return False, "error"
        return True, "ok"
    except Exception:
        return False, "error"
