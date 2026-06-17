"""
============================================================
  core/element_system.py  ── 属性システム  [0.5 Step1 新規]

  担当:
    - 7属性（fire/water/wind/earth/light/dark/none）の定義
    - 属性の日本語名・カラー管理
    - 属性相性テーブル（有利:1.5 / 通常:1.0 / 不利:0.75）
    - get_multiplier()  : 攻撃属性×防御属性 → ダメージ倍率
    - get_element_name(): 属性ID → 日本語名

  ── 属性相性の考え方 ─────────────────────────────────────
    攻撃側の属性が、防御側の属性に「有利」なら 1.5 倍
    攻撃側の属性が、防御側の属性に「不利」なら 0.75 倍
    それ以外（通常・無属性絡み）は 1.0 倍

  ── 相性テーブル ─────────────────────────────────────────
    fire   → wind  有利    water → fire  有利    wind  → earth 有利
    earth  → water 有利    light → dark  有利    dark  → light 有利
    （逆は不利）

    none は常に 1.0 倍（相性なし）

  ── 将来の調整方法 ──────────────────────────────────────
    倍率を変えたいときは ADVANTAGE_RATE / DISADVANTAGE_RATE を変更するだけ。
    相性を追加したいときは ELEMENT_CHART に行を追加するだけ。
    他のファイルは変更不要。

  ── 使い方 ──────────────────────────────────────────────
    from core.element_system import get_multiplier, get_element_name
    from core.element_system import ELEMENT_COLOR, ELEMENT_IDS

    mult = get_multiplier("fire", "wind")   # → 1.5
    mult = get_multiplier("water", "fire")  # → 1.5
    mult = get_multiplier("fire", "fire")   # → 1.0
    mult = get_multiplier("none", "fire")   # → 1.0

    name = get_element_name("fire")         # → "火"
    col  = ELEMENT_COLOR["fire"]            # → (220, 70, 30)
============================================================
"""


# ── 有効な属性IDの一覧 ────────────────────────────────────
# ★ 新しい属性を追加するときはここに追記する
ELEMENT_IDS: list[str] = [
    "fire",    # 火
    "water",   # 水
    "wind",    # 風
    "earth",   # 土
    "light",   # 光
    "dark",    # 闇
    "none",    # 無（属性なし）
]

# ── 属性の日本語名 ────────────────────────────────────────
ELEMENT_NAME: dict[str, str] = {
    "fire"  : "火",
    "water" : "水",
    "wind"  : "風",
    "earth" : "土",
    "light" : "光",
    "dark"  : "闇",
    "none"  : "無",
}

# ── 属性ごとの表示カラー（RGB） ───────────────────────────
# HUD・バトル画面・スキル名の色分けに使う
ELEMENT_COLOR: dict[str, tuple[int, int, int]] = {
    "fire"  : (220,  70,  30),   # 赤橙
    "water" : ( 50, 130, 220),   # 青
    "wind"  : ( 60, 180,  80),   # 緑
    "earth" : (140,  95,  50),   # 茶
    "light" : (230, 220, 140),   # 金白
    "dark"  : ( 90,  50, 140),   # 紫黒
    "none"  : (160, 155, 145),   # グレー
}

# ── ダメージ倍率の定数 ────────────────────────────────────
# ★ 将来バランス調整するときはここだけ変える
ADVANTAGE_RATE    = 1.5    # 有利属性のダメージ倍率
DISADVANTAGE_RATE = 0.75   # 不利属性のダメージ倍率
NEUTRAL_RATE      = 1.0    # 通常（相性なし）のダメージ倍率

# ── 属性相性テーブル ──────────────────────────────────────
# ELEMENT_CHART[(攻撃属性, 防御属性)] = 倍率
#
# 有利な組み合わせだけ登録する。
# 「有利の逆は不利」はコードで自動計算するので、ここには書かない。
# none が絡む相性は登録しない（常に NEUTRAL_RATE）。
#
# ── 一方向の有利ペア ────────────────────────────────────
# 「A→Bが有利」を書くと「B→Aは不利」が自動登録される。
# ★ 新しい一方向相性を追加するときはここに1行追記するだけ
_ADVANTAGE_PAIRS: list[tuple[str, str]] = [
    ("fire",  "wind"),    # 火 → 風：有利 / 風 → 火：不利
    ("water", "fire"),    # 水 → 火：有利 / 火 → 水：不利
    ("wind",  "earth"),   # 風 → 土：有利 / 土 → 風：不利
    ("earth", "water"),   # 土 → 水：有利 / 水 → 土：不利
]

# ── 相互有利ペア（両方向とも有利になる特殊相性） ────────
# 光と闇は互いに弱点であり強み。どちらから攻撃しても有利。
# ★ 相互有利を追加するときはここに1行追記するだけ
_MUTUAL_ADVANTAGE_PAIRS: list[tuple[str, str]] = [
    ("light", "dark"),    # 光 → 闇：有利  かつ  闇 → 光：有利
]

# 上記2つのリストから倍率テーブルを自動生成（手書きミスを防ぐ）
ELEMENT_CHART: dict[tuple[str, str], float] = {}

# 一方向有利の登録（逆は不利）
for _atk, _def in _ADVANTAGE_PAIRS:
    ELEMENT_CHART[(_atk, _def)] = ADVANTAGE_RATE      # 有利
    ELEMENT_CHART[(_def, _atk)] = DISADVANTAGE_RATE   # 不利（逆を自動登録）

# 相互有利の登録（両方向とも有利）
for _a, _b in _MUTUAL_ADVANTAGE_PAIRS:
    ELEMENT_CHART[(_a, _b)] = ADVANTAGE_RATE           # A→B：有利
    ELEMENT_CHART[(_b, _a)] = ADVANTAGE_RATE           # B→A：有利（上書きしない）


# ── 公開関数 ─────────────────────────────────────────────

def get_multiplier(atk_element: str, def_element: str) -> float:
    """
    攻撃側の属性と防御側の属性から、ダメージ倍率を返す。

    引数:
        atk_element : 攻撃側の属性ID（"fire" / "water" / … / "none"）
        def_element : 防御側の属性ID

    戻り値:
        float  1.5（有利） / 1.0（通常） / 0.75（不利）

    使用例:
        get_multiplier("fire",  "wind")   → 1.5   火は風に有利
        get_multiplier("water", "fire")   → 1.5   水は火に有利
        get_multiplier("wind",  "fire")   → 0.75  風は火に不利
        get_multiplier("fire",  "fire")   → 1.0   同属性は通常
        get_multiplier("none",  "fire")   → 1.0   無属性は常に通常
        get_multiplier("fire",  "none")   → 1.0   無属性への攻撃も通常
    """
    # 無効な属性IDはフォールバック（バグで壊れないように）
    if atk_element not in ELEMENT_IDS:
        atk_element = "none"
    if def_element not in ELEMENT_IDS:
        def_element = "none"

    # none が絡む場合は常に通常倍率
    if atk_element == "none" or def_element == "none":
        return NEUTRAL_RATE

    # テーブルを引く。登録なし = 通常倍率
    return ELEMENT_CHART.get((atk_element, def_element), NEUTRAL_RATE)


def get_element_name(element_id: str) -> str:
    """
    属性IDから日本語名を返す。

    引数:
        element_id : 属性ID（"fire" / "water" / … / "none"）

    戻り値:
        str  日本語名（"火" / "水" / … / "無"）
        存在しない ID の場合は "？" を返す。

    使用例:
        get_element_name("fire")   → "火"
        get_element_name("dark")   → "闇"
        get_element_name("none")   → "無"
        get_element_name("xyz")    → "？"
    """
    return ELEMENT_NAME.get(element_id, "？")


def get_element_color(element_id: str) -> tuple[int, int, int]:
    """
    属性IDから表示カラー（RGB）を返す。
    存在しない ID の場合はグレーを返す。

    使用例:
        get_element_color("fire")   → (220, 70, 30)
    """
    return ELEMENT_COLOR.get(element_id, ELEMENT_COLOR["none"])


def get_affinity_label(multiplier: float) -> str:
    """
    倍率から「有利 / 不利 / 通常」の日本語ラベルを返す。
    バトルログや観測補助メッセージの判定に使う。

    使用例:
        get_affinity_label(1.5)   → "有利"
        get_affinity_label(0.75)  → "不利"
        get_affinity_label(1.0)   → "通常"
    """
    if multiplier > NEUTRAL_RATE:
        return "有利"
    if multiplier < NEUTRAL_RATE:
        return "不利"
    return "通常"
