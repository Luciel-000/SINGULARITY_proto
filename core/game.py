"""
============================================================
  core/game.py  ── ゲーム本体（状態管理・メインループ処理）
                   [0.5 更新]

  [0.5 Step9 変更点]
    - HUD にプレイヤーの属性を表示
    - player.element → get_element_name / get_element_color で
      ジョブ名の直下に「属性：火」などを属性カラーで表示

  [0.4 変更点（継続）]
    - J キーでジョブチェンジメニューを開く
    - ジョブチェンジメニュー状態（STATE_JOB_MENU）を追加
    - HUD にジョブ名を常時表示

  [0.3 変更点（継続）]
    - FontManager / SpriteManager を使用
    - STATE_BATTLE バトル状態管理
============================================================
"""

import pygame
import random
from .utils      import safe_alpha, make_rgba
from .constants  import (
    WINDOW_W, WINDOW_H, GAME_AREA_H, HUD_H, TILE,
    STATE_TITLE, STATE_PLAY, STATE_BATTLE, STATE_LEVELUP, STATE_GAMEOVER,
    C_DARK_BG, C_WHITE, C_GOLD,
    C_CRIMSON_LT, C_GREEN_DIM, C_GRAY, C_DARK_GRAY,
    C_WINDOW_BG, C_WINDOW_BORDER,
    SLIME_VARIANTS,
)
from .player         import Player
from .enemy          import Enemy
from .world          import World
from .battle         import Battle
from .font_manager   import FontManager
from .sprite_manager import SpriteManager
from .job_data       import get_job, get_evolutions, JOB_DATA   # ★ 0.4
from .element_system import get_element_name, get_element_color  # ★ 0.5: 属性名・属性カラー

# ★ 0.4: ジョブチェンジメニューの状態定数
STATE_JOB_MENU = "job_menu"


class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.state  = STATE_TITLE

        self.fm      = FontManager()
        self.font_lg = self.fm.lg
        self.font_md = self.fm.md
        self.font_sm = self.fm.sm

        self.sprite_mgr = SpriteManager(base_dir=".")

        self.world  : World        | None = None
        self.player : Player       | None = None
        self.enemies: list[Enemy]         = []
        self.battle : Battle       | None = None
        self.battle_enemy: Enemy   | None = None

        self.messages: list[dict] = []
        self.title_timer    = 0
        self.gameover_timer = 0

        # ★ 0.4: ジョブチェンジメニュー用
        # job_menu_options : 現在選択可能なジョブIDのリスト
        # job_menu_cursor  : カーソル位置
        self.job_menu_options: list[str] = []
        self.job_menu_cursor : int       = 0

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
        self._add_message("J キーでジョブチェンジメニュー", C_GOLD)

        spawn_positions = self.world.get_enemy_spawns(6)
        for i, (ex, ey) in enumerate(spawn_positions):
            self.enemies.append(Enemy(ex, ey, variant_index=i % len(SLIME_VARIANTS)))

    # ──────────────────────────────────────────────────────
    #  イベント処理
    # ──────────────────────────────────────────────────────
    def handle_event(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            # バトル中はバトルへ全イベントを渡す
            if self.state == STATE_BATTLE and self.battle:
                self.battle.handle_event(event)
            return

        key = event.key

        # ── タイトル
        if self.state == STATE_TITLE:
            if key == pygame.K_SPACE:
                self._init_game()
                self.state = STATE_PLAY
            return

        # ── ゲームオーバー
        if self.state == STATE_GAMEOVER:
            if key == pygame.K_SPACE:
                self.state = STATE_TITLE
            return

        # ── バトル中
        if self.state == STATE_BATTLE and self.battle:
            self.battle.handle_event(event)
            return

        # ── ジョブチェンジメニュー ★ 0.4
        if self.state == STATE_JOB_MENU:
            self._handle_job_menu_key(key)
            return

        # ── 探索マップ中
        if self.state in (STATE_PLAY, STATE_LEVELUP):
            if key == pygame.K_j:
                # J キーでジョブメニューを開く
                self._open_job_menu()

    def _open_job_menu(self):
        """
        ジョブチェンジメニューを開く。
        現在のジョブから変更できるジョブ一覧を取得して表示する。
        """
        if not self.player:
            return

        # 現在のジョブから選択可能なジョブを取得
        # ★ 「全ジョブ選択可能」にしたい場合は get_evolutions を all_job_ids に変える
        options = get_evolutions(self.player.current_job_id)

        # 現在のジョブも「戻る」として含める（ノービスに戻れるなど）
        # ただし同じジョブへのチェンジは change_job() 側で弾く
        if not options:
            self._add_message("このジョブから変更できるジョブがありません", C_GRAY)
            return

        self.job_menu_options = options
        self.job_menu_cursor  = 0
        self.state = STATE_JOB_MENU

    def _handle_job_menu_key(self, key: int):
        """ジョブメニュー中のキー操作"""
        options = self.job_menu_options

        if key in (pygame.K_UP, pygame.K_w):
            self.job_menu_cursor = (self.job_menu_cursor - 1) % len(options)

        elif key in (pygame.K_DOWN, pygame.K_s):
            self.job_menu_cursor = (self.job_menu_cursor + 1) % len(options)

        elif key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
            # 選択されたジョブにチェンジ
            chosen_id = options[self.job_menu_cursor]
            self._do_job_change(chosen_id)

        elif key in (pygame.K_ESCAPE, pygame.K_x):
            # キャンセル → 探索に戻る
            self.state = STATE_PLAY
            self._add_message("ジョブチェンジをキャンセルした", C_GRAY)

    def _do_job_change(self, new_job_id: str):
        """ジョブチェンジを実行してメニューを閉じる"""
        if not self.player:
            return

        new_job  = get_job(new_job_id)
        job_name = new_job["name"]

        if self.player.change_job(new_job_id):
            self._add_message(f"ジョブチェンジ：{job_name}！", new_job["color"])
        else:
            self._add_message(f"すでに {job_name} です", C_GRAY)

        self.state = STATE_PLAY

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

        # ジョブメニュー中はプレイヤーを更新しない
        if self.state == STATE_JOB_MENU:
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
                    self._add_message(
                        f"{enemy.name} 撃破！  +{enemy.exp_val} EXP",
                        (100, 220, 100)
                    )
                    if leveled:
                        job = self.player.current_job
                        self._add_message(
                            f"LEVEL UP! Lv{self.player.level}  "
                            f"HP+{job['lv_up_hp']} ATK+{job['lv_up_atk']} DEF+{job['lv_up_def']}",
                            C_GOLD
                        )
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
                self.state        = STATE_PLAY
                self.battle       = None
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
    #  バトル・補充・メッセージ
    # ──────────────────────────────────────────────────────
    def _start_battle(self, enemy: Enemy):
        self.battle_enemy = enemy
        self.battle = Battle(
            player     = self.player,
            enemy      = enemy,
            font_lg    = self.font_lg,
            font_md    = self.font_md,
            font_sm    = self.font_sm,
            sprite_mgr = self.sprite_mgr,
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
        self.messages.insert(0, {"text": text, "timer": 180, "color": color})
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
        elif self.state == STATE_JOB_MENU:
            # ジョブメニューはマップの上に重ねて表示
            self._draw_play(surface)
            self._draw_job_menu(surface)
        elif self.state in (STATE_PLAY, STATE_LEVELUP):
            self._draw_play(surface)
        elif self.state == STATE_GAMEOVER:
            self._draw_play(surface)
            self._draw_gameover(surface)

    # ── タイトル画面 ──────────────────────────────────────
    def _draw_title(self, surface: pygame.Surface):
        surface.fill(C_DARK_BG)
        pygame.draw.line(surface, C_GOLD, (40, 80), (WINDOW_W - 40, 80), 1)
        pygame.draw.line(surface, C_GOLD, (40, WINDOW_H - 80), (WINDOW_W - 40, WINDOW_H - 80), 1)

        t1 = self.font_lg.render("SINGULARITY",             True, C_WHITE)
        t2 = self.font_md.render("- Chronicle of Origin -", True, C_GOLD)
        t3 = self.font_sm.render("Prototype  0.5",          True, C_GRAY)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, 110))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, 158))
        surface.blit(t3, (WINDOW_W // 2 - t3.get_width() // 2, 192))

        img = self.sprite_mgr.get_player("novice_m", size=(64, 64))
        if img:
            surface.blit(img, (WINDOW_W // 2 - 32, 230))
        else:
            pygame.draw.circle(surface, C_WHITE, (WINDOW_W // 2, 258), 18)
            pygame.draw.rect(surface, C_WHITE,
                             pygame.Rect(WINDOW_W // 2 - 10, 275, 20, 30), border_radius=4)

        desc = self.font_sm.render("主人公：ノービス", True, C_GRAY)
        surface.blit(desc, (WINDOW_W // 2 - desc.get_width() // 2, 306))

        info_lines = [
            "移動：WASD / 矢印キー",
            "コマンド：↑↓ 選択  Z/Enter 決定",
            "J キー：ジョブチェンジ",
            "敵に接触するとバトル開始！",
        ]
        for i, line in enumerate(info_lines):
            txt = self.font_sm.render(line, True, C_GRAY)
            surface.blit(txt, (WINDOW_W // 2 - txt.get_width() // 2, 352 + i * 22))

        if (self.title_timer // 30) % 2 == 0:
            start = self.font_md.render("[ SPACE ] でゲーム開始", True, C_GOLD)
            surface.blit(start, (WINDOW_W // 2 - start.get_width() // 2, WINDOW_H - 55))

    # ── 探索マップ ────────────────────────────────────────
    def _draw_play(self, surface: pygame.Surface):
        if not self.world or not self.player:
            return
        self.world.draw(surface)
        for enemy in self.enemies:
            enemy.draw(surface, self.font_sm, self.sprite_mgr)
        self.player.draw(surface, self.sprite_mgr)
        if self.state == STATE_LEVELUP:
            self._draw_levelup_overlay(surface)
        self._draw_hud(surface)

    def _draw_levelup_overlay(self, surface: pygame.Surface):
        overlay = pygame.Surface((WINDOW_W, GAME_AREA_H), pygame.SRCALPHA)
        overlay.fill(make_rgba(0, 0, 0, 110))
        surface.blit(overlay, (0, 0))
        job = self.player.current_job
        t1 = self.font_lg.render("LEVEL UP !", True, C_GOLD)
        t2 = self.font_md.render(
            f"Lv {self.player.level}  "
            f"HP+{job['lv_up_hp']}  ATK+{job['lv_up_atk']}  DEF+{job['lv_up_def']}",
            True, C_WHITE)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, GAME_AREA_H // 2 - 40))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, GAME_AREA_H // 2 + 12))

    # ── HUD（★ 0.4: ジョブ表示を追加） ──────────────────
    def _draw_hud(self, surface: pygame.Surface):
        p = self.player
        pygame.draw.rect(surface, (10, 8, 18),
                         pygame.Rect(0, GAME_AREA_H, WINDOW_W, HUD_H))
        pygame.draw.line(surface, C_GOLD, (0, GAME_AREA_H), (WINDOW_W, GAME_AREA_H), 1)

        bar_x, bar_y, bar_w = 12, GAME_AREA_H + 10, 180

        # HP バー
        hp_label = self.font_sm.render(f"HP  {p.hp} / {p.max_hp}", True, C_WHITE)
        surface.blit(hp_label, (bar_x, bar_y))
        ratio    = max(0.0, p.hp / p.max_hp)
        hp_color = C_CRIMSON_LT if ratio > 0.3 else (255, 50, 50)
        pygame.draw.rect(surface, (50, 15, 15), (bar_x, bar_y + 18, bar_w, 10), border_radius=3)
        pygame.draw.rect(surface, hp_color,     (bar_x, bar_y + 18, int(bar_w * ratio), 10), border_radius=3)

        # EXP バー
        exp_label = self.font_sm.render(
            f"EXP {p.exp}  ( next: {p.exp_to_next()} )", True, C_GOLD)
        surface.blit(exp_label, (bar_x, bar_y + 34))
        pygame.draw.rect(surface, (20, 40, 20), (bar_x, bar_y + 52, bar_w, 6), border_radius=3)
        pygame.draw.rect(surface, C_GREEN_DIM,  (bar_x, bar_y + 52,
                         int(bar_w * p.exp_progress()), 6), border_radius=3)

        # レベル・ステータス
        lv_txt = self.font_md.render(f"Lv {p.level}", True, C_GOLD)
        surface.blit(lv_txt, (210, GAME_AREA_H + 10))
        stats_txt = self.font_sm.render(
            f"ATK {p.atk}   DEF {p.defense}", True, C_GRAY)
        surface.blit(stats_txt, (210, GAME_AREA_H + 34))

        # ★ 0.4: ジョブ名をジョブカラーで表示（レベルの右隣）
        job_txt = self.font_sm.render(f"[ {p.job_name} ]", True, p.job_color)
        surface.blit(job_txt, (210, GAME_AREA_H + 56))

        # ★ 0.5 Step9: 属性名を属性カラーで表示（ジョブ名の直下）
        elem_name  = get_element_name(p.element)          # 例: "火" / "無"
        elem_color = get_element_color(p.element)         # 属性ごとのRGBカラー
        elem_txt   = self.font_sm.render(f"属性：{elem_name}", True, elem_color)
        surface.blit(elem_txt, (210, GAME_AREA_H + 72))

        # ヒント（右端）
        hint = self.font_sm.render(
            "移動：WASD/矢印   J：ジョブチェンジ", True, C_DARK_GRAY)
        surface.blit(hint, (WINDOW_W - hint.get_width() - 10, GAME_AREA_H + 10))

        # メッセージログ（最新3件）
        msg_x = WINDOW_W - 10
        for i, msg in enumerate(self.messages[:3]):
            alpha = safe_alpha(min(255, msg["timer"] * 2))
            txt   = self.font_sm.render(msg["text"], True, msg["color"])
            txt.set_alpha(alpha)
            surface.blit(txt, (msg_x - txt.get_width(), GAME_AREA_H + 30 + i * 18))

    # ── ★ 0.4: ジョブチェンジメニュー ────────────────────
    def _draw_job_menu(self, surface: pygame.Surface):
        """
        探索マップの上に半透明のジョブ選択ウィンドウを重ねて表示する。
        コマンドウィンドウと同じデザインで統一感を出す。
        """
        # 半透明オーバーレイ
        overlay = pygame.Surface((WINDOW_W, GAME_AREA_H), pygame.SRCALPHA)
        overlay.fill(make_rgba(0, 0, 0, 140))
        surface.blit(overlay, (0, 0))

        # ウィンドウ本体
        WIN_W, WIN_H = 420, 320
        wx = WINDOW_W  // 2 - WIN_W // 2
        wy = GAME_AREA_H // 2 - WIN_H // 2
        pygame.draw.rect(surface, C_WINDOW_BG,     (wx, wy, WIN_W, WIN_H), border_radius=6)
        pygame.draw.rect(surface, C_WINDOW_BORDER, (wx, wy, WIN_W, WIN_H), 2, border_radius=6)
        pygame.draw.line(surface, C_GOLD,
                         (wx + 1, wy + 42), (wx + WIN_W - 1, wy + 42), 1)

        # タイトル
        title = self.font_md.render("ジョブチェンジ", True, C_GOLD)
        surface.blit(title, (wx + WIN_W // 2 - title.get_width() // 2, wy + 12))

        p = self.player
        # 現在のジョブ表示
        cur_txt = self.font_sm.render(
            f"現在：{p.job_name}  Lv {p.level}  ATK {p.atk}  DEF {p.defense}",
            True, p.job_color)
        surface.blit(cur_txt, (wx + 16, wy + 52))

        # ── 選択肢リスト
        opt_y = wy + 88
        for i, job_id in enumerate(self.job_menu_options):
            job      = get_job(job_id)
            is_sel   = (i == self.job_menu_cursor)
            jcolor   = job["color"]

            # 選択ハイライト
            if is_sel:
                hl = pygame.Rect(wx + 12, opt_y + i * 66 - 4, WIN_W - 24, 60)
                pygame.draw.rect(surface, (35, 28, 55), hl, border_radius=4)
                pygame.draw.rect(surface, C_GOLD, hl, 1, border_radius=4)

            # カーソル
            if is_sel:
                cur = self.font_md.render("▶", True, C_GOLD)
                surface.blit(cur, (wx + 16, opt_y + i * 66 + 4))

            # ジョブ名（Tier バッジ付き）
            tier_mark = "★" * job.get("tier", 1)
            name_line = self.font_md.render(
                f"{job['name']}  {tier_mark}", True, jcolor)
            surface.blit(name_line, (wx + 38, opt_y + i * 66))

            # ステータスプレビュー（ボーナス差分を表示）
            hp_d  = job.get("hp_bonus",  0) - p.current_job.get("hp_bonus",  0)
            atk_d = job.get("atk_bonus", 0) - p.current_job.get("atk_bonus", 0)
            def_d = job.get("def_bonus", 0) - p.current_job.get("def_bonus", 0)

            def _sign(v): return f"+{v}" if v >= 0 else str(v)

            preview = self.font_sm.render(
                f"HP {_sign(hp_d)}  ATK {_sign(atk_d)}  DEF {_sign(def_d)}  "
                f"| {job['desc'][:16]}…",
                True, C_GRAY)
            surface.blit(preview, (wx + 38, opt_y + i * 66 + 26))

        # 操作ヒント
        hint = self.font_sm.render(
            "↑↓ 選択   Z/Enter 決定   Esc/X キャンセル", True, C_DARK_GRAY)
        surface.blit(hint, (wx + WIN_W // 2 - hint.get_width() // 2, wy + WIN_H - 26))

    # ── ゲームオーバー ────────────────────────────────────
    def _draw_gameover(self, surface: pygame.Surface):
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        alpha   = safe_alpha(min(180, self.gameover_timer * 3))
        overlay.fill(make_rgba(0, 0, 0, alpha))
        surface.blit(overlay, (0, 0))
        if self.gameover_timer < 20: return
        t1 = self.font_lg.render("GAME  OVER", True, C_CRIMSON_LT)
        t2 = self.font_md.render(
            f"到達レベル：{self.player.level}  ジョブ：{self.player.job_name}  EXP：{self.player.exp}",
            True, C_WHITE)
        t3 = self.font_sm.render("[ SPACE ] でタイトルへ戻る", True, C_GRAY)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, WINDOW_H // 2 - 60))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, WINDOW_H // 2 + 10))
        surface.blit(t3, (WINDOW_W // 2 - t3.get_width() // 2, WINDOW_H // 2 + 50))
