"""
============================================================
  core/sprite_manager.py  ── スプライト（画像）管理  [0.3 新規]

  担当:
    - PNG 画像ファイルを読み込んで保持する
    - 画像がない場合は None を返す（呼び出し側で図形描画に切り替える）
    - 画像のスケーリング（リサイズ）を行う
    - 将来の画像追加が簡単にできる構造

  画像ファイルの置き場所:
    singularity_proto_01/
    └── assets/
        └── images/
            ├── player_novice_m.png   ← プレイヤー（男）
            ├── player_novice_f.png   ← プレイヤー（女）※将来用
            ├── slime_fire.png        ← 火スライム
            ├── slime_water.png       ← 水スライム ※将来用
            ├── slime_wind.png        ← 風スライム ※将来用
            ├── slime_earth.png       ← 土スライム ※将来用
            ├── slime_light.png       ← 光スライム ※将来用
            └── slime_dark.png        ← 闇スライム ※将来用

  使い方:
    sm = SpriteManager()
    # スプライトを取得（なければ None）
    img = sm.get_player("novice_m", size=(48, 48))
    img = sm.get_enemy("火スライム", size=(80, 80))

    # 描画側（None チェックを忘れずに）
    if img:
        surface.blit(img, (x, y))
    else:
        pygame.draw.circle(...)  # フォールバック描画
============================================================
"""

import pygame
import pathlib


# ── 画像ファイルパスのマッピング ────────────────────────
# ★ 新しいキャラを追加するときはここに追記するだけ！

# プレイヤー: キー = "識別子"  値 = "ファイル名（拡張子なし）"
PLAYER_SPRITE_MAP: dict[str, str] = {
    "novice_m"  : "player_novice_m",   # ノービス（男）
    "novice_f"  : "player_novice_f",   # ノービス（女）※将来用
    # ジョブを追加するときはここに追記
    # "warrior_m" : "player_warrior_m",
    # "mage_m"    : "player_mage_m",
}

# 敵: キー = "スライムの名前（constants.py の name と一致させる）"
ENEMY_SPRITE_MAP: dict[str, str] = {
    "火スライム" : "slime_fire",
    "水スライム" : "slime_water",
    "風スライム" : "slime_wind",
    "土スライム" : "slime_earth",
    "光スライム" : "slime_light",
    "闇スライム" : "slime_dark",
    # 新しい敵を追加するときはここに追記するだけ
}


class SpriteManager:
    """
    スプライト画像を読み込んで管理するクラス。

    内部キャッシュ（_cache）に一度読んだ画像を保持し、
    同じ画像を何度もディスクから読まないようにする。
    """

    def __init__(self, base_dir: str = "."):
        """
        base_dir: プロジェクトのルートフォルダ（main.py があるフォルダ）
        """
        # 画像フォルダのパス
        self.image_dir = pathlib.Path(base_dir) / "assets" / "images"

        # 読み込んだ画像を入れる辞書（キャッシュ）
        # キー = "ファイル名（拡張子なし）"  値 = pygame.Surface
        self._cache: dict[str, pygame.Surface] = {}

        # 読み込み試行を記録（失敗したファイルを再試行しないため）
        self._failed: set[str] = set()

        print(f"[SpriteManager] 画像フォルダ: {self.image_dir.resolve()}")
        self._preload()

    def _preload(self):
        """
        起動時に全画像を先読みする。
        ファイルが無くてもエラーにせず、ログだけ出す。
        """
        all_keys = list(PLAYER_SPRITE_MAP.values()) + list(ENEMY_SPRITE_MAP.values())
        for filename in all_keys:
            self._load(filename)

    def _load(self, filename: str) -> pygame.Surface | None:
        """
        指定ファイル名（拡張子なし）の PNG を読み込む。
        成功: Surface を返す
        失敗: None を返す（エラーは出さない）
        """
        # キャッシュに既にあればそれを返す
        if filename in self._cache:
            return self._cache[filename]

        # 失敗済みならスキップ
        if filename in self._failed:
            return None

        path = self.image_dir / f"{filename}.png"
        try:
            img = pygame.image.load(str(path)).convert_alpha()
            self._cache[filename] = img
            print(f"[SpriteManager]  OK: {path.name}")
            return img
        except Exception as e:
            self._failed.add(filename)
            print(f"[SpriteManager]  NG: {path.name}  ({e})")
            return None

    def _get_scaled(self, filename: str,
                    size: tuple[int, int]) -> pygame.Surface | None:
        """
        指定サイズにリサイズした Surface を返す。
        ファイルがなければ None を返す。
        """
        img = self._load(filename)
        if img is None:
            return None

        # キャッシュキーにサイズも含める（異なるサイズを両立）
        cache_key = f"{filename}_{size[0]}x{size[1]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        scaled = pygame.transform.scale(img, size)
        self._cache[cache_key] = scaled
        return scaled

    # ──────────────────────────────────────────────────────
    #  公開 API
    # ──────────────────────────────────────────────────────
    def get_player(self, key: str = "novice_m",
                   size: tuple[int, int] = (48, 48)) -> pygame.Surface | None:
        """
        プレイヤースプライトを返す。
        key  : PLAYER_SPRITE_MAP のキー（デフォルト "novice_m"）
        size : 表示サイズ（ピクセル）

        戻り値:
            pygame.Surface : 読み込み成功
            None           : ファイルがない → 呼び出し側で図形描画に切り替える
        """
        filename = PLAYER_SPRITE_MAP.get(key)
        if filename is None:
            return None
        return self._get_scaled(filename, size)

    def get_enemy(self, name: str,
                  size: tuple[int, int] = (80, 80)) -> pygame.Surface | None:
        """
        敵スプライトを enemy.name で取得する。
        name : ENEMY_SPRITE_MAP のキー（"火スライム" など）
        size : 表示サイズ（ピクセル）

        戻り値:
            pygame.Surface : 読み込み成功
            None           : ファイルがない → 呼び出し側で図形描画に切り替える
        """
        filename = ENEMY_SPRITE_MAP.get(name)
        if filename is None:
            return None
        return self._get_scaled(filename, size)

    def has_player(self, key: str = "novice_m") -> bool:
        """プレイヤー画像が存在するか確認する"""
        filename = PLAYER_SPRITE_MAP.get(key)
        return filename is not None and filename not in self._failed

    def has_enemy(self, name: str) -> bool:
        """敵画像が存在するか確認する"""
        filename = ENEMY_SPRITE_MAP.get(name)
        return filename is not None and filename not in self._failed

    def reload(self):
        """画像キャッシュを全クリアして再読み込みする（デバッグ用）"""
        self._cache.clear()
        self._failed.clear()
        self._preload()
