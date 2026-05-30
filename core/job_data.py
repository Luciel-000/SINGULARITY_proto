"""
============================================================
  core/job_data.py  ── ジョブ（職業）データ定義  [0.5 更新]

  SINGULARITY のジョブシステムの「データ置き場」です。
  ロジック（計算処理）は player.py に書きます。
  このファイルには「数値と設定だけ」を書くルールにします。

  ── ジョブ辞書の構造 ────────────────────────────────────
  JOB_DATA["ジョブID"] = {
      "name"       : 表示名（日本語）
      "tier"       : 段階（1=初級, 2=中級, 3=上級）
      "sprite_key" : SpriteManager に渡すキー名
      "color"      : HUD表示カラー（RGB）
      "hp_bonus"   : 最大HPへの加算ボーナス
      "atk_bonus"  : 攻撃力への加算ボーナス
      "def_bonus"  : 防御力への加算ボーナス
      "lv_up_hp"   : レベルアップ時のHP上昇量
      "lv_up_atk"  : レベルアップ時の攻撃力上昇量
      "lv_up_def"  : レベルアップ時の防御力上昇量
      "evolves_to" : チェンジ先ジョブIDのリスト（[] なら上位なし）
      "desc"       : 説明文（UIで表示する）
      "element"    : ジョブの属性ID（element_system.py の ELEMENT_IDS と一致）★0.5追加
      "skills"     : 習得スキルIDのリスト（skill_data.py のキーと一致）★0.5追加
  }

  ── 拡張方法 ────────────────────────────────────────────
  新しいジョブを追加するには:
    1. JOB_DATA に新しいキーでエントリを追加する
    2. evolves_to に追加して進化先を設定する
    3. element にジョブ属性IDを設定する（"fire" / "earth" など）
    4. skills に使用できるスキルIDのリストを設定する
    5. assets/images/ に対応 PNG を置く
    6. sprite_manager.py の PLAYER_SPRITE_MAP に追記する
  それ以外のファイルは変更不要！

  ── 将来のジョブツリー構想（コメントで定義済み）────────
    ノービス(Lv1)
      ├─ ファイター(Lv5～) ──── ナイト / バーサーカー
      ├─ メイジ(Lv5～) ───── ウィザード / ソーサラー
      └─ （将来追加予定）
            アーチャー → レンジャー / ハンター
            クレリック → ビショップ / パラディン
============================================================
"""

# ── デフォルト（開始ジョブ）のID ────────────────────────
DEFAULT_JOB_ID = "novice"


# ── ジョブデータ辞書 ─────────────────────────────────────
#
# ★ 将来ジョブを増やすときはここに辞書エントリを追加するだけ！
#
JOB_DATA: dict[str, dict] = {

    # ──────────────────────────────────────────────────
    #  Tier 1 ── 初期ジョブ
    # ──────────────────────────────────────────────────
    "novice": {
        "name"      : "ノービス",
        "tier"      : 1,
        "sprite_key": "novice_m",          # SpriteManager のキー
        "color"     : (180, 170, 160),     # HUD表示色（グレー系）
        "hp_bonus"  : 0,                   # 基本ジョブなのでボーナスなし
        "atk_bonus" : 0,
        "def_bonus" : 0,
        "lv_up_hp"  : 8,                   # レベルアップ時の HP 上昇
        "lv_up_atk" : 3,                   # レベルアップ時の ATK 上昇
        "lv_up_def" : 1,                   # レベルアップ時の DEF 上昇
        "evolves_to": ["fighter", "mage"], # チェンジ可能な上位ジョブ
        "desc"      : "すべての始まり。可能性を秘めた魂。",
        "element"   : "none",              # ★ 0.5: ジョブ属性（無属性）
        "skills"    : ["tackle", "observe"],  # ★ 0.5: 習得スキル
    },

    # ──────────────────────────────────────────────────
    #  Tier 2 ── 中級ジョブ（物理系）
    # ──────────────────────────────────────────────────
    "fighter": {
        "name"      : "ファイター",
        "tier"      : 2,
        "sprite_key": "fighter_m",         # assets/images/player_fighter_m.png
        "color"     : (220, 100,  60),     # 橙赤（力強い色）
        "hp_bonus"  : 20,                  # HP が多め
        "atk_bonus" : 5,                   # 攻撃力が高い
        "def_bonus" : 2,
        "lv_up_hp"  : 12,                  # レベルアップ伸び率も高い
        "lv_up_atk" : 5,
        "lv_up_def" : 2,
        "evolves_to": [],                  # 0.4 では上位未実装（将来: knight / berserker）
        "desc"      : "剣と体で道を切り開く戦士。HP・ATKに優れる。",
        "element"   : "earth",             # ★ 0.5: ジョブ属性（土）
        "skills"    : ["slash", "earth_break"],  # ★ 0.5: 習得スキル
    },

    # ──────────────────────────────────────────────────
    #  Tier 2 ── 中級ジョブ（魔法系）
    # ──────────────────────────────────────────────────
    "mage": {
        "name"      : "メイジ",
        "tier"      : 2,
        "sprite_key": "mage_m",            # assets/images/player_mage_m.png
        "color"     : ( 90, 140, 220),     # 青紫（魔法の色）
        "hp_bonus"  : -5,                  # HPは低め（ガラスキャノン）
        "atk_bonus" : 8,                   # 攻撃力が非常に高い
        "def_bonus" : -1,
        "lv_up_hp"  : 5,
        "lv_up_atk" : 6,                   # ATK伸び率が最高
        "lv_up_def" : 0,
        "desc"      : "魔力を武器にする魔法使い。ATKが突出するが脆い。",
        "evolves_to": [],                  # 将来: wizard / sorcerer
        "element"   : "fire",             # ★ 0.5: ジョブ属性（火）
        "skills"    : ["fireball", "water_shot"],  # ★ 0.5: 習得スキル
    },

    # ──────────────────────────────────────────────────
    #  以下は将来実装予定（コメントで設計を残しておく）
    # ──────────────────────────────────────────────────

    # "knight": {
    #     "name"      : "ナイト",
    #     "tier"      : 3,
    #     "sprite_key": "knight_m",
    #     "color"     : (180, 160, 100),
    #     "hp_bonus"  : 40,
    #     "atk_bonus" : 8,
    #     "def_bonus" : 10,
    #     "lv_up_hp"  : 15,
    #     "lv_up_atk" : 4,
    #     "lv_up_def" : 4,
    #     "evolves_to": [],
    #     "desc"      : "鋼鉄の守護者。防御と HP が群を抜く。",
    # },

    # "wizard": {
    #     "name"      : "ウィザード",
    #     "tier"      : 3,
    #     "sprite_key": "wizard_m",
    #     "color"     : ( 60,  80, 200),
    #     "hp_bonus"  : -10,
    #     "atk_bonus" : 18,
    #     "def_bonus" : -2,
    #     "lv_up_hp"  : 4,
    #     "lv_up_atk" : 8,
    #     "lv_up_def" : 0,
    #     "evolves_to": [],
    #     "desc"      : "魔力の頂点。凄まじい威力で敵を灰にする。",
    # },
}


# ── ヘルパー関数 ─────────────────────────────────────────

def get_job(job_id: str) -> dict:
    """
    ジョブIDからデータを取得する。
    存在しないIDが渡されたとき「novice」にフォールバックする。

    使用例:
        job = get_job("fighter")
        print(job["name"])   # → "ファイター"
    """
    return JOB_DATA.get(job_id, JOB_DATA[DEFAULT_JOB_ID])


def get_evolutions(job_id: str) -> list[str]:
    """
    指定ジョブからチェンジできるジョブIDのリストを返す。
    チェンジ先がなければ空リスト []。

    使用例:
        get_evolutions("novice")   # → ["fighter", "mage"]
        get_evolutions("fighter")  # → []
    """
    return get_job(job_id).get("evolves_to", [])


def all_job_ids() -> list[str]:
    """
    全ジョブIDのリストを返す（デバッグやUIに使う）。
    """
    return list(JOB_DATA.keys())
