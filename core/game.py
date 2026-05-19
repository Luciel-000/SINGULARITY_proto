"""
============================================================
  core/game.py  ── ゲーム本体（状態管理・メインループ処理）
                   [0.3 更新]

  [0.3 変更点]
    - FontManager を使って日本語フォントに対応
    - SpriteManager を使ってスプライト画像を管理
    - Player / Enemy の draw() に sprite_mgr を渡す
    - Battle 生成時に fonts / sprite_mgr を渡す
============================================================
"""

import pygame
import random
from .constants import (
    WINDOW_W, WINDOW_H, GAME_AREA_H, HUD_H, TILE,
    STATE_TITLE, STATE_PLAY, STATE_BATTLE, STATE_LEVELUP, STATE_GAMEOVER,
    C_DARK_BG, C_WHITE, C_GOLD,
    C_CRIMSON_LT, C_GREEN_DIM, C_GRAY, C_DARK_GRAY,
    SLIME_VARIANTS,
)
from .player         import Player
from .enemy          import Enemy
from .world          import World
from .battle         import Battle
from .font_manager   import FontManager      # ★ 0.3: 日本語フォント管理
from .sprite_manager import SpriteManager    # ★ 0.3: スプライト管理


class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.state  = STATE_TITLE

        # ── ★ 0.3: FontManager でフォントを一元管理
        self.fm = FontManager()
        # 旧コードとの互換性のため短縮名も用意
        self.font_lg = self.fm.lg
        self.font_md = self.fm.md
        self.font_sm = self.fm.sm

        # ── ★ 0.3: SpriteManager でスプライトを一元管理
        self.sprite_mgr = SpriteManager(base_dir=".")

        # ゲームオブジェクト
        self.world  : World        | None = None
        self.player : Player       | None = None
        self.enemies: list[Enemy]         = []
        self.battle : Battle       | None = None
        self.battle_enemy: Enemy   | None = None

        self.messages: list[dict] = []
        self.title_timer    = 0
        self.gameover_timer = 0

    # ──────────────────────────────────────────────────────
    #  ゲーム初期化
    # ──────────────────────────────────────────────────────
    def _init_game(self):
        self.world    = World()
        px, py        = self.world.player_spawn
        self.player   = Player(px, py)
        self.enemies  = []
        self.messages = []
        self.battle   = None
        self.battle_enemy = None

        spawn_positions = self.world.get_enemy_spawns(6)
        for i, (ex, ey) in enumerate(spawn_positions):
            self.enemies.append(Enemy(ex, ey, variant_index=i % len(SLIME_VARIANTS)))

    # ──────────────────────────────────────────────────────
    #  イベント処理
    # ──────────────────────────────────────────────────────
    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if self.state == STATE_TITLE:
                if event.key == pygame.K_SPACE:
                    self._init_game()
                    self.state = STATE_PLAY
            elif self.state == STATE_GAMEOVER:
                if event.key == pygame.K_SPACE:
                    self.state = STATE_TITLE

        if self.state == STATE_BATTLE and self.battle:
            self.battle.handle_event(event)

    # ──────────────────────────────────────────────────────
    #  毎フレーム更新
    # ──────────────────────────────────────────────────────
    def update(self):
        self.title_timer += 1

        if self.state == STATE_TITLE:
            return

        if self.state == STATE_GAMEOVER:
            self.gameover_timer += 1
            return

        if self.state == STATE_LEVELUP:
            if self.player and self.player.levelup_timer <= 0:
                self.state = STATE_PLAY
            if self.player and self.world:
                self.player.update(self.world.wall_rects)
            return

        if self.state == STATE_BATTLE and self.battle:
            result = self.battle.update()
            if result == "win":
                enemy = self.battle_enemy
                if enemy:
                    leveled = self.player.gain_exp(enemy.exp_val)
                    self._add_message(f"{enemy.name} 撃破！  +{enemy.exp_val} EXP", (100, 220, 100))
                    if leveled:
                        self._add_message(f"LEVEL UP!  Lv {self.player.level}", C_GOLD)
                        self.state = STATE_LEVELUP
                    else:
                        self.state = STATE_PLAY
                else:
                    self.state = STATE_PLAY
                self.enemies = [e for e in self.enemies if e is not self.battle_enemy]
                self.battle  = None
                self.battle_enemy = None
                if not any(e.alive for e in self.enemies):
                    self._respawn_enemies()

            elif result == "lose":
                self.state          = STATE_GAMEOVER
                self.gameover_timer = 0
                self.battle         = None

            elif result == "escape":
                self.state = STATE_PLAY
                self.battle = None
                self.battle_enemy = None
                self._add_message("逃走した！", C_GRAY)
            return

        if self.state == STATE_PLAY and self.player and self.world:
            self.player.update(self.world.wall_rects)
            for enemy in self.enemies:
                enemy.update(self.player.rect, self.world.wall_rects)
                if enemy.alive and enemy.touches_player(self.player.rect):
                    self._start_battle(enemy)
                    break
            self.enemies = [e for e in self.enemies if e.alive or e.death_timer > 0]
            if self.player.is_dead:
                self.state          = STATE_GAMEOVER
                self.gameover_timer = 0

        self.messages = [
            {**m, "timer": m["timer"] - 1}
            for m in self.messages if m["timer"] > 0
        ]

    # ──────────────────────────────────────────────────────
    #  バトル開始
    # ──────────────────────────────────────────────────────
    def _start_battle(self, enemy: Enemy):
        self.battle_enemy = enemy
        self.battle = Battle(
            player     = self.player,
            enemy      = enemy,
            font_lg    = self.font_lg,
            font_md    = self.font_md,
            font_sm    = self.font_sm,
            sprite_mgr = self.sprite_mgr,   # ★ 0.3: sprite_mgr を渡す
        )
        self.state = STATE_BATTLE
        self._add_message(f"{enemy.name} が現れた！", C_GOLD)

    def _respawn_enemies(self):
        if not self.world: return
        positions = self.world.get_enemy_spawns(4)
        for i, (ex, ey) in enumerate(positions):
            self.enemies.append(Enemy(ex, ey))
        self._add_message("新たな敵が現れた！", C_GRAY)

    def _add_message(self, text: str, color: tuple):
        self.messages.insert(0, {"text": text, "timer": 150, "color": color})
        if len(self.messages) > 5:
            self.messages.pop()

    # ──────────────────────────────────────────────────────
    #  描画
    # ──────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface):
        if self.state == STATE_TITLE:
            self._draw_title(surface)
        elif self.state == STATE_BATTLE and self.battle:
            self.battle.draw(surface)
        elif self.state in (STATE_PLAY, STATE_LEVELUP):
            self._draw_play(surface)
        elif self.state == STATE_GAMEOVER:
            self._draw_play(surface)
            self._draw_gameover(surface)

    # ── タイトル画面 ──────────────────────────────────────
    def _draw_title(self, surface: pygame.Surface):
        surface.fill(C_DARK_BG)
        pygame.draw.line(surface, C_GOLD, (40, 80),  (WINDOW_W - 40, 80),  1)
        pygame.draw.line(surface, C_GOLD, (40, WINDOW_H - 80), (WINDOW_W - 40, WINDOW_H - 80), 1)

        t1 = self.font_lg.render("SINGULARITY",             True, C_WHITE)
        t2 = self.font_md.render("- Chronicle of Origin -", True, C_GOLD)
        t3 = self.font_sm.render("Prototype  0.3",          True, C_GRAY)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, 110))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, 158))
        surface.blit(t3, (WINDOW_W // 2 - t3.get_width() // 2, 192))

        # プレイヤースプライトまたは図形
        title_player_img = self.sprite_mgr.get_player("novice_m", size=(64, 64))
        if title_player_img:
            surface.blit(title_player_img,
                         (WINDOW_W // 2 - 32, 240))
        else:
            pygame.draw.circle(surface, C_WHITE, (WINDOW_W // 2, 268), 18)
            pygame.draw.rect(surface, C_WHITE,
                             pygame.Rect(WINDOW_W // 2 - 10, 285, 20, 30), border_radius=4)
            pygame.draw.line(surface, C_GOLD,
                             (WINDOW_W // 2 + 10, 293), (WINDOW_W // 2 + 26, 281), 2)

        desc = self.font_sm.render("主人公：ノービス", True, C_GRAY)
        surface.blit(desc, (WINDOW_W // 2 - desc.get_width() // 2, 316))

        info_lines = [
            "移動：WASD / 矢印キー",
            "コマンド：↑↓ 選択  Z/Enter 決定",
            "敵に接触するとバトル開始！",
        ]
        for i, line in enumerate(info_lines):
            txt = self.font_sm.render(line, True, C_GRAY)
            surface.blit(txt, (WINDOW_W // 2 - txt.get_width() // 2, 370 + i * 22))

        if (self.title_timer // 30) % 2 == 0:
            start = self.font_md.render("[ SPACE ] でゲーム開始", True, C_GOLD)
            surface.blit(start, (WINDOW_W // 2 - start.get_width() // 2, WINDOW_H - 55))

    # ── 探索マップ ────────────────────────────────────────
    def _draw_play(self, surface: pygame.Surface):
        if not self.world or not self.player:
            return
        self.world.draw(surface)

        # ★ 0.3: sprite_mgr を渡す
        for enemy in self.enemies:
            enemy.draw(surface, self.font_sm, self.sprite_mgr)

        self.player.draw(surface, self.sprite_mgr)

        if self.state == STATE_LEVELUP:
            self._draw_levelup_overlay(surface)
        self._draw_hud(surface)

    def _draw_levelup_overlay(self, surface: pygame.Surface):
        overlay = pygame.Surface((WINDOW_W, GAME_AREA_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 110))
        surface.blit(overlay, (0, 0))
        t1 = self.font_lg.render("LEVEL UP !", True, C_GOLD)
        t2 = self.font_md.render(
            f"Lv {self.player.level}  HP+8  ATK+3  DEF+1", True, C_WHITE)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, GAME_AREA_H // 2 - 40))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, GAME_AREA_H // 2 + 12))

    def _draw_hud(self, surface: pygame.Surface):
        p = self.player
        pygame.draw.rect(surface, (10, 8, 18),
                         pygame.Rect(0, GAME_AREA_H, WINDOW_W, HUD_H))
        pygame.draw.line(surface, C_GOLD, (0, GAME_AREA_H), (WINDOW_W, GAME_AREA_H), 1)

        bar_x, bar_y, bar_w = 12, GAME_AREA_H + 10, 180

        hp_label = self.font_sm.render(f"HP  {p.hp} / {p.max_hp}", True, C_WHITE)
        surface.blit(hp_label, (bar_x, bar_y))
        ratio    = max(0.0, p.hp / p.max_hp)
        hp_color = C_CRIMSON_LT if ratio > 0.3 else (255, 50, 50)
        pygame.draw.rect(surface, (50, 15, 15), (bar_x, bar_y + 18, bar_w, 10), border_radius=3)
        pygame.draw.rect(surface, hp_color,     (bar_x, bar_y + 18, int(bar_w * ratio), 10), border_radius=3)

        exp_label = self.font_sm.render(f"EXP {p.exp}  ( next: {p.exp_to_next()} )", True, C_GOLD)
        surface.blit(exp_label, (bar_x, bar_y + 34))
        pygame.draw.rect(surface, (20, 40, 20), (bar_x, bar_y + 52, bar_w, 6), border_radius=3)
        pygame.draw.rect(surface, C_GREEN_DIM,  (bar_x, bar_y + 52, int(bar_w * p.exp_progress()), 6), border_radius=3)

        lv_txt = self.font_md.render(f"Lv {p.level}", True, C_GOLD)
        surface.blit(lv_txt, (210, GAME_AREA_H + 10))
        stats_txt = self.font_sm.render(f"ATK {p.atk}   DEF {p.defense}", True, C_GRAY)
        surface.blit(stats_txt, (210, GAME_AREA_H + 38))

        hint = self.font_sm.render("移動：WASD/矢印   敵に接触→バトル", True, C_DARK_GRAY)
        surface.blit(hint, (WINDOW_W - hint.get_width() - 10, GAME_AREA_H + 10))

        msg_x = WINDOW_W - 10
        for i, msg in enumerate(self.messages[:3]):
            alpha = min(255, msg["timer"] * 2)
            txt   = self.font_sm.render(msg["text"], True, msg["color"])
            txt.set_alpha(alpha)
            surface.blit(txt, (msg_x - txt.get_width(), GAME_AREA_H + 30 + i * 18))

    def _draw_gameover(self, surface: pygame.Surface):
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        alpha   = min(180, self.gameover_timer * 3)
        overlay.fill((0, 0, 0, alpha))
        surface.blit(overlay, (0, 0))
        if self.gameover_timer < 20: return
        t1 = self.font_lg.render("GAME  OVER", True, C_CRIMSON_LT)
        t2 = self.font_md.render(
            f"到達レベル：{self.player.level}   累積EXP：{self.player.exp}", True, C_WHITE)
        t3 = self.font_sm.render("[ SPACE ] でタイトルへ戻る", True, C_GRAY)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, WINDOW_H // 2 - 60))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, WINDOW_H // 2 + 10))
        surface.blit(t3, (WINDOW_W // 2 - t3.get_width() // 2, WINDOW_H // 2 + 50))
