"""
============================================================
  core/world.py  ── マップ生成・描画クラス  [0.7 更新]

  [0.7 変更点]
    - self.npc_spawns を追加（NPC 配置座標リスト）
    - _generate_town() で謎の老人のスポーン座標を記録
    - _build_npc_spawns() を追加（タイル座標 → ピクセル座標変換）
    - get_npc_spawns() を追加（game.py が NPC 生成に使う）
    - field では get_npc_spawns() が空リスト [] を返す

  [0.6 変更点（継続）]
    - World(zone_id="field") 形式に変更（デフォルト引数で後方互換）
    - ゾーンIDから名前・色・敵有無・出口情報を zone_data.py より取得
    - exit_rects を追加（出口タイルの当たり判定）
    - draw() で出口タイルをくすんだゴールドで描画

  [互換性維持]
    - World() 引数なし → zone_id="field" として動作（既存コード影響なし）
    - wall_rects / player_spawn / rooms / exit_rects の型・意味は変わらない
    - get_enemy_spawns() の戻り値型は変わらない

  タイルデータ：0 = 床、1 = 壁、2 = 出口タイル
============================================================
"""

import pygame
import random
from .constants import (
    TILE, WINDOW_W, GAME_AREA_H,
    C_FLOOR, C_WALL, C_GRID,
    C_TOWN_FLOOR, C_TOWN_WALL,   # ★ 0.6: 町用タイル色
    C_EXIT_TILE,                 # ★ 0.6: 出口タイル色
)
from .zone_data import (         # ★ 0.6: ゾーン情報取得
    get_zone_name,
    get_zone_map_type,
    get_zone_colors,
    zone_has_enemies,
    get_zone_exits,
    DEFAULT_ZONE_ID,
)

# マップのタイル数（画面サイズ ÷ タイルサイズ）
MAP_COLS = WINDOW_W    // TILE   # 横方向のタイル数 = 25
MAP_ROWS = GAME_AREA_H // TILE   # 縦方向のタイル数 = 15

# タイル値の定数
TILE_WALL   = 1   # 壁
TILE_FLOOR  = 0   # 床
TILE_EXIT   = 2   # 出口タイル（★ 0.6 追加）
TILE_SHRINE = 3   # 古い祠の入口イベント地点
TILE_FRAGMENT = 4  # 封印の欠片イベント地点
TILE_ALTAR = 5     # 祠内部の祭壇地点


class Room:
    """マップ内の1つの部屋を表すデータクラス（変更なし）"""

    def __init__(self, col: int, row: int, w: int, h: int):
        self.col = col
        self.row = row
        self.w   = w
        self.h   = h

    def center(self) -> tuple[int, int]:
        return (self.col + self.w // 2, self.row + self.h // 2)

    def overlaps(self, other: "Room", margin: int = 1) -> bool:
        return (
            self.col - margin < other.col + other.w and
            self.col + self.w + margin > other.col and
            self.row - margin < other.row + other.h and
            self.row + self.h + margin > other.row
        )


class World:
    """
    ゲームマップ全体を管理するクラス。

    使い方:
        world = World()               # 後方互換（field と同じ）
        world = World("field")        # 始まりの草原（ランダムダンジョン）
        world = World("town")         # 始まりの町（固定広間）

    属性（0.5 以前と互換）:
        wall_rects    : 壁の pygame.Rect リスト（当たり判定用）
        rooms         : 部屋のリスト（敵スポーン位置に使う）
        player_spawn  : プレイヤーの初期位置（ピクセル座標）

    属性（0.6 新規追加）:
        zone_id       : ゾーンID文字列（"field" / "town" など）
        zone_name     : マップ名（"始まりの草原" など）
        has_enemies   : 敵をスポーンするか（bool）
        map_type      : マップ生成方式（"dungeon" / "town"）
        floor_color   : 床タイルの色（RGB）
        wall_color    : 壁タイルの色（RGB）
        exit_rects    : 出口タイルの pygame.Rect リスト

    属性（0.7 新規追加）:
        npc_spawns    : NPC 配置座標のリスト（ピクセル座標）
                        town の場合: [(x, y)] 1件
                        field の場合: []（NPC なし）
    """

    def __init__(self, zone_id: str = DEFAULT_ZONE_ID):
        # ── ★ 0.6: ゾーン情報をセット
        self.zone_id    = zone_id
        self.zone_name  = get_zone_name(zone_id)
        self.has_enemies = zone_has_enemies(zone_id)
        self.map_type   = get_zone_map_type(zone_id)
        self.floor_color, self.wall_color = get_zone_colors(zone_id)

        # ── タイルデータ・描画キャッシュ（変更なし）
        self._tiles: list[list[int]] = []
        self._map_surface: pygame.Surface | None = None

        # ── 既存の公開属性（変更なし）
        self.wall_rects: list[pygame.Rect]  = []
        self.rooms:      list[Room]         = []
        self.player_spawn: tuple[int, int]  = (TILE * 2 + 4, TILE * 2 + 4)

        # ── ★ 0.6: 出口タイルの当たり判定 Rect リスト
        self.exit_rects: list[pygame.Rect]  = []
        self.shrine_rects: list[pygame.Rect] = []
        self.fragment_rects: list[pygame.Rect] = []
        self.altar_rects: list[pygame.Rect] = []

        # ── ★ 0.7: NPC 配置座標リスト（ピクセル座標）
        # _generate_town() が _npc_tile_positions に記録し、
        # _build_npc_spawns() がピクセル座標に変換して npc_spawns に格納する。
        self._npc_tile_positions: list[tuple[int, int]] = []  # 内部用タイル座標
        self.npc_spawns: list[tuple[int, int]] = []           # 公開用ピクセル座標

        # ── マップを生成して各データを構築する
        self._generate()
        self._build_surface()
        self._build_wall_rects()
        self._build_exit_rects()
        self._build_shrine_rects()
        self._build_fragment_rects()
        self._build_altar_rects()
        self._build_npc_spawns()  # ★ 0.7

    # ──────────────────────────────────────────────────────
    #  マップ生成ディスパッチャ（★ 0.6 変更）
    # ──────────────────────────────────────────────────────
    def _generate(self):
        """
        map_type に応じて生成方式を切り替える。
          "dungeon" → _generate_dungeon()（旧 _generate、変更なし）
          "town"    → _generate_town()（固定広間レイアウト）
        """
        if self.map_type == "dungeon":
            self._generate_dungeon()
        elif self.map_type == "north_road":
            self._generate_north_road()
        elif self.map_type == "shrine_inner":
            self._generate_shrine_inner()
        else:
            self._generate_town()

    # ──────────────────────────────────────────────────────
    #  ダンジョン生成（旧 _generate そのまま、field 用）
    # ──────────────────────────────────────────────────────
    def _generate_dungeon(self):
        """
        ランダムなダンジョンマップを生成する（0.5 以前と同じロジック）。
        アルゴリズム：
          1. 全体を壁で埋める
          2. ランダムに部屋を配置する（重なり排除）
          3. 隣の部屋と L 字型の通路でつなぐ
        """
        self._tiles = [[TILE_WALL] * MAP_COLS for _ in range(MAP_ROWS)]

        MAX_ATTEMPTS = 25
        MIN_ROOM_W   = 4
        MAX_ROOM_W   = 10
        MIN_ROOM_H   = 4
        MAX_ROOM_H   = 8

        for _ in range(MAX_ATTEMPTS):
            rw = random.randint(MIN_ROOM_W, MAX_ROOM_W)
            rh = random.randint(MIN_ROOM_H, MAX_ROOM_H)
            rc = random.randint(1, MAP_COLS - rw - 2)
            rr = random.randint(1, MAP_ROWS - rh - 2)
            new_room = Room(rc, rr, rw, rh)

            if any(new_room.overlaps(r) for r in self.rooms):
                continue

            self._carve_room(new_room)

            if self.rooms:
                cx1, cy1 = new_room.center()
                cx2, cy2 = self.rooms[-1].center()
                self._carve_tunnel(cx1, cy1, cx2, cy2)

            self.rooms.append(new_room)

        # プレイヤーは最初の部屋の中心にスポーン
        if self.rooms:
            cx, cy = self.rooms[0].center()
            self.player_spawn = (cx * TILE + 4, cy * TILE + 4)

        # ★ 0.6: 出口タイルを最後の部屋の中心の1マス下に配置
        if len(self.rooms) >= 2:
            last = self.rooms[-1]
            ex, ey = last.center()
            ex_tile = min(ex + 1, MAP_COLS - 2)
            ey_tile = min(ey + 1, MAP_ROWS - 2)
            if self._tiles[ey_tile][ex_tile] == TILE_FLOOR:
                self._tiles[ey_tile][ex_tile] = TILE_EXIT

        # 封印の欠片候補地点。表示や取得可否は game.py 側の story_flags で制御する。
        if len(self.rooms) >= 2:
            target_room = self.rooms[-1]
            fx, fy = target_room.center()
            if self._tiles[fy][fx] == TILE_FLOOR:
                self._tiles[fy][fx] = TILE_FRAGMENT

    # ──────────────────────────────────────────────────────
    #  町生成（★ 0.6 新規、town 用）
    # ──────────────────────────────────────────────────────
    def _generate_town(self):
        """
        固定レイアウトの町マップを生成する。
        シンプルな広間1部屋に出口タイルを配置する。
        将来はNPC・建物の内部なども追加できる構造にしている。
        """
        # 全体を壁で埋める
        self._tiles = [[TILE_WALL] * MAP_COLS for _ in range(MAP_ROWS)]

        # ── 中央に大きな広間を作る（町の広場）
        # マップ全体の中央に、余白2タイルを残して広間を掘る
        margin     = 3   # 端からの壁厚
        town_col   = margin
        town_row   = margin
        town_w     = MAP_COLS - margin * 2
        town_h     = MAP_ROWS - margin * 2

        town_room = Room(town_col, town_row, town_w, town_h)
        self._carve_room(town_room)
        self.rooms.append(town_room)

        # ── プレイヤーは広間の中央左よりにスポーン
        px = (town_col + 2) * TILE + 4
        py = (town_row + town_h // 2) * TILE + 4
        self.player_spawn = (px, py)

        # ── 出口タイルを広間の右端中央に配置
        # 「草原へ」向かう出口として右端に設ける
        exit_col = town_col + town_w - 2   # 広間右端から2マス内側
        exit_row = town_row + town_h // 2  # 広間の縦中央
        self._tiles[exit_row][exit_col] = TILE_EXIT

        # 北の道へ向かう出口。解放前は game.py 側で遷移を止める。
        north_exit_col = town_col + town_w // 2
        north_exit_row = town_row
        self._tiles[north_exit_row][north_exit_col] = TILE_EXIT

        # ── ★ 0.7: NPC（謎の老人）のタイル座標を記録
        # プレイヤーの正面（右側2〜3マス先）に立たせる
        # プレイヤーは広間左寄り（col+2, row+h//2）なので
        # NPC は少し右の中央あたりに配置する
        npc_col = town_col + town_w // 2   # 広間の横中央
        npc_row = town_row + town_h // 2   # 広間の縦中央
        self._npc_tile_positions.append((npc_col, npc_row))

    def _generate_north_road(self):
        """ルミナ村の北へ続く小規模な道マップを生成する。"""
        self._tiles = [[TILE_WALL] * MAP_COLS for _ in range(MAP_ROWS)]

        road_col = MAP_COLS // 2 - 3
        road_row = 2
        road_w = 7
        road_h = MAP_ROWS - 4

        road_room = Room(road_col, road_row, road_w, road_h)
        self._carve_room(road_room)
        self.rooms.append(road_room)

        # 村から入ってきた位置。南側の戻り口近くに置く。
        self.player_spawn = ((MAP_COLS // 2) * TILE + 4, (MAP_ROWS - 4) * TILE + 4)

        # town へ戻る出口。
        south_exit_col = MAP_COLS // 2
        south_exit_row = MAP_ROWS - 3
        self._tiles[south_exit_row][south_exit_col] = TILE_EXIT

        # 北側は古い祠へ続く方向を床で示すだけに留める。
        for row in range(1, road_row):
            self._tiles[row][south_exit_col] = TILE_FLOOR

        # 奥に古い祠の入口を置く。内部マップへの遷移はまだ作らない。
        shrine_col = south_exit_col
        shrine_row = 1
        self._tiles[shrine_row][shrine_col] = TILE_SHRINE

    def _generate_shrine_inner(self):
        """古い祠内部の小規模な固定マップを生成する。"""
        self._tiles = [[TILE_WALL] * MAP_COLS for _ in range(MAP_ROWS)]

        room_col = MAP_COLS // 2 - 5
        room_row = 2
        room_w = 11
        room_h = 10

        for row in range(room_row, room_row + room_h):
            for col in range(room_col, room_col + room_w):
                self._tiles[row][col] = TILE_FLOOR

        # 古い柱。壁として置き、内部の雰囲気と進路の輪郭を作る。
        for col, row in (
            (room_col + 2, room_row + 3),
            (room_col + room_w - 3, room_row + 3),
            (room_col + 2, room_row + room_h - 4),
            (room_col + room_w - 3, room_row + room_h - 4),
        ):
            self._tiles[row][col] = TILE_WALL

        altar_col = room_col + room_w // 2
        altar_row = room_row + 1
        self._tiles[altar_row][altar_col] = TILE_ALTAR

        exit_col = room_col + room_w // 2
        exit_row = room_row + room_h - 1
        self._tiles[exit_row][exit_col] = TILE_EXIT
        self.player_spawn = (exit_col * TILE + 4, (exit_row - 1) * TILE + 4)

    # ──────────────────────────────────────────────────────
    #  部屋・通路の掘削ヘルパー（変更なし）
    # ──────────────────────────────────────────────────────
    def _carve_room(self, room: Room):
        for r in range(room.row, room.row + room.h):
            for c in range(room.col, room.col + room.w):
                if 0 <= r < MAP_ROWS and 0 <= c < MAP_COLS:
                    self._tiles[r][c] = TILE_FLOOR

    def _carve_tunnel(self, c1: int, r1: int, c2: int, r2: int):
        if random.random() < 0.5:
            self._carve_h(c1, c2, r1)
            self._carve_v(r1, r2, c2)
        else:
            self._carve_v(r1, r2, c1)
            self._carve_h(c1, c2, r2)

    def _carve_h(self, c1: int, c2: int, r: int):
        for c in range(min(c1, c2), max(c1, c2) + 1):
            if 0 <= r < MAP_ROWS and 0 <= c < MAP_COLS:
                self._tiles[r][c] = TILE_FLOOR

    def _carve_v(self, r1: int, r2: int, c: int):
        for r in range(min(r1, r2), max(r1, r2) + 1):
            if 0 <= r < MAP_ROWS and 0 <= c < MAP_COLS:
                self._tiles[r][c] = TILE_FLOOR

    # ──────────────────────────────────────────────────────
    #  描画キャッシュ（★ 0.6: floor_color / wall_color を使用）
    # ──────────────────────────────────────────────────────
    def _build_surface(self):
        """
        マップ全体を1枚のサーフェスに焼き付ける（高速描画用）。
        ゾーンの floor_color / wall_color を使って色を変える。
        出口タイル（TILE_EXIT）は床と同じ色で描画し、
        draw() で上から C_EXIT_TILE の色を重ね描きする。
        """
        surf = pygame.Surface((MAP_COLS * TILE, MAP_ROWS * TILE))
        surf.fill(self.wall_color)

        fc = self.floor_color   # 床色（ゾーンごとに異なる）
        wc = self.wall_color    # 壁色

        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                px = c * TILE
                py = r * TILE

                if tile in (TILE_FLOOR, TILE_EXIT, TILE_SHRINE, TILE_FRAGMENT, TILE_ALTAR):
                    # 床（出口も床として下地を描く）
                    shade = random.randint(-5, 5)
                    col   = tuple(max(0, min(255, v + shade)) for v in fc)
                    pygame.draw.rect(surf, col, (px, py, TILE, TILE))
                    pygame.draw.rect(surf, C_GRID, (px, py, TILE, TILE), 1)
                else:
                    # 壁：立体感を出す
                    pygame.draw.rect(surf, wc, (px, py, TILE, TILE))
                    highlight = tuple(min(255, v + 18) for v in wc)
                    shadow    = tuple(max(0,   v - 10) for v in wc)
                    pygame.draw.line(surf, highlight,
                                     (px, py), (px + TILE - 1, py), 1)
                    pygame.draw.line(surf, shadow,
                                     (px, py + TILE - 1),
                                     (px + TILE - 1, py + TILE - 1), 1)

        self._map_surface = surf

    # ──────────────────────────────────────────────────────
    #  壁の当たり判定リスト（変更なし）
    # ──────────────────────────────────────────────────────
    def _build_wall_rects(self):
        """壁タイルの pygame.Rect リストを作る（当たり判定用）"""
        self.wall_rects = []
        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                if tile == TILE_WALL:
                    self.wall_rects.append(
                        pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                    )

    # ──────────────────────────────────────────────────────
    #  出口タイルの当たり判定リスト（★ 0.6 新規）
    # ──────────────────────────────────────────────────────
    def _build_exit_rects(self):
        """
        出口タイル（TILE_EXIT）の pygame.Rect リストを作る。
        game.py がプレイヤーとの衝突判定に使う。

        戻り値はなし。self.exit_rects に格納する。
        """
        self.exit_rects = []
        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                if tile == TILE_EXIT:
                    self.exit_rects.append(
                        pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                    )

    def _build_shrine_rects(self):
        """古い祠の入口イベント地点の Rect リストを作る。"""
        self.shrine_rects = []
        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                if tile == TILE_SHRINE:
                    self.shrine_rects.append(
                        pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                    )

    def _build_fragment_rects(self):
        """封印の欠片イベント地点の Rect リストを作る。"""
        self.fragment_rects = []
        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                if tile == TILE_FRAGMENT:
                    self.fragment_rects.append(
                        pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                    )

    def _build_altar_rects(self):
        """祠内部の祭壇地点の Rect リストを作る。"""
        self.altar_rects = []
        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                if tile == TILE_ALTAR:
                    self.altar_rects.append(
                        pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                    )

    # ──────────────────────────────────────────────────────
    #  NPC スポーン位置の構築（★ 0.7 新規）
    # ──────────────────────────────────────────────────────
    def _build_npc_spawns(self):
        """
        _npc_tile_positions（タイル座標）を
        ピクセル座標に変換して self.npc_spawns に格納する。

        town 以外（field など）では _npc_tile_positions が空なので
        npc_spawns も空リストになる。
        """
        self.npc_spawns = [
            (col * TILE + 4, row * TILE + 4)
            for col, row in self._npc_tile_positions
        ]

    # ──────────────────────────────────────────────────────
    #  NPC スポーン位置を返す（★ 0.7 新規）
    # ──────────────────────────────────────────────────────
    def get_npc_spawns(self) -> list[tuple[int, int]]:
        """
        NPC を配置するピクセル座標のリストを返す。

        戻り値:
            list[tuple[int, int]] :
                town の場合 → [(x, y)]  1件（謎の老人の座標）
                field の場合 → []       （NPC なし）

        使用例（game.py 側）:
            for (x, y) in self.world.get_npc_spawns():
                self.npcs.append(
                    NPC(x, y,
                        name="謎の老人",
                        dialogue_id="elder_first",
                        repeat_dialogue_id="elder_repeat")
                )
        """
        return list(self.npc_spawns)  # コピーを返してリスト保護

    # ──────────────────────────────────────────────────────
    #  敵のスポーン位置（★ 0.6: has_enemies=False なら空リスト）
    # ──────────────────────────────────────────────────────
    def get_enemy_spawns(self, count: int) -> list[tuple[int, int]]:
        """
        敵を配置するピクセル座標のリストを返す。

        ★ 0.6 変更点:
            has_enemies が False（町など）の場合は即 [] を返す。
            game.py は戻り値が空でも壊れない設計のまま。

        引数:
            count : 欲しいスポーン位置の数

        戻り値:
            [(x, y), ...]  has_enemies=False のときは []
        """
        # ★ 0.6: 敵なしゾーンは空リストを返す
        if not self.has_enemies:
            return []

        # 以下は 0.5 以前と変更なし
        available = self.rooms[1:] if len(self.rooms) > 1 else self.rooms
        selected  = random.sample(available, min(count, len(available)))
        result    = []
        for room in selected:
            cx, cy = room.center()
            result.append((cx * TILE + 4, cy * TILE + 4))
        return result

    # ──────────────────────────────────────────────────────
    #  描画（★ 0.6: 出口タイルを重ね描き）
    # ──────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface, shrine_seal_reacted: bool = False):
        """
        キャッシュしたサーフェスを貼り付け、
        その上に出口タイルをくすんだゴールドで重ね描きする。
        毎フレーム呼ぶ。
        """
        # 1) マップ下地（キャッシュ済み）
        if self._map_surface:
            surface.blit(self._map_surface, (0, 0))

        # 2) ★ 0.6: 出口タイルを上から描画
        for rect in self.exit_rects:
            pygame.draw.rect(surface, C_EXIT_TILE, rect)
            # 枠線で目立たせる
            pygame.draw.rect(surface, (200, 180, 80), rect, 2)

        for rect in self.shrine_rects:
            if shrine_seal_reacted:
                pygame.draw.rect(surface, (42, 38, 52), rect)
                pygame.draw.rect(surface, (110, 160, 180), rect, 2)
                passage = rect.inflate(-TILE // 3, -TILE // 4)
                pygame.draw.rect(surface, (18, 16, 26), passage)
                pygame.draw.line(surface, (105, 190, 210), rect.midtop, rect.center, 1)
            else:
                pygame.draw.rect(surface, (68, 68, 86), rect)
                pygame.draw.rect(surface, (155, 150, 180), rect, 2)
                pygame.draw.line(surface, (205, 200, 230), rect.midtop, rect.center, 2)

        for rect in self.altar_rects:
            pygame.draw.rect(surface, (64, 58, 78), rect)
            pygame.draw.rect(surface, (150, 145, 175), rect, 2)
            glow_rect = rect.inflate(-TILE // 3, -TILE // 3)
            pygame.draw.rect(surface, (110, 165, 185), glow_rect, 1)
