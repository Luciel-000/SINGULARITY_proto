"""
============================================================
  core/zone_data.py  ── ゾーン（エリア）データ定義  [0.6 新規]

  担当:
    - ゲーム内のゾーン（マップエリア）をIDと辞書で一元管理
    - ゾーンごとの設定（名前・敵の有無・マップ種別・出口）を保持
    - 不正なゾーンIDでもフォールバックして落ちない安全設計

  ── ゾーン辞書の構造 ─────────────────────────────────────
  ZONE_DATA["ゾーンID"] = {
      "name"        : マップ名（HUD・画面遷移メッセージに使う）
      "has_enemies" : 敵をスポーンするか（True / False）
      "map_type"    : マップ生成方式
                        "dungeon" = 現在のランダム部屋+通路生成
                        "town"    = 固定レイアウト（将来実装予定）
      "exits"       : 出口リスト。各要素は辞書
                        {"to": "遷移先ゾーンID", "hint": "ヒント文字列"}
      "floor_color" : 床タイルの色（RGB）
                        None の場合は constants.C_FLOOR を使う
      "wall_color"  : 壁タイルの色（RGB）
                        None の場合は constants.C_WALL を使う
  }

  ── 現在定義されているゾーン ────────────────────────────
    "town"  : 始まりの町（敵なし）
    "field" : 始まりの草原（スライムが出現）

  ── 将来の拡張方法 ──────────────────────────────────────
    新しいゾーンを追加するには:
      1. ZONE_DATA に新しいエントリを追加するだけ
      2. world.py / game.py は変更不要
    例:
      "forest" : { "name": "迷いの森",   "has_enemies": True, ... }
      "cave"   : { "name": "古の洞窟",   "has_enemies": True, ... }
      "temple" : { "name": "始源の神殿", "has_enemies": True, ... }

  ── 他ファイルとの依存関係 ──────────────────────────────
    - constants.py の色定数のみ参照
    - world.py / game.py / player.py / enemy.py / battle.py は import しない
      （循環 import を防ぐため）

  ── 使い方 ──────────────────────────────────────────────
    from core.zone_data import (
        get_zone, get_zone_name, zone_has_enemies,
        get_zone_exits, DEFAULT_ZONE_ID, all_zone_ids,
    )

    zone = get_zone("field")          # 辞書をまるごと取得
    name = get_zone_name("town")      # → "始まりの町"
    has  = zone_has_enemies("field")  # → True
    has  = zone_has_enemies("town")   # → False
    exits = get_zone_exits("town")    # → [{"to": "field", "hint": "草原へ"}]

    # 不正なIDは field にフォールバック（落ちない）
    zone = get_zone("unknown")        # → ZONE_DATA["field"] の内容
============================================================
"""

from .constants import C_FLOOR, C_WALL  # 既存の色定数を床・壁のデフォルトに使う


# ── デフォルトのゾーンID ─────────────────────────────────
# 不正なゾーンIDが渡されたときのフォールバック先
DEFAULT_ZONE_ID = "field"


# ── ゾーンデータ辞書 ─────────────────────────────────────
#
# ★ 新しいゾーンを追加するときはここにエントリを追記するだけ！
#
ZONE_DATA: dict[str, dict] = {

    # ──────────────────────────────────────────────────
    #  始まりの町（敵なし・安全エリア）
    # ──────────────────────────────────────────────────
    "town": {
        # マップ名（HUDや遷移メッセージに表示する）
        "name"       : "始まりの町",

        # 敵を出すか（False = 敵をスポーンしない）
        "has_enemies": False,

        # マップ生成方式
        # "town"    = 固定レイアウト（Step3以降で実装予定）
        # "dungeon" = ランダム部屋+通路生成（現在の world.py の方式）
        "map_type"   : "town",

        # 出口リスト（各要素: {"to": 遷移先ID, "hint": ヒント文字列}）
        "exits"      : [
            {"to": "field", "hint": "草原へ"},
        ],

        # 床・壁の色（None のとき constants.C_FLOOR / C_WALL を使う）
        # 町は少し明るい石畳のイメージ
        "floor_color": ( 45,  40,  55),  # やや明るい石畳
        "wall_color" : ( 35,  30,  48),  # 石造りの壁
    },

    # ──────────────────────────────────────────────────
    #  始まりの草原（スライムが出現するフィールド）
    # ──────────────────────────────────────────────────
    "field": {
        "name"       : "始まりの草原",

        # 敵を出す（True = スライムをスポーンする）
        "has_enemies": True,

        # 現在の world.py のランダム生成をそのまま使う
        "map_type"   : "dungeon",

        "exits"      : [
            {"to": "town", "hint": "町へ戻る"},
        ],

        # 既存の色をそのまま使う（None でも同じ結果だが明示的に設定）
        "floor_color": C_FLOOR,   # (28, 24, 38) 暗い床
        "wall_color" : C_WALL,    # (18, 15, 28) 暗い壁
    },

    "north_road": {
        "name"       : "北の道",
        "has_enemies": False,
        "map_type"   : "north_road",
        "exits"      : [
            {"to": "town", "hint": "村へ戻る"},
        ],
        "floor_color": ( 34,  36,  48),
        "wall_color" : ( 18,  20,  30),
    },

    # ──────────────────────────────────────────────────
    #  以下は将来追加予定（コメントで設計を残しておく）
    # ──────────────────────────────────────────────────

    # "forest": {
    #     "name"       : "迷いの森",
    #     "has_enemies": True,
    #     "map_type"   : "dungeon",
    #     "exits"      : [{"to": "field", "hint": "草原へ戻る"}],
    #     "floor_color": ( 20,  35,  20),  # 緑がかった暗い土
    #     "wall_color" : ( 12,  22,  12),
    # },

    # "cave": {
    #     "name"       : "古の洞窟",
    #     "has_enemies": True,
    #     "map_type"   : "dungeon",
    #     "exits"      : [{"to": "field", "hint": "草原へ出る"}],
    #     "floor_color": ( 30,  25,  20),  # 土と岩
    #     "wall_color" : ( 18,  14,  10),
    # },

    # "temple": {
    #     "name"       : "始源の神殿",
    #     "has_enemies": True,
    #     "map_type"   : "dungeon",
    #     "exits"      : [{"to": "cave",  "hint": "洞窟へ戻る"}],
    #     "floor_color": ( 38,  32,  50),
    #     "wall_color" : ( 25,  20,  38),
    # },
}


# ── フォールバック用データ ────────────────────────────────
# 不正なゾーンIDが渡されたとき、これを返す（ZONE_DATA["field"] と同値）
_FALLBACK_ZONE: dict = ZONE_DATA[DEFAULT_ZONE_ID]


# ── 公開関数 ─────────────────────────────────────────────

def get_zone(zone_id: str) -> dict:
    """
    ゾーンIDからゾーンデータ辞書を返す。
    存在しないIDのときは DEFAULT_ZONE_ID（field）にフォールバック。

    引数:
        zone_id : ゾーンID（"town" / "field" など）

    戻り値:
        dict : ゾーンデータ（keys: name, has_enemies, map_type, exits, ...）

    使用例:
        zone = get_zone("field")
        print(zone["name"])   # → "始まりの草原"

        zone = get_zone("unknown")   # → "field" のデータ（フォールバック）
    """
    return ZONE_DATA.get(zone_id, _FALLBACK_ZONE)


def get_zone_name(zone_id: str) -> str:
    """
    ゾーンIDからマップ名を返す。
    HUD表示や画面遷移メッセージに使う。

    使用例:
        get_zone_name("town")    → "始まりの町"
        get_zone_name("field")   → "始まりの草原"
        get_zone_name("unknown") → "始まりの草原"  ← フォールバック
    """
    return get_zone(zone_id)["name"]


def zone_has_enemies(zone_id: str) -> bool:
    """
    そのゾーンで敵をスポーンするかを返す。
    game.py が _init_game() / _respawn_enemies() を呼ぶ前に参照する。

    使用例:
        zone_has_enemies("field")   → True
        zone_has_enemies("town")    → False
        zone_has_enemies("unknown") → True  ← フォールバック（field 相当）
    """
    return get_zone(zone_id)["has_enemies"]


def get_zone_exits(zone_id: str) -> list[dict]:
    """
    そのゾーンの出口リストを返す。
    各要素は {"to": 遷移先ゾーンID, "hint": ヒント文字列} の辞書。
    出口がないゾーンは空リストを返す。

    使用例:
        get_zone_exits("town")
        → [{"to": "field", "hint": "草原へ"}]

        get_zone_exits("field")
        → [{"to": "town", "hint": "町へ戻る"}]
    """
    return get_zone(zone_id).get("exits", [])


def get_zone_map_type(zone_id: str) -> str:
    """
    そのゾーンのマップ生成方式を返す。
    world.py がマップを生成するときに参照する。

    戻り値:
        "dungeon" : ランダム部屋+通路生成（現在の world.py の方式）
        "town"    : 固定レイアウト（将来実装予定）

    使用例:
        get_zone_map_type("field")  → "dungeon"
        get_zone_map_type("town")   → "town"
    """
    return get_zone(zone_id).get("map_type", "dungeon")


def get_zone_colors(zone_id: str) -> tuple[tuple, tuple]:
    """
    そのゾーンの (床色, 壁色) を返す。
    world.py がタイルを描画するときに参照する。

    戻り値:
        (floor_color, wall_color) : それぞれ RGB タプル

    使用例:
        floor, wall = get_zone_colors("town")
    """
    zone        = get_zone(zone_id)
    floor_color = zone.get("floor_color") or C_FLOOR
    wall_color  = zone.get("wall_color")  or C_WALL
    return floor_color, wall_color


def all_zone_ids() -> list[str]:
    """
    全ゾーンIDのリストを返す（デバッグ・UI用）。

    使用例:
        all_zone_ids()  → ["town", "field"]
    """
    return list(ZONE_DATA.keys())
