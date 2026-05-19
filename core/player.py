"""
============================================================
  core/player.py  ── プレイヤー「ノービス」クラス  [0.3 更新]

  [0.3 変更点]
    - draw()        : スプライト画像に対応（なければ図形描画）
    - draw_battle() : バトル画面用の大きなスプライト描画に対応
    - SpriteManager を外部から受け取って使う設計

  担当機能（変更なし）:
    - WASD / 矢印キーで移動
    - HP・攻撃力・防御力の管理
    - 経験値獲得とレベルアップ
============================================================
"""

import pygame
import math
from .constants import (
    TILE, PLAYER_SPEED, PLAYER_ATTACK_CD,
    GAME_AREA_H, WINDOW_W,
    C_WHITE, C_GOLD, C_CRIMSON_LT, C_DARK_GRAY, C_DARK_BG,
    EXP_TABLE,
)


class Player:
    """
    プレイヤーキャラクター「ノービス」

    使い方:
        player = Player(x=100, y=100)
        player.update(walls)                      # 毎フレーム
        player.draw(surface, sprite_manager)      # 探索マップ描画
        player.draw_battle(surface, px, py, ...)  # バトル画面描画
    """

    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x, y, TILE - 4, TILE - 4)

        # ── ステータス
        self.level   = 1
        self.max_hp  = 30
        self.hp      = 30
        self.atk     = 8
        self.defense = 2
        self.exp     = 0

        # ── タイマー類
        self.attack_cd           = 0
        self.attack_effect_timer = 0
        self.hit_timer           = 0
        self.levelup_timer       = 0

        # ── 向き・アニメ
        self.direction = "right"
        self.attack_rect: pygame.Rect | None = None
        self.trail: list[tuple[int, int, int]] = []

        # ── スプライトキー（ジョブ切り替えに使う）
        # ★ 将来ジョブを増やすときはここを変えるだけ
        self.sprite_key = "novice_m"

    # ──────────────────────────────────────────────────────
    #  更新（変更なし）
    # ──────────────────────────────────────────────────────
    def update(self, walls: list[pygame.Rect]):
        keys = pygame.key.get_pressed()
        vx, vy = 0, 0

        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: vx = -PLAYER_SPEED; self.direction = "left"
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: vx =  PLAYER_SPEED; self.direction = "right"
        if keys[pygame.K_UP]    or keys[pygame.K_w]: vy = -PLAYER_SPEED
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: vy =  PLAYER_SPEED

        if vx != 0 and vy != 0:
            vx = int(vx * 0.707)
            vy = int(vy * 0.707)

        self.rect.x += vx
        for wall in walls:
            if self.rect.colliderect(wall):
                if vx > 0: self.rect.right = wall.left
                else:      self.rect.left  = wall.right

        self.rect.y += vy
        for wall in walls:
            if self.rect.colliderect(wall):
                if vy > 0: self.rect.bottom = wall.top
                else:      self.rect.top    = wall.bottom

        self.rect.clamp_ip(pygame.Rect(0, 0, WINDOW_W, GAME_AREA_H))

        if vx != 0 or vy != 0:
            self.trail.append((self.rect.centerx, self.rect.centery, 160))
        self.trail = [(x, y, a - 18) for x, y, a in self.trail if a > 0]

        if self.attack_cd           > 0: self.attack_cd           -= 1
        if self.hit_timer           > 0: self.hit_timer           -= 1
        if self.attack_effect_timer > 0: self.attack_effect_timer -= 1
        if self.levelup_timer       > 0: self.levelup_timer       -= 1
        if self.attack_effect_timer <= 0: self.attack_rect = None

    # ──────────────────────────────────────────────────────
    #  攻撃・ダメージ・EXP（変更なし）
    # ──────────────────────────────────────────────────────
    def try_attack(self) -> bool:
        if self.attack_cd > 0:
            return False
        attack_w = TILE + 8
        ax = self.rect.right if self.direction == "right" else self.rect.left - attack_w
        self.attack_rect         = pygame.Rect(ax, self.rect.top, attack_w, self.rect.height)
        self.attack_cd           = PLAYER_ATTACK_CD
        self.attack_effect_timer = 10
        return True

    def take_damage(self, amount: int) -> int:
        dmg = max(1, amount - self.defense)
        self.hp = max(0, self.hp - dmg)
        self.hit_timer = 20
        return dmg

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0

    def gain_exp(self, amount: int) -> bool:
        self.exp += amount
        if self.level < len(EXP_TABLE) - 1:
            if self.exp >= EXP_TABLE[self.level]:
                self._do_level_up()
                return True
        return False

    def _do_level_up(self):
        self.level   += 1
        self.max_hp  += 8
        self.hp       = self.max_hp
        self.atk     += 3
        self.defense += 1
        self.levelup_timer = 90

    def exp_to_next(self) -> int:
        if self.level >= len(EXP_TABLE) - 1:
            return 0
        return EXP_TABLE[self.level] - self.exp

    def exp_progress(self) -> float:
        if self.level >= len(EXP_TABLE) - 1:
            return 1.0
        prev = EXP_TABLE[self.level - 1]
        nxt  = EXP_TABLE[self.level]
        return (self.exp - prev) / max(1, nxt - prev)

    # ──────────────────────────────────────────────────────
    #  探索マップ描画（スプライト対応）
    # ──────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface, sprite_mgr=None):
        """
        探索マップ上のプレイヤーを描く。
        sprite_mgr が渡されて画像があれば PNG を使う。
        なければ今まで通りの図形描画にフォールバック。
        """
        # 足跡エフェクト
        for tx, ty, alpha in self.trail:
            s = pygame.Surface((6, 6), pygame.SRCALPHA)
            s.fill((*C_GOLD, max(0, min(255, int(alpha)))))
            surface.blit(s, (tx - 3, ty - 3))

        # ── スプライト描画を試みる
        img = None
        if sprite_mgr is not None:
            # 探索マップ用サイズ（タイルサイズ相当）
            img = sprite_mgr.get_player(self.sprite_key,
                                         size=(self.rect.width, self.rect.height))

        if img is not None:
            # PNG がある場合：画像を表示
            # ダメージ中は赤く着色（Surface をコピーして赤を重ねる）
            if self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0:
                img = img.copy()
                red = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                red.fill((220, 60, 60, 140))
                img.blit(red, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            # 左向きのときは水平反転
            if self.direction == "left":
                img = pygame.transform.flip(img, True, False)

            surface.blit(img, (self.rect.x, self.rect.y))

        else:
            # PNG がない場合：図形で描く（フォールバック）
            body_color = C_CRIMSON_LT if (self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0) else C_WHITE
            pygame.draw.rect(surface, body_color, self.rect, border_radius=5)
            head_cx, head_cy = self.rect.centerx, self.rect.top + 8
            pygame.draw.circle(surface, body_color, (head_cx, head_cy), 7)
            eye_dx = 3 if self.direction == "right" else -3
            pygame.draw.circle(surface, C_DARK_BG, (head_cx + eye_dx, head_cy - 1), 2)
            sx, ex = (self.rect.right - 2, self.rect.right + 10) if self.direction == "right" \
                else (self.rect.left + 2, self.rect.left - 10)
            pygame.draw.line(surface, C_GOLD, (sx, self.rect.centery), (ex, self.rect.centery - 6), 2)

        # 攻撃エフェクト（スプライト有無に関わらず表示）
        if self.attack_rect and self.attack_effect_timer > 0:
            alpha = int(self.attack_effect_timer / 10 * 160)
            s = pygame.Surface((self.attack_rect.width, self.attack_rect.height), pygame.SRCALPHA)
            s.fill((*C_GOLD, alpha))
            surface.blit(s, (self.attack_rect.x, self.attack_rect.y))

        # HP バー（頭上）
        bar_w = self.rect.width
        ratio = max(0.0, self.hp / self.max_hp)
        pygame.draw.rect(surface, (40, 10, 10), (self.rect.x, self.rect.top - 8, bar_w, 4))
        pygame.draw.rect(surface, C_CRIMSON_LT, (self.rect.x, self.rect.top - 8, int(bar_w * ratio), 4))

    # ──────────────────────────────────────────────────────
    #  バトル画面描画（スプライト対応）
    # ──────────────────────────────────────────────────────
    def draw_battle(self, surface: pygame.Surface,
                    px: int, py: int,
                    font_md: pygame.font.Font,
                    font_sm: pygame.font.Font,
                    sprite_mgr=None):
        """
        バトル画面用の大きなプレイヤーを描く。
        px, py: 表示中心座標（PLAYER_BATTLE_X, PLAYER_BATTLE_Y）
        sprite_mgr: SpriteManager（省略可）

        スプライトがある場合はPNG、ない場合は図形でフォールバック。
        """
        # ── スプライト描画を試みる（バトル用の大きいサイズ）
        BATTLE_SIZE = (96, 96)   # ★ バトル画面でのプレイヤーサイズ
        img = None
        if sprite_mgr is not None:
            img = sprite_mgr.get_player(self.sprite_key, size=BATTLE_SIZE)

        if img is not None:
            # PNG がある場合
            draw_img = img

            # ダメージ点滅
            if self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0:
                draw_img = img.copy()
                red = pygame.Surface(draw_img.get_size(), pygame.SRCALPHA)
                red.fill((220, 60, 60, 140))
                draw_img.blit(red, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            # 画像の中心を px, py に合わせて表示
            img_rect = draw_img.get_rect(center=(px, py))
            surface.blit(draw_img, img_rect)

            # 影
            sw, sh = BATTLE_SIZE[0], 14
            shadow_s = pygame.Surface((sw, sh), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_s, (0, 0, 0, 55), (0, 0, sw, sh))
            surface.blit(shadow_s, (px - sw // 2, py + BATTLE_SIZE[1] // 2 - 4))

        else:
            # PNG がない場合：図形で描く
            body_color = C_CRIMSON_LT if (self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0) else C_WHITE

            shadow_s = pygame.Surface((70, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_s, (0, 0, 0, 60), (0, 0, 70, 14))
            surface.blit(shadow_s, (px - 35, py + 45))

            body = pygame.Rect(px - 20, py - 10, 40, 55)
            pygame.draw.rect(surface, body_color, body, border_radius=6)
            pygame.draw.circle(surface, body_color, (px, py - 22), 22)
            pygame.draw.circle(surface, (30, 25, 45), (px + 7,  py - 24), 4)
            pygame.draw.circle(surface, (30, 25, 45), (px - 7,  py - 24), 4)
            pygame.draw.circle(surface, (200, 210, 240), (px + 8, py - 25), 2)
            pygame.draw.line(surface, C_GOLD, (px + 22, py - 5), (px + 46, py - 28), 3)
            pygame.draw.line(surface, (180, 140, 60), (px + 28, py), (px + 36, py - 12), 3)

        # 名前ラベル（スプライト有無に関わらず表示）
        name_txt = font_md.render("ノービス", True, C_GOLD)
        surface.blit(name_txt, (px - name_txt.get_width() // 2, py - 70))

        # HP バー
        bar_w = 120
        bar_x = px - bar_w // 2
        bar_y = py + 54
        ratio = max(0.0, self.hp / self.max_hp)
        bc = (50, 210, 80) if ratio > 0.5 else C_CRIMSON_LT
        pygame.draw.rect(surface, (40, 10, 10), (bar_x, bar_y, bar_w, 10), border_radius=4)
        pygame.draw.rect(surface, bc,           (bar_x, bar_y, int(bar_w * ratio), 10), border_radius=4)
        pygame.draw.rect(surface, C_GOLD,       (bar_x, bar_y, bar_w, 10), 1, border_radius=4)
        hp_txt = font_sm.render(f"HP {self.hp}/{self.max_hp}", True, C_WHITE)
        surface.blit(hp_txt, (px - hp_txt.get_width() // 2, bar_y + 13))
