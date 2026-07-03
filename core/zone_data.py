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
            {"to": "distant_path", "hint": "彼方への道へ"},
        ],
        "floor_color": ( 34,  36,  48),
        "wall_color" : ( 18,  20,  30),
    },

    "shrine_inner": {
        "name"       : "古い祠・内部",
        "has_enemies": False,
        "map_type"   : "shrine_inner",
        "exits"      : [
            {"to": "north_road", "hint": "北の道へ戻る"},
            {"to": "boundary_path", "hint": "境界の回廊へ"},
        ],
        "floor_color": ( 32,  31,  42),
        "wall_color" : ( 16,  15,  24),
    },

    "wind_gorge": {
        "name"       : "風鳴きの峡谷",
        "has_enemies": False,
        "map_type"   : "wind_gorge",
        "exits"      : [
            {"to": "field", "hint": "草原へ戻る"},
        ],
        "floor_color": ( 38,  43,  48),
        "wall_color" : ( 22,  24,  30),
    },

    "water_cave": {
        "name"       : "水鏡の洞窟",
        "has_enemies": False,
        "map_type"   : "water_cave",
        "exits"      : [
            {"to": "field", "hint": "草原へ戻る"},
        ],
        "floor_color": ( 24,  40,  52),
        "wall_color" : ( 10,  22,  32),
    },

    "water_cave_depths": {
        "name"       : "水鏡の洞窟・奥",
        "has_enemies": False,
        "map_type"   : "water_cave_depths",
        "exits"      : [
            {"to": "water_cave", "hint": "水鏡の洞窟へ戻る"},
        ],
        "floor_color": ( 18,  34,  48),
        "wall_color" : (  8,  18,  30),
    },

    "water_cave_source": {
        "name"       : "水鏡の洞窟・水源",
        "has_enemies": False,
        "map_type"   : "water_cave_source",
        "exits"      : [
            {"to": "water_cave_depths", "hint": "水鏡の洞窟・奥へ戻る"},
        ],
        "floor_color": ( 15,  31,  46),
        "wall_color" : (  6,  15,  26),
    },

    "water_cave_reflection": {
        "name"       : "水鏡の回廊",
        "has_enemies": False,
        "map_type"   : "water_cave_reflection",
        "exits"      : [
            {"to": "water_cave_depths", "hint": "水鏡の洞窟・奥へ戻る"},
        ],
        "floor_color": ( 20,  36,  58),
        "wall_color" : (  8,  18,  34),
    },

    "water_cave_mirror_chamber": {
        "name"       : "水鏡の間",
        "has_enemies": False,
        "map_type"   : "water_cave_mirror_chamber",
        "exits"      : [
            {"to": "water_cave_reflection", "hint": "水鏡の回廊へ戻る"},
        ],
        "floor_color": ( 18,  34,  56),
        "wall_color" : (  7,  16,  32),
    },

    "ember_path": {
        "name"       : "熾火の道",
        "has_enemies": False,
        "map_type"   : "ember_path",
        "exits"      : [
            {"to": "field", "hint": "草原へ戻る"},
        ],
        "floor_color": ( 68,  38,  28),
        "wall_color" : ( 34,  20,  18),
    },

    "ember_depths": {
        "name"       : "熾火の深部",
        "has_enemies": False,
        "map_type"   : "ember_depths",
        "exits"      : [
            {"to": "ember_path", "hint": "熾火の道へ戻る"},
        ],
        "floor_color": ( 76,  34,  26),
        "wall_color" : ( 24,  16,  16),
    },

    "stonefield_path": {
        "name"       : "岩盤の道",
        "has_enemies": False,
        "map_type"   : "stonefield_path",
        "exits"      : [
            {"to": "field", "hint": "草原へ戻る"},
        ],
        "floor_color": ( 82,  76,  58),
        "wall_color" : ( 38,  34,  28),
    },

    "stonefield_depths": {
        "name"       : "岩盤の深部",
        "has_enemies": False,
        "map_type"   : "stonefield_depths",
        "exits"      : [
            {"to": "stonefield_path", "hint": "岩盤の道へ戻る"},
        ],
        "floor_color": ( 58,  55,  48),
        "wall_color" : ( 24,  23,  22),
    },

    "pale_path": {
        "name"       : "白影の道",
        "has_enemies": False,
        "map_type"   : "pale_path",
        "exits"      : [
            {"to": "field", "hint": "草原へ戻る"},
        ],
        "floor_color": ( 86,  88,  84),
        "wall_color" : ( 38,  38,  42),
    },

    "pale_depths": {
        "name"       : "白影の奥",
        "has_enemies": False,
        "map_type"   : "pale_depths",
        "exits"      : [
            {"to": "pale_path", "hint": "白影の道へ戻る"},
        ],
        "floor_color": ( 78,  78,  76),
        "wall_color" : ( 32,  32,  36),
    },

    "boundary_path": {
        "name"       : "境界の回廊",
        "has_enemies": False,
        "map_type"   : "boundary_path",
        "exits"      : [
            {"to": "shrine_inner", "hint": "古い祠へ戻る"},
        ],
        "floor_color": ( 70,  72,  70),
        "wall_color" : ( 26,  27,  30),
    },

    "boundary_depths": {
        "name"       : "境界の深部",
        "has_enemies": False,
        "map_type"   : "boundary_depths",
        "exits"      : [
            {"to": "boundary_path", "hint": "境界の回廊へ戻る"},
        ],
        "floor_color": ( 66,  68,  68),
        "wall_color" : ( 24,  25,  28),
    },

    "distant_path": {
        "name"       : "彼方への道",
        "has_enemies": False,
        "map_type"   : "distant_path",
        "exits"      : [
            {"to": "north_road", "hint": "北の道へ戻る"},
            {"to": "distant_depths", "hint": "彼方の深部へ"},
            {"to": "old_road", "hint": "忘れられた街道へ"},
        ],
        "floor_color": ( 50,  54,  50),
        "wall_color" : ( 24,  26,  28),
    },

    "distant_depths": {
        "name"       : "彼方の深部",
        "has_enemies": False,
        "map_type"   : "distant_depths",
        "exits"      : [
            {"to": "distant_path", "hint": "彼方への道へ戻る"},
        ],
        "floor_color": ( 54,  56,  52),
        "wall_color" : ( 25,  26,  28),
    },

    "old_road": {
        "name"       : "忘れられた街道",
        "has_enemies": False,
        "map_type"   : "old_road",
        "exits"      : [
            {"to": "distant_path", "hint": "彼方への道へ戻る"},
            {"to": "old_road_depths", "hint": "街道の深部へ"},
            {"to": "sealed_path", "hint": "閉ざされた小径へ"},
        ],
        "floor_color": ( 56,  58,  52),
        "wall_color" : ( 25,  27,  27),
    },

    "old_road_depths": {
        "name"       : "街道の深部",
        "has_enemies": False,
        "map_type"   : "old_road_depths",
        "exits"      : [
            {"to": "old_road", "hint": "忘れられた街道へ戻る"},
        ],
        "floor_color": ( 58,  59,  53),
        "wall_color" : ( 25,  26,  27),
    },

    "sealed_path": {
        "name"       : "閉ざされた小径",
        "has_enemies": False,
        "map_type"   : "sealed_path",
        "exits"      : [
            {"to": "old_road", "hint": "忘れられた街道へ戻る"},
            {"to": "sealed_path_depths", "hint": "閉ざされた奥へ"},
            {"to": "lost_place", "hint": "失われた場所へ"},
        ],
        "floor_color": ( 52,  56,  52),
        "wall_color" : ( 24,  27,  27),
    },

    "sealed_path_depths": {
        "name"       : "閉ざされた奥",
        "has_enemies": False,
        "map_type"   : "sealed_path_depths",
        "exits"      : [
            {"to": "sealed_path", "hint": "閉ざされた小径へ戻る"},
        ],
        "floor_color": ( 54,  56,  53),
        "wall_color" : ( 24,  26,  27),
    },

    # ──────────────────────────────────────────────────
    #  以下は将来追加予定（コメントで設計を残しておく）
    # ──────────────────────────────────────────────────

    "lost_place": {
        "name"       : "失われた場所",
        "has_enemies": False,
        "map_type"   : "lost_place",
        "exits"      : [
            {"to": "sealed_path", "hint": "閉ざされた小径へ戻る"},
            {"to": "lost_place_depths", "hint": "失われた場所の奥へ"},
            {"to": "forgotten_boundary", "hint": "忘れられた境域へ"},
        ],
        "floor_color": ( 55,  57,  54),
        "wall_color" : ( 24,  26,  27),
    },

    "lost_place_depths": {
        "name"       : "失われた場所の奥",
        "has_enemies": False,
        "map_type"   : "lost_place_depths",
        "exits"      : [
            {"to": "lost_place", "hint": "失われた場所へ戻る"},
        ],
        "floor_color": ( 52,  54,  53),
        "wall_color" : ( 23,  25,  26),
    },

    "forgotten_boundary": {
        "name"       : "忘れられた境域",
        "has_enemies": False,
        "map_type"   : "forgotten_boundary",
        "exits"      : [
            {"to": "lost_place", "hint": "失われた場所へ戻る"},
            {"to": "forgotten_boundary_depths", "hint": "忘れられた境域の奥へ"},
            {"to": "far_boundary", "hint": "彼方へ続く境目へ"},
        ],
        "floor_color": ( 50,  53,  53),
        "wall_color" : ( 22,  24,  26),
    },

    "forgotten_boundary_depths": {
        "name"       : "忘れられた境域の奥",
        "has_enemies": False,
        "map_type"   : "forgotten_boundary_depths",
        "exits"      : [
            {"to": "forgotten_boundary", "hint": "忘れられた境域へ戻る"},
        ],
        "floor_color": ( 49,  51,  52),
        "wall_color" : ( 21,  23,  25),
    },

    "far_boundary": {
        "name"       : "彼方へ続く境目",
        "has_enemies": False,
        "map_type"   : "far_boundary",
        "exits"      : [
            {"to": "forgotten_boundary", "hint": "忘れられた境域へ戻る"},
            {"to": "far_boundary_depths", "hint": "彼方へ続く境目の奥へ"},
            {"to": "far_echo", "hint": "彼方の残響へ"},
        ],
        "floor_color": ( 48,  50,  51),
        "wall_color" : ( 20,  22,  24),
    },

    "far_boundary_depths": {
        "name"       : "彼方へ続く境目の奥",
        "has_enemies": False,
        "map_type"   : "far_boundary_depths",
        "exits"      : [
            {"to": "far_boundary", "hint": "彼方へ続く境目へ戻る"},
        ],
        "floor_color": ( 47,  49,  50),
        "wall_color" : ( 19,  21,  23),
    },

    "far_echo": {
        "name"       : "彼方の残響",
        "has_enemies": False,
        "map_type"   : "far_echo",
        "exits"      : [
            {"to": "far_boundary", "hint": "彼方へ続く境目へ戻る"},
            {"to": "far_echo_depths", "hint": "彼方の残響の奥へ"},
            {"to": "far_connection", "hint": "彼方の接続点へ"},
        ],
        "floor_color": ( 49,  50,  49),
        "wall_color" : ( 20,  21,  22),
    },

    "far_echo_depths": {
        "name"       : "彼方の残響の奥",
        "has_enemies": False,
        "map_type"   : "far_echo_depths",
        "exits"      : [
            {"to": "far_echo", "hint": "彼方の残響へ戻る"},
        ],
        "floor_color": ( 48,  49,  48),
        "wall_color" : ( 19,  20,  21),
    },

    "far_connection": {
        "name"       : "彼方の接続点",
        "has_enemies": False,
        "map_type"   : "far_connection",
        "exits"      : [
            {"to": "far_echo", "hint": "彼方の残響へ戻る"},
            {"to": "far_connection_depths", "hint": "彼方の接続点の奥へ"},
            {"to": "far_relay", "hint": "彼方の中継地へ"},
        ],
        "floor_color": ( 50,  50,  48),
        "wall_color" : ( 20,  20,  22),
    },

    "far_connection_depths": {
        "name"       : "彼方の接続点の奥",
        "has_enemies": False,
        "map_type"   : "far_connection_depths",
        "exits"      : [
            {"to": "far_connection", "hint": "彼方の接続点へ戻る"},
        ],
        "floor_color": ( 49,  49,  47),
        "wall_color" : ( 19,  20,  22),
    },

    "far_relay": {
        "name"       : "彼方の中継地",
        "has_enemies": False,
        "map_type"   : "far_relay",
        "exits"      : [
            {"to": "far_connection", "hint": "彼方の接続点へ戻る"},
            {"to": "far_relay_depths", "hint": "彼方の中継地の奥へ"},
            {"to": "far_terminus", "hint": "彼方の終端へ"},
        ],
        "floor_color": ( 52,  51,  47),
        "wall_color" : ( 21,  20,  21),
    },

    "far_relay_depths": {
        "name"       : "彼方の中継地の奥",
        "has_enemies": False,
        "map_type"   : "far_relay_depths",
        "exits"      : [
            {"to": "far_relay", "hint": "彼方の中継地へ戻る"},
        ],
        "floor_color": ( 50,  49,  46),
        "wall_color" : ( 20,  19,  21),
    },

    "far_terminus": {
        "name"       : "彼方の終端",
        "has_enemies": False,
        "map_type"   : "far_terminus",
        "exits"      : [
            {"to": "far_relay", "hint": "彼方の中継地へ戻る"},
            {"to": "outer_edge", "hint": "外縁の道へ"},
        ],
        "floor_color": ( 51,  50,  47),
        "wall_color" : ( 20,  20,  21),
    },

    "outer_edge": {
        "name"       : "外縁の道",
        "has_enemies": False,
        "map_type"   : "outer_edge",
        "exits"      : [
            {"to": "far_terminus", "hint": "彼方の終端へ戻る"},
            {"to": "outer_edge_depths", "hint": "外縁の道の奥へ"},
        ],
        "floor_color": ( 49,  50,  48),
        "wall_color" : ( 18,  20,  22),
    },

    "outer_edge_depths": {
        "name"       : "外縁の道の奥",
        "has_enemies": False,
        "map_type"   : "outer_edge_depths",
        "exits"      : [
            {"to": "outer_edge", "hint": "外縁の道へ戻る"},
        ],
        "floor_color": ( 46,  48,  47),
        "wall_color" : ( 16,  18,  21),
    },

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
