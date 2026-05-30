"""
============================================================
  core/enemy.py  ── 敵「属性スライム」クラス  [0.5 更新]

  [0.5 変更点]
    - self.element を追加（SLIME_ELEMENT から属性IDを取得）
      battle.py が Step8 で属性相性ダメージ計算に使用する予定
    - do_attack() の戻り値は int のまま変更なし（互換維持）
    - 描画・AI・ダメージ処理は変更なし

  [0.3 変更点（継続）]
    - draw()        : スプライト画像に対応（なければ図形描画）
    - draw_battle() : スプライト画像に対応（なければ図形描画）

  担当機能（変更なし）:
    - 探索マップ上の追跡 AI
    - 接触でバトル開始トリガー
    - バトル用ダメージ・攻撃
============================================================
"""

import pygame
import math
import random
from .utils import safe_alpha, make_rgba, lerp_alpha  # ★ 0.3.1: alpha安全変換
from .constants import (
    TILE, ENEMY_SPEED, ENEMY_DETECT_R,
    GAME_AREA_H, WINDOW_W,
    C_WHITE, C_DARK_BG, C_CRIMSON_LT, C_GOLD,
    SLIME_VARIANTS,
    SLIME_ELEMENT,        # ★ 0.5: スライム名 → 属性ID マップ
)


class Enemy:
    def __init__(self, x: int, y: int, variant_index: int = -1):
        self.rect = pygame.Rect(x, y, TILE - 6, TILE - 6)

        idx = variant_index if variant_index >= 0 else random.randint(0, len(SLIME_VARIANTS) - 1)
        name, hp, atk, defense, exp_val, color = SLIME_VARIANTS[idx]

        self.name    = name
        self.max_hp  = hp
        self.hp      = hp
        self.atk     = atk
        self.defense = defense
        self.exp_val = exp_val
        self.color   = color
        self.element = SLIME_ELEMENT.get(self.name, "none")  # ★ 0.5: 属性ID

        self.state       = "idle"
        self.alive       = True
        self.death_timer = 0
        self.anim_t      = random.uniform(0, math.pi * 2)
        self.hit_timer   = 0
        self.float_texts: list[dict] = []

    # ──────────────────────────────────────────────────────
    #  探索マップ更新
    # ──────────────────────────────────────────────────────
    def update(self, player_rect: pygame.Rect, walls: list[pygame.Rect]):
        if not self.alive:
            if self.death_timer > 0: self.death_timer -= 1
            return

        self.anim_t += 0.08
        dx   = player_rect.centerx - self.rect.centerx
        dy   = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        self.state = "chase" if dist < ENEMY_DETECT_R else "idle"

        if self.state == "chase" and dist > 2:
            vx = int(dx / dist * ENEMY_SPEED)
            vy = int(dy / dist * ENEMY_SPEED)
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

        if self.hit_timer > 0: self.hit_timer -= 1
        self.float_texts = [
            {**ft, "y": ft["y"] - 1, "life": ft["life"] - 1}
            for ft in self.float_texts if ft["life"] > 0
        ]

    def touches_player(self, player_rect: pygame.Rect) -> bool:
        return self.alive and self.rect.colliderect(player_rect.inflate(6, 6))

    # ──────────────────────────────────────────────────────
    #  バトル用
    # ──────────────────────────────────────────────────────
    def do_attack(self) -> int:
        return self.atk + random.randint(-1, 2)

    def take_damage(self, amount: int) -> int:
        dmg = max(1, amount - self.defense)
        self.hp -= dmg
        self.hit_timer = 18
        self.float_texts.append({
            "text": str(dmg), "x": 0, "y": 0,
            "life": 50, "color": (255, 220, 60),
        })
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.death_timer = 30
        return dmg

    def reset_for_next_battle(self):
        self.hp = self.max_hp
        self.alive = True
        self.float_texts.clear()

    # ──────────────────────────────────────────────────────
    #  探索マップ描画（スプライト対応）
    # ──────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface,
             font_small: pygame.font.Font,
             sprite_mgr=None):
        """
        探索マップ上のスライムシンボルを描く。
        sprite_mgr が渡されて画像があれば PNG を使う。
        """
        if not self.alive:
            if self.death_timer > 0:
                self._draw_death_effect(surface)
            return

        # ── スプライト描画を試みる（タイルサイズ）
        img = None
        if sprite_mgr is not None:
            img = sprite_mgr.get_enemy(self.name,
                                        size=(self.rect.width, self.rect.height))

        if img is not None:
            # PNG がある場合
            draw_img = img
            if self.hit_timer > 0 and (self.hit_timer // 3) % 2 == 0:
                draw_img = img.copy()
                white = pygame.Surface(draw_img.get_size(), pygame.SRCALPHA)
                white.fill((255, 255, 255, 160))
                draw_img.blit(white, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(draw_img, (self.rect.x, self.rect.y))

        else:
            # PNG がない場合：図形で描く
            sx = 1.0 + math.sin(self.anim_t) * 0.07
            sy = 1.0 - math.sin(self.anim_t) * 0.07
            w  = int(self.rect.width  * sx)
            h  = int(self.rect.height * sy)
            dr = pygame.Rect(self.rect.centerx - w // 2,
                             self.rect.centery - h // 2, w, h)
            body_color = C_WHITE if (self.hit_timer > 0 and (self.hit_timer // 3) % 2 == 0) else self.color
            pygame.draw.rect(surface, body_color, dr, border_radius=7)
            pygame.draw.circle(surface, C_DARK_BG, (dr.centerx - 4, dr.centery - 2), 2)
            pygame.draw.circle(surface, C_DARK_BG, (dr.centerx + 4, dr.centery - 2), 2)
            lbl = font_small.render(self.name[0], True, (20, 15, 30))
            surface.blit(lbl, (dr.centerx - lbl.get_width() // 2, dr.top + 2))

        # HP バー（スプライト有無に関わらず表示）
        bw  = self.rect.width + 4
        bx  = self.rect.centerx - bw // 2
        by  = self.rect.top - 9
        rat = max(0.0, self.hp / self.max_hp)
        bc  = (40, 200, 70) if rat > 0.5 else C_CRIMSON_LT
        pygame.draw.rect(surface, (40, 10, 10), (bx, by, bw, 4))
        pygame.draw.rect(surface, bc,           (bx, by, int(bw * rat), 4))

    def _draw_death_effect(self, surface: pygame.Surface):
        prog   = self.death_timer / 30
        radius = int((1 - prog) * 22)
        alpha  = lerp_alpha(self.death_timer, 30, max_alpha=200)  # safe
        if radius < 1: return
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, make_rgba(*self.color, alpha), (radius, radius), radius)  # safe
        surface.blit(s, (self.rect.centerx - radius, self.rect.centery - radius))

    # ──────────────────────────────────────────────────────
    #  バトル画面描画（スプライト対応）
    # ──────────────────────────────────────────────────────
    def draw_battle(self, surface: pygame.Surface,
                    cx: int, cy: int,
                    font_md: pygame.font.Font,
                    font_sm: pygame.font.Font,
                    sprite_mgr=None):
        """
        バトル画面で大きく描く。
        cx, cy      : 中心座標
        sprite_mgr  : SpriteManager（省略可。あれば PNG 表示を試みる）
        """
        if not self.alive:
            if self.death_timer > 0:
                self._draw_battle_death(surface, cx, cy)
            return

        # ── スプライト描画を試みる（バトル用の大きいサイズ）
        BATTLE_SIZE = (100, 100)   # ★ バトル画面での敵サイズ
        img = None
        if sprite_mgr is not None:
            img = sprite_mgr.get_enemy(self.name, size=BATTLE_SIZE)

        if img is not None:
            # PNG がある場合：ぷるぷるアニメーションをスケールで表現
            sx = 1.0 + math.sin(self.anim_t) * 0.04
            sy = 1.0 - math.sin(self.anim_t) * 0.04
            sw = int(BATTLE_SIZE[0] * sx)
            sh = int(BATTLE_SIZE[1] * sy)
            scaled_img = pygame.transform.scale(img, (sw, sh))

            # ダメージ点滅
            if self.hit_timer > 0 and (self.hit_timer // 3) % 2 == 0:
                scaled_img = scaled_img.copy()
                white = pygame.Surface(scaled_img.get_size(), pygame.SRCALPHA)
                white.fill((255, 255, 255, 180))
                scaled_img.blit(white, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            img_rect = scaled_img.get_rect(center=(cx, cy))
            surface.blit(scaled_img, img_rect)

            # 影
            shadow_s = pygame.Surface((sw + 20, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_s, (0, 0, 0, 55), (0, 0, sw + 20, 14))
            surface.blit(shadow_s, (cx - (sw + 20) // 2, cy + sh // 2 - 4))

            # HP バー下端の y 座標を img_rect から計算
            bar_top_y = img_rect.bottom + 12

        else:
            # PNG がない場合：図形でぷるぷる描画
            base_w, base_h = 90, 80
            sx = 1.0 + math.sin(self.anim_t) * 0.06
            sy = 1.0 - math.sin(self.anim_t) * 0.06
            w  = int(base_w * sx)
            h  = int(base_h * sy)
            dr = pygame.Rect(cx - w // 2, cy - h // 2, w, h)

            body_col = C_WHITE if (self.hit_timer > 0 and (self.hit_timer // 3) % 2 == 0) else self.color

            shadow_s = pygame.Surface((w + 20, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_s, (0, 0, 0, 60), (0, 0, w + 20, 14))
            surface.blit(shadow_s, (cx - (w + 20) // 2, cy + h // 2 - 4))

            pygame.draw.rect(surface, body_col, dr, border_radius=18)
            hl_rect = pygame.Rect(dr.x + 8, dr.y + 8, w // 3, h // 4)
            hl_s    = pygame.Surface((max(1,hl_rect.width), max(1,hl_rect.height)), pygame.SRCALPHA)
            hl_s.fill((255, 255, 255, 50))
            surface.blit(hl_s, hl_rect)

            eye_y = cy - 6
            pygame.draw.circle(surface, C_DARK_BG, (cx - 14, eye_y), 7)
            pygame.draw.circle(surface, C_DARK_BG, (cx + 14, eye_y), 7)
            pygame.draw.circle(surface, (200, 200, 240), (cx - 12, eye_y - 1), 3)
            pygame.draw.circle(surface, (200, 200, 240), (cx + 16, eye_y - 1), 3)
            if self.state == "chase":
                pygame.draw.line(surface, C_DARK_BG, (cx - 12, cy + 18), (cx + 12, cy + 18), 2)
            else:
                pygame.draw.arc(surface, C_DARK_BG,
                                pygame.Rect(cx - 12, cy + 10, 24, 14), math.pi, 0, 2)

            bar_top_y = dr.bottom + 12

        # 属性名ラベル（スプライト有無に関わらず）
        name_txt = font_md.render(self.name, True, self.color)
        surface.blit(name_txt, (cx - name_txt.get_width() // 2, cy - 80))

        # HP バー
        bar_w   = 120
        bar_x   = cx - bar_w // 2
        ratio   = max(0.0, self.hp / self.max_hp)
        bar_col = (50, 210, 80) if ratio > 0.5 else C_CRIMSON_LT
        pygame.draw.rect(surface, (40, 10, 10), (bar_x, bar_top_y, bar_w, 10), border_radius=4)
        pygame.draw.rect(surface, bar_col,      (bar_x, bar_top_y, int(bar_w * ratio), 10), border_radius=4)
        pygame.draw.rect(surface, C_GOLD,       (bar_x, bar_top_y, bar_w, 10), 1, border_radius=4)
        hp_txt = font_sm.render(f"{self.hp}/{self.max_hp}", True, C_WHITE)
        surface.blit(hp_txt, (cx - hp_txt.get_width() // 2, bar_top_y + 13))

        # ダメージ数値の浮き上がり
        for ft in self.float_texts:
            alpha   = lerp_alpha(ft["life"], 50)           # safe: float→int→clamp
            fx      = ft["x"] if ft["x"] != 0 else cx
            fy      = ft["y"] if ft["y"] != 0 else (cy - 60 - (50 - ft["life"]))
            dmg_txt = font_md.render(ft["text"], True, ft["color"])
            dmg_txt.set_alpha(alpha)
            surface.blit(dmg_txt, (fx - dmg_txt.get_width() // 2, fy))

    def _draw_battle_death(self, surface: pygame.Surface, cx: int, cy: int):
        prog   = self.death_timer / 30
        radius = int((1 - prog) * 60)
        alpha  = lerp_alpha(self.death_timer, 30, max_alpha=220)  # safe
        if radius < 1: return
        s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, make_rgba(*self.color, alpha), (radius, radius), radius)  # safe
        surface.blit(s, (cx - radius, cy - radius))
