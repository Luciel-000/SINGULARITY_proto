"""
============================================================
  core/skill_data.py  ── スキルデータ定義  [0.5 Step2 新規]

  担当:
    - スキルIDと内容を辞書で一元管理
    - どのジョブがどのスキルを使えるかのマッピング
    - スキル取得用のヘルパー関数
    - 不正IDでも落ちない安全な設計

  ── スキル辞書の構造 ─────────────────────────────────────
  SKILL_DATA["スキルID"] = {
      "name"    : 表示名（日本語）
      "element" : 属性ID（element_system.py の ELEMENT_IDS と一致させる）
      "power"   : ATK に掛ける倍率（0.0 = ダメージなし）
      "desc"    : 説明文
      "jobs"    : 使用可能なジョブIDのリスト
  }

  ── ジョブ別スキル早見表 ────────────────────────────────
    ノービス  : tackle（たいあたり）/ observe（観察）
    ファイター: slash（スラッシュ）/ earth_break（アースブレイク）
    メイジ   : fireball（ファイアボール）/ water_shot（ウォーターショット）

  ── 拡張方法 ────────────────────────────────────────────
    新しいスキルを追加するには:
      1. SKILL_DATA に新しいキーでエントリを追加する
      2. "jobs" に使用可能なジョブIDを書く
    それだけ！ 他のファイルは変更不要。

  ── 他ファイルとの依存関係 ──────────────────────────────
    - element_system.py の属性IDを使用（"fire" / "water" など）
    - job_data.py / player.py / battle.py からインポートされる予定
    - このファイル自身は他の core ファイルを import しない
      （循環 import を防ぐため）

  ── 使い方 ──────────────────────────────────────────────
    from core.skill_data import (
        get_skill, get_skill_name, get_skill_element,
        get_skill_power, get_skill_desc,
        get_skills_for_job, is_valid_skill,
    )

    skill = get_skill("fireball")          # 辞書をまるごと取得
    name  = get_skill_name("fireball")     # → "ファイアボール"
    elem  = get_skill_element("fireball")  # → "fire"
    power = get_skill_power("fireball")    # → 2.0
    desc  = get_skill_desc("fireball")     # → "炎の球を放つ"

    skills = get_skills_for_job("mage")    # → ["fireball", "water_shot"]

    is_valid_skill("fireball")             # → True
    is_valid_skill("unknown")              # → False
============================================================
"""


# ── スキルデータ辞書 ─────────────────────────────────────
#
# ★ 新しいスキルを追加するときは、ここに辞書エントリを追加するだけ！
# ★ 属性IDは element_system.py の ELEMENT_IDS に合わせること
#    （fire / water / wind / earth / light / dark / none）
#
SKILL_DATA: dict[str, dict] = {

    # ──────────────────────────────────────────────────
    #  ノービス専用スキル
    # ──────────────────────────────────────────────────

    "tackle": {
        "name"   : "たいあたり",
        "element": "none",    # 無属性：相性ボーナスなし
        "power"  : 1.2,       # ATK × 1.2 のダメージ
        "desc"   : "全身でぶつかる基本攻撃。",
        "jobs"   : ["novice"],
    },

    "observe": {
        "name"   : "観察",
        "element": "none",
        "power"  : 0.0,       # ダメージなし（情報取得スキル）
        "desc"   : "敵の情報を観察する。大賢者メッセージと連携予定。",
        "jobs"   : ["novice"],
    },

    # ──────────────────────────────────────────────────
    #  ファイター専用スキル
    # ──────────────────────────────────────────────────

    "slash": {
        "name"   : "スラッシュ",
        "element": "none",
        "power"  : 1.5,       # 通常攻撃の 1.5 倍
        "desc"   : "武器で鋭く斬りつける。",
        "jobs"   : ["fighter"],
    },

    "earth_break": {
        "name"   : "アースブレイク",
        "element": "earth",   # 土属性
        "power"  : 1.8,       # 火力は高いが属性相性で変動
        "desc"   : "大地の力を込めた一撃。",
        "jobs"   : ["fighter"],
    },

    # ──────────────────────────────────────────────────
    #  メイジ専用スキル
    # ──────────────────────────────────────────────────

    "fireball": {
        "name"   : "ファイアボール",
        "element": "fire",    # 火属性
        "power"  : 2.0,       # 高火力・属性有利なら最大 3.0 相当
        "desc"   : "炎の球を放つ。",
        "jobs"   : ["mage"],
    },

    "water_shot": {
        "name"   : "ウォーターショット",
        "element": "water",   # 水属性
        "power"  : 1.8,
        "desc"   : "水の弾を放つ。",
        "jobs"   : ["mage"],
    },

    # ──────────────────────────────────────────────────
    #  将来追加予定（コメントで設計を残しておく）
    # ──────────────────────────────────────────────────

    # "wind_blade": {
    #     "name"   : "ウィンドブレード",
    #     "element": "wind",
    #     "power"  : 1.6,
    #     "desc"   : "風の刃を飛ばす。",
    #     "jobs"   : ["mage", "wizard"],
    # },
    # "holy_light": {
    #     "name"   : "ホーリーライト",
    #     "element": "light",
    #     "power"  : 2.2,
    #     "desc"   : "神聖な光で相手を貫く。",
    #     "jobs"   : ["cleric", "bishop"],
    # },
    # "dark_pulse": {
    #     "name"   : "ダークパルス",
    #     "element": "dark",
    #     "power"  : 2.2,
    #     "desc"   : "闇の波動を放つ。",
    #     "jobs"   : ["mage", "sorcerer"],
    # },
}


# ── ジョブ別スキルマップ（高速検索用キャッシュ） ──────────
# SKILL_DATA から自動生成するので手動で編集する必要はない。
# 「このジョブが使えるスキルID一覧」をすぐに引けるようにする。
_JOB_SKILL_MAP: dict[str, list[str]] = {}
for _sid, _sdata in SKILL_DATA.items():
    for _jid in _sdata.get("jobs", []):
        _JOB_SKILL_MAP.setdefault(_jid, []).append(_sid)


# ── 存在しないスキルIDへのフォールバック用データ ──────────
_FALLBACK_SKILL: dict = {
    "name"   : "???",
    "element": "none",
    "power"  : 0.0,
    "desc"   : "不明なスキル。",
    "jobs"   : [],
}


# ── 公開関数 ─────────────────────────────────────────────

def is_valid_skill(skill_id: str) -> bool:
    """
    スキルIDが存在するか確認する。

    引数:
        skill_id : スキルID（"fireball" など）

    戻り値:
        True  : 存在する
        False : 存在しない

    使用例:
        is_valid_skill("fireball")  → True
        is_valid_skill("unknown")   → False
    """
    return skill_id in SKILL_DATA


def get_skill(skill_id: str) -> dict:
    """
    スキルIDからスキルデータ辞書を取得する。
    存在しないIDでもフォールバックを返すので落ちない。

    引数:
        skill_id : スキルID

    戻り値:
        dict : スキルデータ（keys: name, element, power, desc, jobs）

    使用例:
        skill = get_skill("fireball")
        print(skill["name"])   # → "ファイアボール"
    """
    return SKILL_DATA.get(skill_id, _FALLBACK_SKILL)


def get_skill_name(skill_id: str) -> str:
    """
    スキルIDから表示名（日本語）を返す。

    使用例:
        get_skill_name("fireball")     → "ファイアボール"
        get_skill_name("earth_break")  → "アースブレイク"
        get_skill_name("unknown")      → "???"
    """
    return get_skill(skill_id)["name"]


def get_skill_element(skill_id: str) -> str:
    """
    スキルIDから属性IDを返す。
    element_system.get_multiplier() に渡すために使う。

    使用例:
        get_skill_element("fireball")    → "fire"
        get_skill_element("tackle")      → "none"
        get_skill_element("unknown")     → "none"
    """
    return get_skill(skill_id)["element"]


def get_skill_power(skill_id: str) -> float:
    """
    スキルIDから ATK 倍率を返す。
    実ダメージは「player.atk × power × 属性相性」で計算する。

    使用例:
        get_skill_power("fireball")   → 2.0
        get_skill_power("tackle")     → 1.2
        get_skill_power("observe")    → 0.0  （ダメージなし）
        get_skill_power("unknown")    → 0.0
    """
    return get_skill(skill_id)["power"]


def get_skill_desc(skill_id: str) -> str:
    """
    スキルIDから説明文を返す。
    バトルUIやスキル選択メニューの表示に使う。

    使用例:
        get_skill_desc("fireball")  → "炎の球を放つ。"
        get_skill_desc("unknown")   → "不明なスキル。"
    """
    return get_skill(skill_id)["desc"]


def get_skills_for_job(job_id: str) -> list[str]:
    """
    ジョブIDから、そのジョブが使えるスキルIDのリストを返す。
    スキル選択メニューの一覧表示に使う。

    引数:
        job_id : ジョブID（"novice" / "fighter" / "mage" など）

    戻り値:
        list[str] : スキルIDのリスト。スキルがなければ []。

    使用例:
        get_skills_for_job("mage")     → ["fireball", "water_shot"]
        get_skills_for_job("fighter")  → ["slash", "earth_break"]
        get_skills_for_job("novice")   → ["tackle", "observe"]
        get_skills_for_job("unknown")  → []
    """
    return list(_JOB_SKILL_MAP.get(job_id, []))


def all_skill_ids() -> list[str]:
    """
    全スキルIDのリストを返す（デバッグ・UI一覧表示に使う）。
    """
    return list(SKILL_DATA.keys())
