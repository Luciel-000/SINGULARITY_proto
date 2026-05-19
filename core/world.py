"""
============================================================
  core/world.py  ── マップ生成・描画クラス

  ローグライク風の「部屋 + 通路」マップを自動生成します。
  タイルデータ：0 = 床、1 = 壁

  初心者向けメモ：
    - _generate() でランダムにマップを作る
    - _build_surface() で一枚絵に焼き付けて高速描画
    - wall_rects が当たり判定用の壁リスト
============================================================
"""

import pygame
import random
from .constants import (
    TILE, WINDOW_W, GAME_AREA_H,
    C_FLOOR, C_WALL, C_GRID,
)

# マップのタイル数（画面サイズ ÷ タイルサイズ）
MAP_COLS = WINDOW_W   // TILE   # 横方向のタイル数
MAP_ROWS = GAME_AREA_H // TILE  # 縦方向のタイル数


class Room:
    """マップ内の1つの部屋を表すデータクラス"""

    def __init__(self, col: int, row: int, w: int, h: int):
        self.col = col  # 左端のタイル列
        self.row = row  # 上端のタイル行
        self.w   = w    # 横幅（タイル数）
        self.h   = h    # 縦幅（タイル数）

    def center(self) -> tuple[int, int]:
        """部屋の中心タイル座標を返す"""
        return (self.col + self.w // 2, self.row + self.h // 2)

    def overlaps(self, other: "Room", margin: int = 1) -> bool:
        """別の部屋と重なっているか確認する（margin で余白を設定）"""
        return (
            self.col - margin < other.col + other.w and
            self.col + self.w + margin > other.col and
            self.row - margin < other.row + other.h and
            self.row + self.h + margin > other.row
        )


class World:
    """
    ゲームマップ全体を管理するクラス。

    属性:
        wall_rects    : 壁の pygame.Rect リスト（当たり判定用）
        rooms         : 部屋のリスト（敵のスポーン位置に使う）
        player_spawn  : プレイヤーの初期位置（ピクセル座標）
    """

    def __init__(self):
        # タイルデータ（2次元リスト）：0=床、1=壁
        self._tiles: list[list[int]] = []

        # 描画用キャッシュサーフェス（一度だけ作成する）
        self._map_surface: pygame.Surface | None = None

        # 当たり判定用の壁 Rect リスト
        self.wall_rects: list[pygame.Rect] = []

        # 部屋のリスト
        self.rooms: list[Room] = []

        # プレイヤーの初期スポーン位置（ピクセル）
        self.player_spawn: tuple[int, int] = (TILE * 2 + 4, TILE * 2 + 4)

        # マップを生成して各データを構築する
        self._generate()
        self._build_surface()
        self._build_wall_rects()

    # ──────────────────────────────────────────────────────
    #  マップ生成
    # ──────────────────────────────────────────────────────
    def _generate(self):
        """
        ランダムなダンジョンマップを生成する。
        アルゴリズム：
          1. 全体を壁で埋める
          2. ランダムに部屋を配置する（重なり排除）
          3. 隣の部屋とL字型の通路でつなぐ
        """
        # 全体を壁（1）で埋める
        self._tiles = [[1] * MAP_COLS for _ in range(MAP_ROWS)]

        # ★ 部屋の数と大きさを変えたいときはここを調整
        MAX_ATTEMPTS = 25    # 部屋を置こうとする最大試行回数
        MIN_ROOM_W   = 4     # 部屋の最小横幅（タイル）
        MAX_ROOM_W   = 10    # 部屋の最大横幅
        MIN_ROOM_H   = 4     # 部屋の最小縦幅
        MAX_ROOM_H   = 8     # 部屋の最大縦幅

        for _ in range(MAX_ATTEMPTS):
            # ランダムなサイズと位置で部屋を作る
            rw = random.randint(MIN_ROOM_W, MAX_ROOM_W)
            rh = random.randint(MIN_ROOM_H, MAX_ROOM_H)
            rc = random.randint(1, MAP_COLS - rw - 2)
            rr = random.randint(1, MAP_ROWS - rh - 2)
            new_room = Room(rc, rr, rw, rh)

            # 既存の部屋と重なっていたらスキップ
            if any(new_room.overlaps(r) for r in self.rooms):
                continue

            # 床として掘り込む
            self._carve_room(new_room)

            # 2部屋目以降は前の部屋と通路でつなぐ
            if self.rooms:
                cx1, cy1 = new_room.center()
                cx2, cy2 = self.rooms[-1].center()
                self._carve_tunnel(cx1, cy1, cx2, cy2)

            self.rooms.append(new_room)

        # ★ プレイヤーは最初の部屋の中心にスポーン
        if self.rooms:
            cx, cy = self.rooms[0].center()
            self.player_spawn = (cx * TILE + 4, cy * TILE + 4)

    def _carve_room(self, room: Room):
        """部屋の内側を床（0）にする"""
        for r in range(room.row, room.row + room.h):
            for c in range(room.col, room.col + room.w):
                if 0 <= r < MAP_ROWS and 0 <= c < MAP_COLS:
                    self._tiles[r][c] = 0  # 床に変える

    def _carve_tunnel(self, c1: int, r1: int, c2: int, r2: int):
        """
        2点間を L 字型の通路でつなぐ。
        ランダムに水平→垂直 か 垂直→水平 を選ぶ。
        """
        if random.random() < 0.5:
            self._carve_h(c1, c2, r1)   # まず横に掘る
            self._carve_v(r1, r2, c2)   # 次に縦に掘る
        else:
            self._carve_v(r1, r2, c1)   # まず縦に掘る
            self._carve_h(c1, c2, r2)   # 次に横に掘る

    def _carve_h(self, c1: int, c2: int, r: int):
        """水平方向に通路を掘る"""
        for c in range(min(c1, c2), max(c1, c2) + 1):
            if 0 <= r < MAP_ROWS and 0 <= c < MAP_COLS:
                self._tiles[r][c] = 0

    def _carve_v(self, r1: int, r2: int, c: int):
        """垂直方向に通路を掘る"""
        for r in range(min(r1, r2), max(r1, r2) + 1):
            if 0 <= r < MAP_ROWS and 0 <= c < MAP_COLS:
                self._tiles[r][c] = 0

    # ──────────────────────────────────────────────────────
    #  描画キャッシュ（高速化）
    # ──────────────────────────────────────────────────────
    def _build_surface(self):
        """
        マップ全体を1枚のサーフェスに焼き付ける。
        毎フレーム個々のタイルを描くより大幅に高速になる。
        """
        surf = pygame.Surface((MAP_COLS * TILE, MAP_ROWS * TILE))
        surf.fill(C_WALL)

        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                px = c * TILE
                py = r * TILE

                if tile == 0:
                    # 床：微妙なランダム明暗でリアルに見せる
                    shade = random.randint(-5, 5)
                    col = tuple(max(0, min(255, v + shade)) for v in C_FLOOR)
                    pygame.draw.rect(surf, col, (px, py, TILE, TILE))
                    # 薄いグリッド線
                    pygame.draw.rect(surf, C_GRID, (px, py, TILE, TILE), 1)
                else:
                    # 壁：上端と下端に明暗をつけて立体感を出す
                    pygame.draw.rect(surf, C_WALL, (px, py, TILE, TILE))
                    highlight = tuple(min(255, v + 18) for v in C_WALL)
                    shadow    = tuple(max(0,   v - 10) for v in C_WALL)
                    pygame.draw.line(surf, highlight, (px, py),          (px + TILE - 1, py),          1)
                    pygame.draw.line(surf, shadow,    (px, py + TILE - 1),(px + TILE - 1, py + TILE - 1), 1)

        self._map_surface = surf

    # ──────────────────────────────────────────────────────
    #  壁の当たり判定リスト構築
    # ──────────────────────────────────────────────────────
    def _build_wall_rects(self):
        """壁タイルの pygame.Rect リストを作る（当たり判定用）"""
        self.wall_rects = []
        for r, row in enumerate(self._tiles):
            for c, tile in enumerate(row):
                if tile == 1:  # 壁タイルのみ追加
                    self.wall_rects.append(
                        pygame.Rect(c * TILE, r * TILE, TILE, TILE)
                    )

    # ──────────────────────────────────────────────────────
    #  敵のスポーン位置を返す
    # ──────────────────────────────────────────────────────
    def get_enemy_spawns(self, count: int) -> list[tuple[int, int]]:
        """
        敵を配置する位置（ピクセル座標）を返す。
        最初の部屋（プレイヤー部屋）は除いて、残りの部屋から選ぶ。

        引数:
            count: 欲しいスポーン位置の数
        戻り値:
            [(x, y), ...] のリスト
        """
        available = self.rooms[1:] if len(self.rooms) > 1 else self.rooms
        selected  = random.sample(available, min(count, len(available)))
        result    = []
        for room in selected:
            cx, cy = room.center()
            result.append((cx * TILE + 4, cy * TILE + 4))
        return result

    # ──────────────────────────────────────────────────────
    #  描画
    # ──────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface):
        """
        キャッシュしたサーフェスをそのまま貼り付ける（高速）。
        毎フレーム呼ぶ。
        """
        if self._map_surface:
            surface.blit(self._map_surface, (0, 0))
