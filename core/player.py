"""
============================================================
  core/player.py  ── プレイヤー「ノービス」クラス  [0.5 更新]

  [0.5 変更点]
    - element プロパティを追加
      現在ジョブの "element" キーを返す（例: "fire" / "earth" / "none"）
      battle.py が Step8 で属性相性計算に使用する予定
    - learned_skills を追加
      現在ジョブの "skills" キーをリストで保持する
      battle.py が Step8 でスキルメニュー構築に使用する予定
    - change_job() に learned_skills 更新を追加
      ジョブチェンジ時に新ジョブのスキルリストへ自動更新

  [0.4 変更点（継続）]
    - current_job    : 現在のジョブID（"novice" / "fighter" / "mage"）
    - change_job()   : ジョブチェンジメソッド
    - sprite_key     : ジョブ辞書から自動で決まる
    - draw_battle()  : 名前ラベルをジョブ名で表示
    - _do_level_up() : ジョブごとのレベルアップ成長量を使用

  [0.3 変更点（継続）]
    - draw()        : スプライト画像に対応（なければ図形描画）
    - draw_battle() : バトル画面用の大きなスプライト描画に対応

  [変更なし]
    - 移動・当たり判定・攻撃・EXP・レベルアップのロジック
============================================================
"""

import pygame
from .action_log import ActionLog
from .utils import make_rgba, lerp_alpha
from .job_data import get_job, DEFAULT_JOB_ID  # ★ 0.4: ジョブデータ
from .constants import (
    TILE,
    PLAYER_SPEED,
    PLAYER_ATTACK_CD,
    GAME_AREA_H,
    WINDOW_W,
    C_WHITE,
    C_GOLD,
    C_CRIMSON_LT,
    C_DARK_BG,
    EXP_TABLE,
)


class Player:
    """
    プレイヤーキャラクター。

    使い方:
        player = Player(x=100, y=100)
        player.update(walls)                        # 毎フレーム（探索）
        player.draw(surface, sprite_manager)        # 探索マップ描画
        player.draw_battle(surface, px, py, ...)    # バトル画面描画
        player.change_job("fighter")                # ジョブチェンジ
    """

    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x, y, TILE - 4, TILE - 4)

        # ── ★ 0.4: ジョブ管理
        # current_job_id : ジョブ辞書のキー（"novice" / "fighter" / "mage"）
        self.current_job_id: str = DEFAULT_JOB_ID
        # current_job     : ジョブデータの辞書（get_job() で取得）
        self.current_job: dict = get_job(DEFAULT_JOB_ID)

        # ── ベースステータス（ジョブボーナスを加算する前の値）
        # ジョブチェンジしてもリセットされない「プレイヤー本来の力」
        self._base_max_hp = 30
        self._base_atk = 8
        self._base_defense = 2

        # ── 表示ステータス（ベース + ジョブボーナスの合計）
        # ゲーム内でダメージ計算などに使うのはこちら
        self.level = 1
        self.exp = 0
        self.max_hp = self._calc_max_hp()
        self.hp = self.max_hp
        self.atk = self._calc_atk()
        self.defense = self._calc_defense()

        # ── タイマー類
        self.attack_cd = 0
        self.attack_effect_timer = 0
        self.hit_timer = 0
        self.levelup_timer = 0

        # ── 向き・アニメ
        self.direction = "right"
        self.attack_rect: pygame.Rect | None = None
        self.trail: list[tuple[int, int, int]] = []

        # ── ★ 0.5: スキルリスト
        # 現在ジョブが使えるスキルIDのリスト。
        # ジョブチェンジ時は change_job() が自動で更新する。
        # battle.py が Step8 でスキルメニュー構築に参照する。
        self.learned_skills: list[str] = list(self.current_job.get("skills", []))
        self.action_log = ActionLog()

    # ──────────────────────────────────────────────────────
    #  ★ 0.4: ジョブ関連
    # ──────────────────────────────────────────────────────

    @property
    def sprite_key(self) -> str:
        """
        現在のジョブに対応するスプライトキーを返す。
        SpriteManager.get_player() に渡す。

        例:
            "novice"  → "novice_m"
            "fighter" → "fighter_m"
            "mage"    → "mage_m"
        """
        return self.current_job.get("sprite_key", "novice_m")

    @property
    def job_name(self) -> str:
        """現在のジョブ名（日本語）を返す。HUD・バトル表示に使う。"""
        return self.current_job.get("name", "ノービス")

    @property
    def job_color(self) -> tuple:
        """現在のジョブのカラーを返す。HUD の装飾に使う。"""
        return self.current_job.get("color", C_WHITE)

    @property
    def element(self) -> str:
        """
        現在ジョブの属性IDを返す。  ★ 0.5 追加
        element_system.get_multiplier() に渡して相性計算に使う。

        例:
            novice  → "none"
            fighter → "earth"
            mage    → "fire"
        """
        return self.current_job.get("element", "none")

    def _calc_max_hp(self) -> int:
        """ベースHP + ジョブボーナスを合計して返す"""
        return self._base_max_hp + self.current_job.get("hp_bonus", 0)

    def _calc_atk(self) -> int:
        """ベースATK + ジョブボーナスを合計して返す"""
        return self._base_atk + self.current_job.get("atk_bonus", 0)

    def _calc_defense(self) -> int:
        """ベースDEF + ジョブボーナスを合計して返す"""
        return max(0, self._base_defense + self.current_job.get("def_bonus", 0))

    def change_job(self, new_job_id: str) -> bool:
        """
        ジョブチェンジを実行する。

        引数:
            new_job_id : 変更先ジョブID（"fighter" / "mage" など）

        戻り値:
            True  : チェンジ成功
            False : 同じジョブ or 存在しないジョブ → 変更なし

        処理内容:
            1. ジョブデータを差し替える
            2. ステータスを再計算（ジョブボーナスの付け替え）
            3. HPは最大HPに変わっても現在HPの割合を維持する
        """
        from .job_data import JOB_DATA

        # 同じジョブまたは存在しないジョブは変更なし
        if new_job_id == self.current_job_id:
            return False
        if new_job_id not in JOB_DATA:
            return False

        # HP割合を記録（チェンジ後も比率を維持するため）
        hp_ratio = self.hp / max(1, self.max_hp)

        # ジョブを変更
        self.current_job_id = new_job_id
        self.current_job = get_job(new_job_id)

        # ステータスを再計算
        self.max_hp = self._calc_max_hp()
        self.atk = self._calc_atk()
        self.defense = self._calc_defense()

        # HP は変更前の割合を引き継ぐ（最低1）
        self.hp = max(1, int(self.max_hp * hp_ratio))

        # ★ 0.5: 新ジョブのスキルリストに更新
        self.learned_skills = list(self.current_job.get("skills", []))

        return True

    # ──────────────────────────────────────────────────────
    #  移動・当たり判定（変更なし）
    # ──────────────────────────────────────────────────────
    def update(self, walls: list[pygame.Rect]):
        """毎フレーム呼ぶ。キー入力を読んで移動し壁との当たり判定を行う。"""
        keys = pygame.key.get_pressed()
        vx, vy = 0, 0

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            vx = -PLAYER_SPEED
            self.direction = "left"
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            vx = PLAYER_SPEED
            self.direction = "right"
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            vy = -PLAYER_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            vy = PLAYER_SPEED

        if vx != 0 and vy != 0:
            vx = int(vx * 0.707)
            vy = int(vy * 0.707)

        self.rect.x += vx
        for wall in walls:
            if self.rect.colliderect(wall):
                if vx > 0:
                    self.rect.right = wall.left
                else:
                    self.rect.left = wall.right

        self.rect.y += vy
        for wall in walls:
            if self.rect.colliderect(wall):
                if vy > 0:
                    self.rect.bottom = wall.top
                else:
                    self.rect.top = wall.bottom

        self.rect.clamp_ip(pygame.Rect(0, 0, WINDOW_W, GAME_AREA_H))

        if vx != 0 or vy != 0:
            self.trail.append((self.rect.centerx, self.rect.centery, 160))
        self.trail = [(x, y, a - 18) for x, y, a in self.trail if a > 0]

        if self.attack_cd > 0:
            self.attack_cd -= 1
        if self.hit_timer > 0:
            self.hit_timer -= 1
        if self.attack_effect_timer > 0:
            self.attack_effect_timer -= 1
        if self.levelup_timer > 0:
            self.levelup_timer -= 1
        if self.attack_effect_timer <= 0:
            self.attack_rect = None

    # ──────────────────────────────────────────────────────
    #  攻撃・ダメージ（変更なし）
    # ──────────────────────────────────────────────────────
    def try_attack(self) -> bool:
        if self.attack_cd > 0:
            return False
        attack_w = TILE + 8
        ax = self.rect.right if self.direction == "right" else self.rect.left - attack_w
        self.attack_rect = pygame.Rect(ax, self.rect.top, attack_w, self.rect.height)
        self.attack_cd = PLAYER_ATTACK_CD
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

    # ──────────────────────────────────────────────────────
    #  経験値・レベルアップ（★ 0.4: ジョブ成長量を使用）
    # ──────────────────────────────────────────────────────
    def gain_exp(self, amount: int) -> bool:
        """経験値を加算。レベルアップした場合は True を返す。"""
        self.exp += amount
        if self.level < len(EXP_TABLE) - 1:
            if self.exp >= EXP_TABLE[self.level]:
                self._do_level_up()
                return True
        return False

    def _do_level_up(self):
        """
        レベルアップ処理。
        ★ 0.4: ジョブデータの lv_up_* を使って成長量を決める。
        ジョブによって伸び方が変わる（ファイター→HP多め、メイジ→ATK多め）
        """
        self.level += 1

        # ジョブの成長量を取得
        lv_hp = self.current_job.get("lv_up_hp", 8)
        lv_atk = self.current_job.get("lv_up_atk", 3)
        lv_def = self.current_job.get("lv_up_def", 1)

        # ベースステータスを伸ばす（ジョブボーナスの二重加算を避けるため）
        self._base_max_hp += lv_hp
        self._base_atk += lv_atk
        self._base_defense += lv_def

        # 表示ステータスを再計算（ジョブボーナスも含む）
        self.max_hp = self._calc_max_hp()
        self.atk = self._calc_atk()
        self.defense = self._calc_defense()
        self.hp = self.max_hp  # HP全回復

        self.levelup_timer = 90

    def exp_to_next(self) -> int:
        if self.level >= len(EXP_TABLE) - 1:
            return 0
        return EXP_TABLE[self.level] - self.exp

    def exp_progress(self) -> float:
        if self.level >= len(EXP_TABLE) - 1:
            return 1.0
        prev = EXP_TABLE[self.level - 1]
        nxt = EXP_TABLE[self.level]
        return (self.exp - prev) / max(1, nxt - prev)

    # ──────────────────────────────────────────────────────
    #  探索マップ描画（変更なし）
    # ──────────────────────────────────────────────────────
    def draw(self, surface: pygame.Surface, sprite_mgr=None):
        """探索マップ上のプレイヤーを描く。スプライトがなければ図形で代替。"""
        # 足跡エフェクト
        for tx, ty, alpha in self.trail:
            s = pygame.Surface((6, 6), pygame.SRCALPHA)
            s.fill(make_rgba(*C_GOLD, alpha))
            surface.blit(s, (tx - 3, ty - 3))

        # スプライト描画を試みる
        img = None
        if sprite_mgr is not None:
            img = sprite_mgr.get_player(
                self.sprite_key, size=(self.rect.width, self.rect.height)
            )

        if img is not None:
            if self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0:
                img = img.copy()
                red = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                red.fill((220, 60, 60, 140))
                img.blit(red, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            if self.direction == "left":
                img = pygame.transform.flip(img, True, False)
            surface.blit(img, (self.rect.x, self.rect.y))
        else:
            # フォールバック：図形描画
            body_color = (
                C_CRIMSON_LT
                if (self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0)
                else C_WHITE
            )
            pygame.draw.rect(surface, body_color, self.rect, border_radius=5)
            head_cx, head_cy = self.rect.centerx, self.rect.top + 8
            pygame.draw.circle(surface, body_color, (head_cx, head_cy), 7)
            eye_dx = 3 if self.direction == "right" else -3
            pygame.draw.circle(surface, C_DARK_BG, (head_cx + eye_dx, head_cy - 1), 2)
            sx, ex = (
                (self.rect.right - 2, self.rect.right + 10)
                if self.direction == "right"
                else (self.rect.left + 2, self.rect.left - 10)
            )
            pygame.draw.line(
                surface, C_GOLD, (sx, self.rect.centery), (ex, self.rect.centery - 6), 2
            )

        # 攻撃エフェクト
        if self.attack_rect and self.attack_effect_timer > 0:
            alpha = lerp_alpha(self.attack_effect_timer, 10, max_alpha=160)
            s = pygame.Surface(
                (self.attack_rect.width, self.attack_rect.height), pygame.SRCALPHA
            )
            s.fill(make_rgba(*C_GOLD, alpha))
            surface.blit(s, (self.attack_rect.x, self.attack_rect.y))

        # HP バー（頭上）
        bar_w = self.rect.width
        ratio = max(0.0, self.hp / self.max_hp)
        pygame.draw.rect(
            surface, (40, 10, 10), (self.rect.x, self.rect.top - 8, bar_w, 4)
        )
        pygame.draw.rect(
            surface,
            C_CRIMSON_LT,
            (self.rect.x, self.rect.top - 8, int(bar_w * ratio), 4),
        )

    # ──────────────────────────────────────────────────────
    #  バトル画面描画（★ 0.4: 名前表示をジョブ名に変更）
    # ──────────────────────────────────────────────────────
    def draw_battle(
        self,
        surface: pygame.Surface,
        px: int,
        py: int,
        font_md: pygame.font.Font,
        font_sm: pygame.font.Font,
        sprite_mgr=None,
    ):
        """バトル画面用の大きなプレイヤーを描く。"""
        BATTLE_SIZE = (96, 96)
        img = None
        if sprite_mgr is not None:
            img = sprite_mgr.get_player(self.sprite_key, size=BATTLE_SIZE)

        if img is not None:
            draw_img = img
            if self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0:
                draw_img = img.copy()
                red = pygame.Surface(draw_img.get_size(), pygame.SRCALPHA)
                red.fill((220, 60, 60, 140))
                draw_img.blit(red, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            img_rect = draw_img.get_rect(center=(px, py))
            surface.blit(draw_img, img_rect)
            sw, sh = BATTLE_SIZE[0], 14
            shadow_s = pygame.Surface((sw, sh), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_s, (0, 0, 0, 55), (0, 0, sw, sh))
            surface.blit(shadow_s, (px - sw // 2, py + BATTLE_SIZE[1] // 2 - 4))
        else:
            # フォールバック：図形描画
            body_color = (
                C_CRIMSON_LT
                if (self.hit_timer > 0 and (self.hit_timer // 4) % 2 == 0)
                else C_WHITE
            )
            shadow_s = pygame.Surface((70, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_s, (0, 0, 0, 60), (0, 0, 70, 14))
            surface.blit(shadow_s, (px - 35, py + 45))
            body = pygame.Rect(px - 20, py - 10, 40, 55)
            pygame.draw.rect(surface, body_color, body, border_radius=6)
            pygame.draw.circle(surface, body_color, (px, py - 22), 22)
            pygame.draw.circle(surface, (30, 25, 45), (px + 7, py - 24), 4)
            pygame.draw.circle(surface, (30, 25, 45), (px - 7, py - 24), 4)
            pygame.draw.circle(surface, (200, 210, 240), (px + 8, py - 25), 2)
            pygame.draw.line(surface, C_GOLD, (px + 22, py - 5), (px + 46, py - 28), 3)
            pygame.draw.line(
                surface, (180, 140, 60), (px + 28, py), (px + 36, py - 12), 3
            )

        # ★ 0.4: 名前ラベルをジョブ名で表示（ジョブカラーで色分け）
        name_txt = font_md.render(self.job_name, True, self.job_color)
        surface.blit(name_txt, (px - name_txt.get_width() // 2, py - 70))

        # HP バー
        bar_w = 120
        bar_x = px - bar_w // 2
        bar_y = py + 54
        ratio = max(0.0, self.hp / self.max_hp)
        bc = (50, 210, 80) if ratio > 0.5 else C_CRIMSON_LT
        pygame.draw.rect(
            surface, (40, 10, 10), (bar_x, bar_y, bar_w, 10), border_radius=4
        )
        pygame.draw.rect(
            surface, bc, (bar_x, bar_y, int(bar_w * ratio), 10), border_radius=4
        )
        pygame.draw.rect(surface, C_GOLD, (bar_x, bar_y, bar_w, 10), 1, border_radius=4)
        hp_txt = font_sm.render(f"HP {self.hp}/{self.max_hp}", True, C_WHITE)
        surface.blit(hp_txt, (px - hp_txt.get_width() // 2, bar_y + 13))
