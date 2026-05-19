"""
============================================================
  core/battle.py  ── ターン制バトルエンジン  [0.2 新規]

  担当機能:
    - コマンド選択（攻撃 / スキル / 合成 / 逃げる）
    - ターン進行管理（プレイヤーターン → 敵ターン → ...）
    - 攻撃アニメーション（前進 → 剣エフェクト → 後退）
    - ダメージ計算と浮き上がり数字
    - 勝利 / 敗北 / 逃走の判定

  流れ:
    プレイヤーターン → コマンド待機 → 実行 → 敵ターン → ...

  用語:
    phase（フェーズ）= 今バトルが何をしているか
      "player_select" : プレイヤーがコマンドを選んでいる
      "player_anim"   : プレイヤーの攻撃アニメーション中
      "enemy_anim"    : 敵の攻撃アニメーション中
      "result"        : 勝利・敗北・逃走の結果表示中
============================================================
"""

import pygame
import math
import random
from .constants import (
    WINDOW_W, WINDOW_H,
    BATTLE_TOP_H, BATTLE_CMD_Y, BATTLE_CMD_H,
    PLAYER_BATTLE_X, PLAYER_BATTLE_Y,
    ENEMY_BATTLE_X,  ENEMY_BATTLE_Y,
    C_DARK_BG, C_BATTLE_BG, C_WINDOW_BG, C_WINDOW_BORDER,
    C_WHITE, C_GOLD, C_CRIMSON_LT, C_GREEN_DIM, C_GRAY,
    C_CMD_SELECT, C_CMD_NORMAL, C_CMD_DISABLED,
    C_DAMAGE_NUM,
)


# ── コマンドの定義 ──────────────────────────────────────
# (表示名, 実装済みか)  False のコマンドはグレー表示のみ
COMMANDS = [
    ("攻撃",   True),    # ★ 実装済み
    ("スキル", False),   # 未実装（今後追加予定）
    ("合成",   False),   # 未実装（今後追加予定）
    ("逃げる", True),    # ★ 実装済み
]

# ── アニメーションの長さ（フレーム数） ────────────────
ANIM_FORWARD  = 12   # 前進するフレーム数
ANIM_SLASH    = 10   # 剣エフェクトを表示するフレーム数
ANIM_BACK     = 12   # 後退するフレーム数
ANIM_RESULT   = 120  # 結果表示（勝利など）のフレーム数
ESCAPE_CHANCE = 0.7  # 逃げる成功確率（0.0〜1.0）


class Battle:
    """
    ターン制バトルを管理するクラス。

    使い方:
        battle = Battle(player, enemy)
        battle.handle_event(event)   # キー入力を渡す
        result = battle.update()     # None / "win" / "lose" / "escape"
        battle.draw(surface)         # 毎フレーム描画
    """

    def __init__(self, player, enemy, font_lg, font_md, font_sm, sprite_mgr=None):
        self.player   = player
        self.enemy    = enemy
        self.font_lg  = font_lg
        self.font_md  = font_md
        self.font_sm  = font_sm
        self.sprite_mgr = sprite_mgr   # ★ 0.3: スプライト管理

        # ── フェーズ（バトルの進行段階）
        #   "player_select" → コマンドを選ぶ
        #   "player_anim"   → プレイヤー攻撃アニメ
        #   "enemy_anim"    → 敵攻撃アニメ
        #   "result"        → 結果表示（勝利・敗北・逃走）
        self.phase = "player_select"

        # ── コマンドカーソル位置（0〜3）
        self.cursor = 0

        # ── アニメーションタイマー
        self.anim_timer = 0

        # ── プレイヤーのバトル中X座標（アニメーションで変化）
        self.player_x = PLAYER_BATTLE_X
        self.player_y = PLAYER_BATTLE_Y

        # ── ダメージ数値の浮き上がり（プレイヤー側）
        #    [{"text": "12", "x": 160, "y": 200, "life": 50, "color": ...}]
        self.player_floats: list[dict] = []

        # ── 剣エフェクト用タイマー（0のとき非表示）
        self.slash_timer = 0

        # ── 最後に表示するメッセージ（結果フェーズ用）
        self.result_text   = ""
        self.result_timer  = 0

        # ── バトルログ（画面下コマンドウィンドウ内に表示）
        self.log: list[str] = ["バトル開始！"]

        # ── 最終結果（update() の戻り値になる）
        self._result: str | None = None

        # ── 背景用タイマー（エフェクト）
        self.bg_timer = 0

    # ──────────────────────────────────────────────────────
    #  キー入力処理
    # ──────────────────────────────────────────────────────
    def handle_event(self, event: pygame.event.Event):
        """キーダウンイベントを受け取って処理する"""
        if event.type != pygame.KEYDOWN:
            return

        # ── コマンド選択フェーズのみキー受付
        if self.phase != "player_select":
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            # カーソルを上に移動（0 の上は 3 に折り返し）
            self.cursor = (self.cursor - 1) % len(COMMANDS)

        elif event.key in (pygame.K_DOWN, pygame.K_s):
            # カーソルを下に移動
            self.cursor = (self.cursor + 1) % len(COMMANDS)

        elif event.key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
            # 決定キー → コマンドを実行
            self._execute_command()

    # ──────────────────────────────────────────────────────
    #  コマンド実行
    # ──────────────────────────────────────────────────────
    def _execute_command(self):
        """カーソル位置のコマンドを実行する"""
        name, implemented = COMMANDS[self.cursor]

        # 未実装コマンドは無視
        if not implemented:
            self._add_log(f"「{name}」はまだ使えない...")
            return

        if name == "攻撃":
            self._start_player_attack()

        elif name == "逃げる":
            self._try_escape()

    def _start_player_attack(self):
        """プレイヤー攻撃フェーズを開始する"""
        self.phase      = "player_anim"
        self.anim_timer = 0
        self.slash_timer = 0
        self._add_log(f"ノービスの攻撃！")

    def _try_escape(self):
        """逃走を試みる"""
        if random.random() < ESCAPE_CHANCE:
            self._add_log("うまく逃げ出した！")
            self.phase        = "result"
            self.result_text  = "逃走成功"
            self.result_timer = ANIM_RESULT
            self._result      = "escape"
        else:
            self._add_log("逃げられなかった！")
            # 逃げ失敗 → 敵のターンへ
            self._start_enemy_turn()

    # ──────────────────────────────────────────────────────
    #  毎フレーム更新
    # ──────────────────────────────────────────────────────
    def update(self) -> str | None:
        """
        毎フレーム呼ぶ。
        戻り値:
          None     : バトル継続中
          "win"    : プレイヤーの勝利
          "lose"   : プレイヤーの敗北
          "escape" : 逃走成功
        """
        self.bg_timer += 1
        self.anim_timer += 1

        # ダメージ数値（プレイヤー側）のフェードアウト
        self.player_floats = [
            {**ft, "y": ft["y"] - 1, "life": ft["life"] - 1}
            for ft in self.player_floats if ft["life"] > 0
        ]

        # 敵ヒットタイマー
        if self.enemy.hit_timer > 0:
            self.enemy.hit_timer -= 1

        # ── フェーズごとの処理
        if self.phase == "player_anim":
            self._update_player_anim()

        elif self.phase == "enemy_anim":
            self._update_enemy_anim()

        elif self.phase == "result":
            self.result_timer -= 1
            if self.result_timer <= 0:
                return self._result   # バトル終了を通知

        return None  # バトル継続中

    # ──────────────────────────────────────────────────────
    #  プレイヤー攻撃アニメーション
    # ──────────────────────────────────────────────────────
    def _update_player_anim(self):
        """
        プレイヤー攻撃の3段階アニメーション:
          1. 前進（ANIM_FORWARD フレーム）
          2. 剣エフェクト＋ダメージ計算（ANIM_SLASH フレーム）
          3. 後退（ANIM_BACK フレーム）→ 敵ターンへ
        """
        total = ANIM_FORWARD + ANIM_SLASH + ANIM_BACK

        if self.anim_timer <= ANIM_FORWARD:
            # 段階1: 前進（右に近づく）
            progress    = self.anim_timer / ANIM_FORWARD
            self.player_x = PLAYER_BATTLE_X + int(120 * progress)

        elif self.anim_timer == ANIM_FORWARD + 1:
            # 段階2開始: ダメージ計算（1回だけ実行）
            self.slash_timer = ANIM_SLASH
            dmg = self.enemy.take_damage(self.player.atk)
            # ダメージ数値をセット（敵の中心上部に表示）
            # enemy.float_texts の y を敵バトル位置に合わせて上書き
            if self.enemy.float_texts:
                ft = self.enemy.float_texts[-1]
                ft["x"] = ENEMY_BATTLE_X
                ft["y"] = ENEMY_BATTLE_Y - 60
            self._add_log(f"  {dmg} のダメージ！")

            # 敵を倒したか確認
            if not self.enemy.alive:
                self._add_log(f"{self.enemy.name} を倒した！")

        elif self.anim_timer <= ANIM_FORWARD + ANIM_SLASH:
            # 段階2: 剣エフェクト中
            self.slash_timer = max(0, self.slash_timer - 1)

        elif self.anim_timer <= total:
            # 段階3: 後退（元の位置に戻る）
            progress    = (self.anim_timer - ANIM_FORWARD - ANIM_SLASH) / ANIM_BACK
            self.player_x = PLAYER_BATTLE_X + int(120 * (1 - progress))

        else:
            # アニメーション完了
            self.player_x  = PLAYER_BATTLE_X
            self.slash_timer = 0

            # 敵が死んでいたら勝利
            if not self.enemy.alive:
                self.phase        = "result"
                self.result_text  = "勝利！"
                self.result_timer = ANIM_RESULT
                self._result      = "win"
            else:
                # 生きていたら敵のターンへ
                self._start_enemy_turn()

    # ──────────────────────────────────────────────────────
    #  敵ターン
    # ──────────────────────────────────────────────────────
    def _start_enemy_turn(self):
        """敵のターンを開始する"""
        self.phase      = "enemy_anim"
        self.anim_timer = 0
        self._add_log(f"{self.enemy.name}の攻撃！")

    def _update_enemy_anim(self):
        """
        敵攻撃の3段階アニメーション（左に近づいて戻る）
        """
        total = ANIM_FORWARD + ANIM_SLASH + ANIM_BACK

        if self.anim_timer == ANIM_FORWARD + 1:
            # ダメージ計算（1回だけ）
            raw  = self.enemy.do_attack()
            dmg  = self.player.take_damage(raw)
            self._add_log(f"  {dmg} のダメージ！")
            # プレイヤー側のダメージ数値を追加
            self.player_floats.append({
                "text" : str(dmg),
                "x"    : PLAYER_BATTLE_X,
                "y"    : PLAYER_BATTLE_Y - 60,
                "life" : 50,
                "color": C_CRIMSON_LT,
            })

        if self.anim_timer > total:
            # アニメーション完了 → プレイヤーが生きていればコマンド待機へ
            if self.player.is_dead:
                self.phase        = "result"
                self.result_text  = "敗北..."
                self.result_timer = ANIM_RESULT
                self._result      = "lose"
            else:
                self.phase      = "player_select"
                self.anim_timer = 0
                self._add_log("コマンドを選んでください")

    # ──────────────────────────────────────────────────────
    #  ログ管理
    # ──────────────────────────────────────────────────────
    def _add_log(self, text: str):
        """バトルログに1行追加する（最新4件を表示）"""
        self.log.insert(0, text)
        if len(self.log) > 8:
            self.log.pop()

    # ──────────────────────────────────────────────────────
    #  描画
    # ──────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface):
        """バトル画面全体を描く（毎フレーム呼ぶ）"""
        self._draw_background(surface)
        self._draw_player(surface)
        self.enemy.draw_battle(surface, ENEMY_BATTLE_X, ENEMY_BATTLE_Y,
                               self.font_md, self.font_sm,
                               sprite_mgr=self.sprite_mgr)
        self._draw_slash_effect(surface)
        self._draw_player_floats(surface)
        self._draw_command_window(surface)

        # 結果表示
        if self.phase == "result":
            self._draw_result(surface)

    # ── バトル背景 ────────────────────────────────────────
    def _draw_background(self, surface: pygame.Surface):
        """バトル背景（暗い床 + グリッド + 装飾）"""
        surface.fill(C_BATTLE_BG)

        # 薄いグリッドライン（奥行き感）
        grid_color = (20, 16, 35)
        for x in range(0, WINDOW_W, 40):
            pygame.draw.line(surface, grid_color, (x, 0), (x, BATTLE_TOP_H), 1)
        for y in range(0, BATTLE_TOP_H, 40):
            pygame.draw.line(surface, grid_color, (0, y), (WINDOW_W, y), 1)

        # 床（下部の帯）
        floor_rect = pygame.Rect(0, BATTLE_TOP_H - 60, WINDOW_W, 60)
        pygame.draw.rect(surface, (18, 14, 30), floor_rect)
        pygame.draw.line(surface, C_GOLD,
                         (0, BATTLE_TOP_H - 60), (WINDOW_W, BATTLE_TOP_H - 60), 1)

        # 背景の装飾（右上のルーン風円）
        t = self.bg_timer * 0.005
        for i in range(3):
            r   = 80 + i * 30
            alp = 18 - i * 4
            ang = t + i * math.pi / 3
            cx  = int(WINDOW_W * 0.72 + math.cos(ang) * 10)
            cy  = int(BATTLE_TOP_H * 0.35 + math.sin(ang) * 10)
            s   = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 50, 120, alp), (r, r), r, 1)
            surface.blit(s, (cx - r, cy - r))

    # ── プレイヤー描画（バトル用） ──────────────────────────
    def _draw_player(self, surface: pygame.Surface):
        """
        ★ 0.3: player.draw_battle() に委譲することで
                スプライット/図形フォールバックを player.py に一元管理
        """
        self.player.draw_battle(
            surface,
            px         = self.player_x,
            py         = self.player_y,
            font_md    = self.font_md,
            font_sm    = self.font_sm,
            sprite_mgr = self.sprite_mgr,
        )
        # プレイヤー側ダメージ数値の浮き上がり（battle 固有）
        for ft in self.player_floats:
            alpha   = int(255 * ft["life"] / 50)
            dmg_txt = self.font_md.render(ft["text"], True, ft["color"])
            dmg_txt.set_alpha(alpha)
            surface.blit(dmg_txt, (ft["x"] - dmg_txt.get_width() // 2, ft["y"]))

    # ── 剣エフェクト ──────────────────────────────────────
    def _draw_slash_effect(self, surface: pygame.Surface):
        """プレイヤー攻撃時の剣閃エフェクト"""
        if self.slash_timer <= 0:
            return

        progress = self.slash_timer / ANIM_SLASH   # 1.0 → 0.0
        alpha    = int(progress * 200)
        cx       = ENEMY_BATTLE_X - 30
        cy       = ENEMY_BATTLE_Y

        # 複数の斜め線で剣閃を表現
        for i in range(4):
            angle  = math.pi * 0.3 + i * 0.15
            length = 60 + i * 10
            x1 = int(cx - math.cos(angle) * length * 0.3)
            y1 = int(cy - math.sin(angle) * length * 0.3)
            x2 = int(cx + math.cos(angle) * length * 0.7)
            y2 = int(cy + math.sin(angle) * length * 0.7)

            s = pygame.Surface((WINDOW_W, BATTLE_TOP_H), pygame.SRCALPHA)
            a = max(0, min(255, int(alpha - i * 30)))

            pygame.draw.line(
              s,
             (*C_GOLD, a),
             (x1, y1),
             (x2, y2),
              3 - i // 2
)
            surface.blit(s, (0, 0))

    # ── プレイヤーダメージ数値 ────────────────────────────
    def _draw_player_floats(self, surface: pygame.Surface):
        """プレイヤー側のダメージ数値（_draw_player内で描いているので空）"""
        pass  # _draw_player() の中で描画済み

    # ── コマンドウィンドウ ────────────────────────────────
    def _draw_command_window(self, surface: pygame.Surface):
        """
        画面下部のコマンドウィンドウを描く。
        左：バトルログ（メッセージ）
        右：コマンド一覧
        """
        # ウィンドウ背景
        win_rect = pygame.Rect(0, BATTLE_CMD_Y, WINDOW_W, BATTLE_CMD_H)
        pygame.draw.rect(surface, C_WINDOW_BG, win_rect)
        pygame.draw.rect(surface, C_WINDOW_BORDER, win_rect, 2)
        pygame.draw.line(surface, C_GOLD,
                         (0, BATTLE_CMD_Y + 1), (WINDOW_W, BATTLE_CMD_Y + 1), 1)

        # ── 左側：バトルログ（最新4件）
        log_x = 20
        log_y = BATTLE_CMD_Y + 16
        for i, line in enumerate(self.log[:4]):
            alpha = 255 if i == 0 else max(100, 200 - i * 40)
            txt   = self.font_sm.render(line, True, C_WHITE)
            txt.set_alpha(alpha)
            surface.blit(txt, (log_x, log_y + i * 22))

        # ── 区切り線
        pygame.draw.line(surface, C_WINDOW_BORDER,
                         (WINDOW_W - 200, BATTLE_CMD_Y + 10),
                         (WINDOW_W - 200, WINDOW_H - 10), 1)

        # ── 右側：コマンド一覧
        cmd_x   = WINDOW_W - 185
        cmd_y   = BATTLE_CMD_Y + 20
        cmd_gap = 44

        for i, (name, implemented) in enumerate(COMMANDS):
            is_selected = (i == self.cursor) and (self.phase == "player_select")

            # 色の選択
            if not implemented:
                color = C_CMD_DISABLED
            elif is_selected:
                color = C_CMD_SELECT
            else:
                color = C_CMD_NORMAL

            # 選択中はハイライト背景
            if is_selected:
                hl = pygame.Rect(cmd_x - 12, cmd_y + i * cmd_gap - 6, 165, 34)
                pygame.draw.rect(surface, (40, 32, 60), hl, border_radius=4)
                pygame.draw.rect(surface, C_GOLD, hl, 1, border_radius=4)

            # カーソル（▶）
            if is_selected:
                cur = self.font_md.render("▶", True, C_GOLD)
                surface.blit(cur, (cmd_x - 24, cmd_y + i * cmd_gap))

            # コマンド名
            cmd_txt = self.font_md.render(name, True, color)
            surface.blit(cmd_txt, (cmd_x, cmd_y + i * cmd_gap))

            # 未実装バッジ
            if not implemented:
                badge = self.font_sm.render("準備中", True, (80, 70, 90))
                surface.blit(badge, (cmd_x + 80, cmd_y + i * cmd_gap + 4))

        # 操作説明（下端）
        hint = self.font_sm.render("↑↓ 選択   Z/Enter 決定", True, (60, 55, 80))
        surface.blit(hint, (cmd_x - 12, WINDOW_H - 22))

    # ── 結果表示 ──────────────────────────────────────────
    def _draw_result(self, surface: pygame.Surface):
        """勝利・敗北・逃走の結果オーバーレイ"""
        alpha   = min(160, (ANIM_RESULT - self.result_timer) * 4)
        overlay = pygame.Surface((WINDOW_W, BATTLE_TOP_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        surface.blit(overlay, (0, 0))

        # 結果テキストの色
        if self._result == "win":
            color = C_GOLD
        elif self._result == "lose":
            color = C_CRIMSON_LT
        else:
            color = (180, 180, 220)

        txt = self.font_lg.render(self.result_text, True, color)
        surface.blit(txt, (WINDOW_W // 2 - txt.get_width() // 2,
                           BATTLE_TOP_H // 2 - txt.get_height() // 2))
