"""
core/job_unlock.py

行動ログを見て、解放候補ジョブを判定するユーティリティ。
"""

from .job_data import JOB_DATA


def get_unlocked_jobs(action_log) -> list[str]:
    """ActionLog を見て、解放候補のジョブIDを返す。
    返すジョブは `JOB_DATA` に存在するものだけ。
    """
    unlocked: list[str] = []

    # 条件: 通常攻撃を 3 回以上 → fighter 候補
    if getattr(action_log, "normal_attack_count", 0) >= 3:
        if "fighter" in JOB_DATA:
            unlocked.append("fighter")

    # 条件: 魔法スキルを 3 回以上 → mage 候補
    if getattr(action_log, "magic_skill_count", 0) >= 3:
        if "mage" in JOB_DATA:
            unlocked.append("mage")

    # observe_count による候補は将来追加（analyst/observer 等）
    # 現時点で JOB_DATA に存在しないジョブIDは返さない

    return unlocked


def get_unlock_reasons(action_log) -> dict[str, str]:
    """解放候補ごとの理由テキストを返す。
    まだ候補がない場合は空辞書を返す。
    """
    reasons: dict[str, str] = {}
    if getattr(action_log, "normal_attack_count", 0) >= 3 and "fighter" in JOB_DATA:
        reasons["fighter"] = "通常攻撃を重ねた"
    if getattr(action_log, "magic_skill_count", 0) >= 3 and "mage" in JOB_DATA:
        reasons["mage"] = "魔法スキルを使い続けた"
    # observe による候補は将来追加予定
    return reasons
