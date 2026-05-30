"""
============================================================
  core/sage_messages.py  ── 大賢者メッセージ管理  [0.5 Step3 新規]

  担当:
    - バトル中に大賢者が発するセリフを一元管理
    - 状況タグ・属性・スキルに応じてメッセージを返す
    - 不正な引数でも必ず文字列を返す（ゲームを落とさない）

  ── 大賢者とは ───────────────────────────────────────────
    SINGULARITY の世界に存在する「未完成AI / 世界叡智システム」。
    起源（Origin）の時代に構築された属性解析を行う支援存在であり、
    感情や意図を持つかは不明だが、バトル中にプレイヤーへ
    属性情報・スキル解析・状況判断の助言を出力する。
    バトルログ下部（またはポップアップ）に表示する想定。

  ── メッセージ種別（situation タグ）─────────────────────
    "battle_start" : バトル開始時
    "effective"    : 属性が有利だったとき
    "weak"         : 属性が不利だったとき
    "neutral"      : 属性相性が通常のとき
    "observe"      : 観察スキル使用時
    "skill_use"    : スキル使用時（汎用）
    "level_up"     : レベルアップ時

  ── 他ファイルとの依存関係 ──────────────────────────────
    - element_system.py : 属性名・倍率ラベルの取得に使用
    - skill_data.py     : スキル名の取得に使用
    - battle.py から呼ばれる予定（Step 8 で連携）

  ── 使い方 ──────────────────────────────────────────────
    from core.sage_messages import (
        get_sage_message,
        get_affinity_message,
        get_battle_start_message,
        get_observe_message,
        get_skill_message,
    )

    # 汎用メッセージ
    msg = get_sage_message("battle_start")
    msg = get_sage_message("effective", atk_element="fire", def_element="wind")
    msg = get_sage_message("skill_use", skill_id="fireball")

    # 専用ラッパー（引数が明確で読みやすい）
    msg = get_affinity_message("fire", "wind")
    msg = get_battle_start_message(enemy_name="火スライム", enemy_element="fire")
    msg = get_observe_message(enemy_name="水スライム", enemy_element="water")
    msg = get_skill_message("fireball")
============================================================
"""

import random

# ── 他の core モジュールから必要な関数だけインポート ─────
from .element_system import (
    get_element_name,
    get_affinity_label,
    get_multiplier,
    ELEMENT_IDS,
)
from .skill_data import get_skill_name, is_valid_skill

# ── 大賢者の名称プレフィックス ───────────────────────────
SAGE_PREFIX = "《大賢者》"

# ── フォールバックメッセージ（何も当たらなかったとき） ───
_FALLBACK_MSG = f"{SAGE_PREFIX}……（沈黙）"


# ── メッセージプール ─────────────────────────────────────
# 同じ状況でも複数のセリフからランダム選択する。
# バリエーションが多いほど表示が単調にならない。
#
# キー = situation タグ
# 値   = セリフ文字列のリスト（1件でもリストにする）
#
# ★ セリフを追加・変更したいときはここだけ編集すればよい
#
_MESSAGE_POOL: dict[str, list[str]] = {

    # ── バトル開始 ──────────────────────────────────────
    "battle_start": [
        f"{SAGE_PREFIX}戦闘を開始します。対象の属性を解析中……",
        f"{SAGE_PREFIX}敵影を感知。能力値の測定を開始します。",
        f"{SAGE_PREFIX}警戒を解かぬよう。属性解析を行います。",
    ],

    # ── 属性有利 ────────────────────────────────────────
    "effective": [
        f"{SAGE_PREFIX}解析完了。攻撃属性は対象に有効です。",
        f"{SAGE_PREFIX}属性が有効に作用しています。攻勢を維持してください。",
        f"{SAGE_PREFIX}好機。この属性は対象の弱点です。",
    ],

    # ── 属性不利 ────────────────────────────────────────
    "weak": [
        f"{SAGE_PREFIX}警告。この属性は対象に対して効果が薄いようです。",
        f"{SAGE_PREFIX}相性が悪い。属性または戦術の変更を検討してください。",
        f"{SAGE_PREFIX}この組み合わせは不利です。慎重に。",
    ],

    # ── 属性通常 ────────────────────────────────────────
    "neutral": [
        f"{SAGE_PREFIX}属性相性に大きな変化はありません。",
        f"{SAGE_PREFIX}通常の属性相性です。技術で補いましょう。",
        f"{SAGE_PREFIX}相性は中立。実力勝負になります。",
    ],

    # ── 観察スキル ──────────────────────────────────────
    "observe": [
        f"{SAGE_PREFIX}対象を観察します。属性・行動傾向・弱点を解析中……",
        f"{SAGE_PREFIX}スキャン開始。対象のデータを収集しています……",
        f"{SAGE_PREFIX}解析を試みます。しばらくお待ちください……",
    ],

    # ── スキル使用（汎用） ──────────────────────────────
    "skill_use": [
        f"{SAGE_PREFIX}スキル発動を確認しました。",
        f"{SAGE_PREFIX}技能が行使されました。結果を観察します。",
        f"{SAGE_PREFIX}スキルの発動を記録しました。",
    ],

    # ── レベルアップ ────────────────────────────────────
    "level_up": [
        f"{SAGE_PREFIX}レベル上昇を確認。能力値の成長を記録します。",
        f"{SAGE_PREFIX}力が増しています。記録を更新しました。",
        f"{SAGE_PREFIX}成長を感知。汝の魂が一段上の領域へ踏み込みました。",
    ],
}


# ── 属性別の特殊メッセージ ───────────────────────────────
# 特定の属性が絡むときだけ出る追加コメント。
# get_affinity_message() の末尾に付加する（任意）。
#
_ELEMENT_COMMENT: dict[str, str] = {
    "fire"  : f"{SAGE_PREFIX}炎は風に乗り、さらなる力を得ます。",
    "water" : f"{SAGE_PREFIX}水は流れ、火を制します。",
    "wind"  : f"{SAGE_PREFIX}風は大地を侵食します。",
    "earth" : f"{SAGE_PREFIX}大地は水を吸い込み、その流れを断ちます。",
    "light" : f"{SAGE_PREFIX}光は闇を照らし、その本質を暴きます。",
    "dark"  : f"{SAGE_PREFIX}闇は光を呑み込み、その輝きを奪います。",
    "none"  : "",   # 無属性はコメントなし
}


# ──────────────────────────────────────────────────────────
#  内部ヘルパー
# ──────────────────────────────────────────────────────────

def _pick(situation: str) -> str:
    """
    メッセージプールから situation に対応するセリフをランダムに1つ選ぶ。
    存在しない situation のときはフォールバックを返す。
    """
    pool = _MESSAGE_POOL.get(situation)
    if not pool:
        return _FALLBACK_MSG
    return random.choice(pool)


def _safe_element(element_id) -> str:
    """
    属性IDを安全に正規化する。
    None または不正な値は "none" に変換する。
    """
    if element_id is None:
        return "none"
    return element_id if element_id in ELEMENT_IDS else "none"


# ──────────────────────────────────────────────────────────
#  公開関数
# ──────────────────────────────────────────────────────────

def get_sage_message(
    situation: str,
    atk_element: str | None = None,
    def_element: str | None = None,
    skill_id:    str | None = None,
) -> str:
    """
    状況タグとオプション情報からメッセージを返す汎用関数。

    引数:
        situation   : メッセージ種別タグ
                      "battle_start" / "effective" / "weak" /
                      "neutral" / "observe" / "skill_use" / "level_up"
        atk_element : 攻撃側の属性ID（省略可）
        def_element : 防御側の属性ID（省略可）
        skill_id    : 使用スキルID（省略可）

    戻り値:
        str : 大賢者のセリフ（必ず文字列を返す）

    使用例:
        get_sage_message("battle_start")
        get_sage_message("effective", atk_element="fire", def_element="wind")
        get_sage_message("skill_use", skill_id="fireball")
        get_sage_message("unknown_tag")   # → フォールバックメッセージ
    """
    # 属性を安全に正規化
    atk = _safe_element(atk_element)
    df  = _safe_element(def_element)

    # 属性相性に応じた分岐
    if situation in ("effective", "weak", "neutral"):
        return get_affinity_message(atk, df)

    # スキル使用
    if situation == "skill_use" and skill_id:
        return get_skill_message(skill_id)

    # 観察スキル
    if situation == "observe":
        return _pick("observe")

    # それ以外はプールから選ぶ
    return _pick(situation)


def get_affinity_message(
    atk_element: str,
    def_element: str,
) -> str:
    """
    攻撃側と防御側の属性IDから、相性に応じたメッセージを返す。
    "effective" / "weak" / "neutral" のいずれかを自動判定して選択する。

    引数:
        atk_element : 攻撃側の属性ID
        def_element : 防御側の属性ID

    戻り値:
        str : 大賢者のセリフ

    使用例:
        get_affinity_message("fire", "wind")   # 有利メッセージ
        get_affinity_message("wind", "fire")   # 不利メッセージ
        get_affinity_message("fire", "fire")   # 通常メッセージ
        get_affinity_message("none", "fire")   # 通常メッセージ
    """
    atk = _safe_element(atk_element)
    df  = _safe_element(def_element)

    # 倍率から相性ラベルを取得（"有利" / "不利" / "通常"）
    mult  = get_multiplier(atk, df)
    label = get_affinity_label(mult)

    # ラベルを situation タグに変換
    situation_map = {
        "有利": "effective",
        "不利": "weak",
        "通常": "neutral",
    }
    situation = situation_map.get(label, "neutral")
    base_msg  = _pick(situation)

    # 有利・不利のとき「攻撃属性名 → 防御属性名」の補足を追加
    if situation in ("effective", "weak"):
        atk_name = get_element_name(atk)
        def_name = get_element_name(df)
        base_msg += f"  ［{atk_name}属性 → {def_name}属性：{label}］"

    return base_msg


def get_battle_start_message(
    enemy_name:    str | None = None,
    enemy_element: str | None = None,
) -> str:
    """
    バトル開始時のメッセージを返す。
    敵の名前と属性が分かる場合は情報を付加する。

    引数:
        enemy_name    : 敵の名前（"火スライム" など）省略可
        enemy_element : 敵の属性ID（"fire" など）省略可

    戻り値:
        str : 大賢者のセリフ

    使用例:
        get_battle_start_message()
        get_battle_start_message("火スライム", "fire")
        get_battle_start_message(enemy_name="闇スライム", enemy_element="dark")
    """
    base_msg = _pick("battle_start")

    # 敵情報が揃っているときは属性情報を付加
    if enemy_name and enemy_element:
        elem = _safe_element(enemy_element)
        elem_name = get_element_name(elem)
        base_msg += f"  ［対象：{enemy_name} / 属性：{elem_name}］"
    elif enemy_name:
        base_msg += f"  ［対象：{enemy_name}］"

    return base_msg


def get_observe_message(
    enemy_name:    str | None = None,
    enemy_element: str | None = None,
) -> str:
    """
    「観察」スキル使用時のメッセージを返す。
    敵の属性が分かる場合は弱点情報を付加する。

    引数:
        enemy_name    : 敵の名前（省略可）
        enemy_element : 敵の属性ID（省略可）

    戻り値:
        str : 大賢者のセリフ

    使用例:
        get_observe_message()
        get_observe_message("水スライム", "water")
    """
    base_msg = _pick("observe")

    # 敵属性が分かる場合、弱点属性を追加
    if enemy_element:
        elem = _safe_element(enemy_element)
        if elem != "none":
            elem_name = get_element_name(elem)
            # 弱点属性（この属性に有利な攻撃属性）を逆引きして表示
            weak_to = _find_effective_elements(elem)
            if weak_to:
                weak_names = "・".join(get_element_name(e) for e in weak_to)
                base_msg += f"  ［属性：{elem_name} / 弱点：{weak_names}属性］"
            else:
                base_msg += f"  ［属性：{elem_name} / 弱点：なし（解析不能）］"

    if enemy_name:
        # 名前を先頭に追加（読みやすさのため）
        base_msg = base_msg.replace(
            SAGE_PREFIX,
            f"{SAGE_PREFIX}「{enemy_name}」を解析します。",
            1
        )

    return base_msg


def _find_effective_elements(def_element: str) -> list[str]:
    """
    指定した防御属性に「有利」な攻撃属性のリストを返す内部関数。
    get_observe_message() の弱点表示に使う。

    引数:
        def_element : 調べたい防御属性ID

    戻り値:
        list[str] : 有利な攻撃属性IDのリスト
    """
    from .element_system import ELEMENT_CHART, ADVANTAGE_RATE
    result = []
    for (atk, df), mult in ELEMENT_CHART.items():
        if df == def_element and mult >= ADVANTAGE_RATE:
            result.append(atk)
    return result


def get_skill_message(skill_id: str) -> str:
    """
    スキル使用時のメッセージを返す。
    有効なスキルIDならスキル名を含めたメッセージを返す。
    無効なIDでもフォールバックで安全に動作する。

    引数:
        skill_id : スキルID（"fireball" / "tackle" など）

    戻り値:
        str : 大賢者のセリフ

    使用例:
        get_skill_message("fireball")
        → "《大賢者》スキル「ファイアボール」の発動を確認しました。"
        get_skill_message("unknown")
        → "《大賢者》スキル発動を確認しました。"
    """
    if is_valid_skill(skill_id):
        skill_name = get_skill_name(skill_id)
        return f"{SAGE_PREFIX}スキル「{skill_name}」の発動を確認しました。"

    # 不正なIDのとき汎用メッセージ
    return _pick("skill_use")
