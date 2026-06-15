"""
============================================================
  core/action_log.py  ── プレイヤー行動ログクラス

  目的:
    - プレイヤーの戦闘・行動実績を記録する土台を提供
    - 将来的なジョブ解放条件や行動ログUIの基礎として使う

  機能:
    - 通常攻撃、スキル使用、観察、逃走、勝利、敗北、ジョブチェンジを記録
    - スキルが物理/魔法のどちらかを分類
    - 記録値をまとめて取得できる
============================================================
"""

from .skill_data import get_skill_element


class ActionLog:
    def __init__(self):
        self.normal_attack_count = 0
        self.skill_use_count = 0
        self.observe_count = 0
        self.magic_skill_count = 0
        self.physical_skill_count = 0
        self.escape_count = 0
        self.battle_win_count = 0
        self.battle_lose_count = 0
        self.job_change_count = 0

    def record_normal_attack(self) -> None:
        self.normal_attack_count += 1

    def record_skill_use(self, skill_id: str) -> None:
        self.skill_use_count += 1
        # observe はスキル使用の一種としてカウントしつつ、別途観察数も記録
        if skill_id == "observe":
            self.record_observe()
            return

        element = get_skill_element(skill_id)
        if element == "none":
            self.physical_skill_count += 1
        else:
            self.magic_skill_count += 1

    def record_observe(self) -> None:
        self.observe_count += 1

    def record_escape(self) -> None:
        self.escape_count += 1

    def record_battle_win(self) -> None:
        self.battle_win_count += 1

    def record_battle_lose(self) -> None:
        self.battle_lose_count += 1

    def record_job_change(self) -> None:
        self.job_change_count += 1

    def get_summary(self) -> dict[str, int]:
        return {
            "normal_attack_count": self.normal_attack_count,
            "skill_use_count": self.skill_use_count,
            "observe_count": self.observe_count,
            "physical_skill_count": self.physical_skill_count,
            "magic_skill_count": self.magic_skill_count,
            "escape_count": self.escape_count,
            "battle_win_count": self.battle_win_count,
            "battle_lose_count": self.battle_lose_count,
            "job_change_count": self.job_change_count,
        }

    def to_dict(self) -> dict:
        """保存用の辞書を返す。"""
        return self.get_summary()

    def load_from_dict(self, data: dict) -> None:
        """辞書からカウント値を復元する。存在しないキーは0にフォールバックする。"""
        if not isinstance(data, dict):
            return
        self.normal_attack_count = int(data.get("normal_attack_count", 0))
        self.skill_use_count = int(data.get("skill_use_count", 0))
        self.observe_count = int(data.get("observe_count", 0))
        self.physical_skill_count = int(data.get("physical_skill_count", 0))
        self.magic_skill_count = int(data.get("magic_skill_count", 0))
        self.escape_count = int(data.get("escape_count", 0))
        self.battle_win_count = int(data.get("battle_win_count", 0))
        self.battle_lose_count = int(data.get("battle_lose_count", 0))
        self.job_change_count = int(data.get("job_change_count", 0))
