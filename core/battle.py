"""
============================================================
  core/battle.py  ── ターン制バトルエンジン  [0.5 Step8-D 更新]

  [0.5 Step8-A 変更点]
    - 通常攻撃に属性相性を接続（get_multiplier 使用）
    - player.element × enemy.element → ダメージ倍率を反映
    - 敵→プレイヤー攻撃も同様に属性倍率を適用
    - 有利/不利/通常でダメージログを分岐

  [0.5 Step8-B 変更点]
    - 「スキル」コマンドを True に変更（選択可能に）
    - phase "skill_select" を追加（スキル一覧ウィンドウ表示）
    - player.learned_skills を使ってスキル一覧を表示
    - ↑↓ で選択、Z/Enter/Space で決定、X/Esc でキャンセル

  [0.5 Step8-C 変更点]
    - スキル選択後に実際にスキルを発動できるよう実装
    - _execute_skill() を新規追加
    - player.atk × skill_power × 属性相性倍率 でダメージ計算
    - observe（power=0.0）はダメージなし・情報スキルとして処理
    - 敵撃破で勝利処理、生存で敵ターンへ進む

  [0.5 Step8-D 変更点]
    - sage_messages を import し、大賢者メッセージをログに追加
    - バトル開始時: get_battle_start_message(enemy.name, enemy.element)
    - 通常攻撃時 : get_affinity_message(player.element, enemy.element)
    - 敵攻撃時   : get_affinity_message(enemy.element, player.element)
    - スキル発動時: get_skill_message(skill_id)
    - observe 使用時: get_observe_message(enemy.name, enemy.element)

  担当機能:
    - コマンド選択（攻撃 / スキル / 合成 / 逃げる）
    - ターン進行管理（プレイヤーターン → 敵ターン → ...）
    - 攻撃アニメーション（前進 → 剣エフェクト → 後退）
    - ダメージ計算と浮き上がり数字（属性倍率込み）
    - スキル発動・属性相性・大賢者メッセージの連携
    - 勝利 / 敗北 / 逃走の判定

  用語:
    phase（フェーズ）= 今バトルが何をしているか
      "player_select" : コマンドを選んでいる
      "skill_select"  : スキル一覧から選んでいる
      "player_anim"   : プレイヤー攻撃アニメーション中
      "enemy_anim"    : 敵の攻撃アニメーション中
      "result"        : 勝利・敗北・逃走の結果表示中
============================================================
"""

import pygame
import math
import random
from .utils import safe_alpha, make_rgba, lerp_alpha  # ★ 0.3.1: alpha安全変換
from .element_system  import get_multiplier             # ★ 0.5: 属性相性倍率
from .sage_messages   import (                          # ★ 0.5 Step8-D: 大賢者メッセージ
    get_battle_start_message,
    get_affinity_message,
    get_skill_message,
    get_observe_message,
)
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
    ("スキル", True),    # ★ 0.5 Step8-B: スキル選択メニューを追加
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

        # ── ★ 0.5 Step8-B: スキルカーソル位置
        # phase が "skill_select" のときに有効。
        # player.learned_skills のインデックスを指す。
        self.skill_cursor: int = 0

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

        # ★ 0.5 Step8-D: バトル開始時の大賢者メッセージ
        sage_start = get_battle_start_message(
            enemy_name    = enemy.name,
            enemy_element = enemy.element,
        )
        self.log.insert(0, sage_start)

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

        # ── ★ 0.5 Step8-B: スキル選択フェーズのキー受付
        if self.phase == "skill_select":
            self._handle_skill_select_key(event.key)
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

        elif name == "スキル":
            self._open_skill_menu()     # ★ 0.5 Step8-B

        elif name == "逃げる":
            self._try_escape()

    # ──────────────────────────────────────────────────────
    #  ★ 0.5 Step8-B: スキル選択メニュー
    # ──────────────────────────────────────────────────────
    def _open_skill_menu(self):
        """
        スキル選択メニューを開く。
        player.learned_skills が空のときはメニューを開かずログを出す。
        """
        skills = self.player.learned_skills
        if not skills:
            self._add_log("使えるスキルがない！")
            return
        # skill_select フェーズへ移行
        self.skill_cursor = 0
        self.phase        = "skill_select"
        self._add_log("スキルを選んでください")

    def _handle_skill_select_key(self, key: int):
        """
        スキル選択フェーズのキー操作を処理する。
        ↑↓ で skill_cursor 移動
        Z / Enter / Space で決定
        X / Esc でキャンセルして player_select へ戻る
        """
        skills = self.player.learned_skills
        if not skills:
            # 万一空になっていたらコマンド選択に戻す
            self.phase = "player_select"
            return

        if key in (pygame.K_UP, pygame.K_w):
            self.skill_cursor = (self.skill_cursor - 1) % len(skills)

        elif key in (pygame.K_DOWN, pygame.K_s):
            self.skill_cursor = (self.skill_cursor + 1) % len(skills)

        elif key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
            # 決定：スキルを発動する（★ Step8-C 実装）
            skill_id = skills[self.skill_cursor]
            self.skill_cursor = 0
            self.phase        = "player_select"  # 一旦戻す（_execute_skill内で上書きあり）
            self._execute_skill(skill_id)

        elif key in (pygame.K_x, pygame.K_ESCAPE):
            # キャンセル：コマンド選択へ戻す
            self._add_log("スキルをキャンセルした")
            self.phase        = "player_select"
            self.skill_cursor = 0

    def _execute_skill(self, skill_id: str):
        """
        スキルを発動してダメージ処理・ターン進行を行う。  ★ Step8-C

        ── 処理フロー ──────────────────────────────────────
        1. skill_data からスキル名・属性・倍率を取得
        2. power == 0.0 → observe など非攻撃スキル → ログだけ出して戻る
        3. power  > 0.0 → ダメージ計算
              raw_atk = int(player.atk × power × 属性相性倍率)
        4. enemy.take_damage(raw_atk) でダメージを与える
        5. 敵が死んだ → 勝利処理へ
           生きている → 敵ターンへ
        """
        from .skill_data      import get_skill_name, get_skill_element, get_skill_power
        from .element_system  import get_multiplier, get_affinity_label

        skill_name  = get_skill_name(skill_id)
        skill_elem  = get_skill_element(skill_id)
        skill_power = get_skill_power(skill_id)

        # ── 非攻撃スキル（power == 0.0）────────────────────
        if skill_power == 0.0:
            if skill_id == "observe":
                self._add_log(f"「{skill_name}」で観察した。")
                self._add_log("解析処理は後で実装")
                # ★ 0.5 Step8-D: observe 専用の大賢者メッセージ
                self._add_log(get_observe_message(
                    enemy_name    = self.enemy.name,
                    enemy_element = self.enemy.element,
                ))
            else:
                self._add_log(f"「{skill_name}」を使った。")
            # ダメージなし・敵ターンなし → そのまま player_select へ
            self.phase = "player_select"
            return

        # ── 攻撃スキル（power > 0.0）────────────────────────
        # ★ 0.5 Step8-D: スキル使用の大賢者メッセージ
        self._add_log(get_skill_message(skill_id))
        # 属性相性倍率を計算
        mult = get_multiplier(skill_elem, self.enemy.element)

        # ダメージ計算：player.atk × skill_power × 属性倍率
        raw_atk = int(self.player.atk * skill_power * mult)

        # 敵にダメージを与える
        dmg = self.enemy.take_damage(raw_atk)

        # ダメージ数値を敵位置に表示
        if self.enemy.float_texts:
            ft = self.enemy.float_texts[-1]
            ft["x"] = ENEMY_BATTLE_X
            ft["y"] = ENEMY_BATTLE_Y - 60

        # ── ダメージログ（属性相性メッセージ付き）
        label = get_affinity_label(mult)
        if label == "有利":
            self._add_log(f"「{skill_name}」  効果は抜群だ！  {dmg} のダメージ！")
        elif label == "不利":
            self._add_log(f"「{skill_name}」  効果はいまひとつ…  {dmg} のダメージ！")
        else:
            self._add_log(f"「{skill_name}」  {dmg} のダメージ！")

        # ── 勝利判定 or 敵ターンへ
        if not self.enemy.alive:
            self._add_log(f"{self.enemy.name} を倒した！")
            self.phase        = "result"
            self.result_text  = "勝利！"
            self.result_timer = ANIM_RESULT
            self._result      = "win"
        else:
            self._start_enemy_turn()

    def _get_skill_display_name(self, skill_id: str) -> str:
        """
        スキルIDから表示名を取得する内部ヘルパー。
        skill_data.py をインポートして名前を引く。
        インポートに失敗したときはスキルIDをそのまま返す（安全設計）。
        """
        try:
            from .skill_data import get_skill_name
            return get_skill_name(skill_id)
        except Exception:
            return skill_id

    def _start_player_attack(self):
        """プレイヤー攻撃フェーズを開始する"""
        self.phase       = "player_anim"
        self.anim_timer  = 0
        self.slash_timer = 0
        self._add_log(f"ノービスの攻撃！")
        # ★ 0.5 Step8-D: 属性相性メッセージ（攻撃開始時）
        self._add_log(get_affinity_message(
            self.player.element, self.enemy.element))

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

            # ★ 0.5: 属性相性倍率を計算
            # player.element と enemy.element から倍率を取得
            # どちらかが "none" の場合は get_multiplier が自動で 1.0 を返す
            mult = get_multiplier(self.player.element, self.enemy.element)

            # 基本 ATK に倍率を掛けて整数化（最低1ダメージ保証は take_damage 側）
            raw_atk = int(self.player.atk * mult)
            dmg = self.enemy.take_damage(raw_atk)

            # ダメージ数値をセット（敵の中心上部に表示）
            if self.enemy.float_texts:
                ft = self.enemy.float_texts[-1]
                ft["x"] = ENEMY_BATTLE_X
                ft["y"] = ENEMY_BATTLE_Y - 60

            # 倍率ログ（通常以外のときだけ表示）
            if mult > 1.0:
                self._add_log(f"  効果は抜群だ！  {dmg} のダメージ！")
            elif mult < 1.0:
                self._add_log(f"  効果はいまひとつ…  {dmg} のダメージ！")
            else:
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
        # ★ 0.5 Step8-D: 属性相性メッセージ（敵攻撃開始時）
        self._add_log(get_affinity_message(
            self.enemy.element, self.player.element))

    def _update_enemy_anim(self):
        """
        敵攻撃の3段階アニメーション（左に近づいて戻る）
        """
        total = ANIM_FORWARD + ANIM_SLASH + ANIM_BACK

        if self.anim_timer == ANIM_FORWARD + 1:
            # ダメージ計算（1回だけ）

            # ★ 0.5: 属性相性倍率を計算（敵→プレイヤー方向）
            mult = get_multiplier(self.enemy.element, self.player.element)

            # do_attack() が返す int に倍率を掛けて整数化
            raw  = int(self.enemy.do_attack() * mult)
            dmg  = self.player.take_damage(raw)

            # 倍率ログ（通常以外のときだけ表示）
            if mult > 1.0:
                self._add_log(f"  効果は抜群だ！  {dmg} のダメージ！")
            elif mult < 1.0:
                self._add_log(f"  効果はいまひとつ…  {dmg} のダメージ！")
            else:
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

        # ★ 0.5 Step8-B: スキル選択中は上にスキルウィンドウを重ねて表示
        if self.phase == "skill_select":
            self._draw_skill_window(surface)

        # 結果表示
        if self.phase == "result":
            self._draw_result(surface)

    # ── ★ 0.5 Step8-B: スキル選択ウィンドウ ─────────────
    def _draw_skill_window(self, surface: pygame.Surface):
        """
        スキル一覧ウィンドウをコマンドウィンドウの上に重ねて描く。
        player.learned_skills の各スキルを縦に並べて表示する。
        """
        from .skill_data import get_skill_name, get_skill_element, get_skill_power
        from .element_system import get_element_name, get_element_color

        skills = self.player.learned_skills

        # ウィンドウサイズ（スキル数に応じて高さを調整）
        WIN_W    = 340
        ROW_H    = 48
        PADDING  = 16
        WIN_H    = PADDING * 2 + ROW_H * max(1, len(skills)) + 30
        wx       = WINDOW_W - WIN_W - 10
        wy       = BATTLE_CMD_Y - WIN_H - 4

        # ウィンドウ背景
        pygame.draw.rect(surface, C_WINDOW_BG,     (wx, wy, WIN_W, WIN_H), border_radius=6)
        pygame.draw.rect(surface, C_WINDOW_BORDER, (wx, wy, WIN_W, WIN_H), 2, border_radius=6)
        pygame.draw.line(surface, C_GOLD,
                         (wx + 1, wy + 30), (wx + WIN_W - 1, wy + 30), 1)

        # タイトル行
        title = self.font_sm.render("── スキル ──", True, C_GOLD)
        surface.blit(title, (wx + WIN_W // 2 - title.get_width() // 2, wy + 8))

        # スキル一覧
        for i, sid in enumerate(skills):
            row_y   = wy + PADDING + 22 + i * ROW_H
            is_sel  = (i == self.skill_cursor)

            # 選択ハイライト
            if is_sel:
                hl = pygame.Rect(wx + 6, row_y - 4, WIN_W - 12, ROW_H - 4)
                pygame.draw.rect(surface, (40, 32, 60), hl, border_radius=4)
                pygame.draw.rect(surface, C_GOLD, hl, 1, border_radius=4)
                # カーソル ▶
                cur = self.font_sm.render("▶", True, C_GOLD)
                surface.blit(cur, (wx + 10, row_y + 4))

            # スキル名（属性カラー）
            elem_id    = get_skill_element(sid)
            elem_color = get_element_color(elem_id)
            name_txt   = self.font_md.render(get_skill_name(sid), True,
                                             C_CMD_SELECT if is_sel else C_CMD_NORMAL)
            surface.blit(name_txt, (wx + 28, row_y + 2))

            # 属性名タグ
            elem_tag = self.font_sm.render(
                f"[{get_element_name(elem_id)}]", True, elem_color)
            surface.blit(elem_tag, (wx + 28, row_y + 22))

            # 倍率
            power_val = get_skill_power(sid)
            if power_val > 0:
                power_txt = self.font_sm.render(
                    f"× {power_val:.1f}", True, C_GRAY)
                surface.blit(power_txt, (wx + WIN_W - 60, row_y + 12))

        # 操作ヒント
        hint = self.font_sm.render("↑↓選択  Z決定  X/Esc戻る", True, (60, 55, 80))
        surface.blit(hint, (wx + WIN_W // 2 - hint.get_width() // 2, wy + WIN_H - 18))

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
            alp = safe_alpha(18 - i * 4)              # safe: 負数をクランプ
            ang = t + i * math.pi / 3
            cx  = int(WINDOW_W * 0.72 + math.cos(ang) * 10)
            cy  = int(BATTLE_TOP_H * 0.35 + math.sin(ang) * 10)
            s   = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, make_rgba(80, 50, 120, alp), (r, r), r, 1)  # safe
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
            alpha   = lerp_alpha(ft["life"], 50)          # safe: float→int→clamp
            dmg_txt = self.font_md.render(ft["text"], True, ft["color"])
            dmg_txt.set_alpha(alpha)
            surface.blit(dmg_txt, (ft["x"] - dmg_txt.get_width() // 2, ft["y"]))

    # ── 剣エフェクト ──────────────────────────────────────
    def _draw_slash_effect(self, surface: pygame.Surface):
        """プレイヤー攻撃時の剣閃エフェクト"""
        if self.slash_timer <= 0:
            return

        progress = self.slash_timer / ANIM_SLASH   # 1.0 → 0.0
        alpha    = lerp_alpha(self.slash_timer, ANIM_SLASH, max_alpha=200)  # safe
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
            pygame.draw.line(s, make_rgba(*C_GOLD, alpha - i * 30), (x1, y1), (x2, y2), 3 - i // 2)  # safe: 負数をクランプ
            surface.blit(s, (0, 0))

    # ── プレイヤーダメージ数値 ────────────────────────────
    def _draw_player_floats(self, surface: pygame.Surface):
        """プレイヤー側のダメージ数値（_draw_player内で描いているので空）"""
        pass  # _draw_player() の中で描画済み

    # ── コマンドウィンドウ ────────────────────────────────
    def _wrap_text(self, text: str, font: "pygame.font.Font", max_width: int) -> list[str]:
        """
        テキストを max_width に収まるよう1文字ずつ折り返して行リストで返す。

        日本語は単語境界が不明確なため、1文字ずつ幅を測定して折り返す。
        半角英数字が続く場合も同じロジックで対応できる。

        引数:
            text      : 折り返したい文字列
            font      : 幅の計測に使うフォント
            max_width : 1行の最大幅（ピクセル）

        戻り値:
            list[str] : 折り返し済みの行リスト（1件以上）

        例:
            _wrap_text("《大賢者》長いメッセージ…", font, 570)
            → ["《大賢者》長いメッセ", "ージ…"]
        """
        lines: list[str] = []
        current = ""

        for char in text:
            test = current + char
            # font.size() でピクセル幅を測定（pygame の組み込み関数）
            w, _ = font.size(test)
            if w <= max_width:
                current = test
            else:
                # 現在行を確定して新しい行を開始
                if current:
                    lines.append(current)
                current = char  # はみ出した文字で次の行を始める

        if current:
            lines.append(current)

        # 万一空になった場合のフォールバック
        return lines if lines else [""]

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

        # ── 左側：バトルログ（最新4件・折り返し対応）
        log_x     = 20
        log_y     = BATTLE_CMD_Y + 16
        # 最大幅 = 区切り線(WINDOW_W-200) の手前 10px 余白
        # = 800 - 200 - 20(log_x) - 10 = 570px
        LOG_MAX_W = WINDOW_W - 200 - log_x - 10

        # ウィンドウ内に収まる最大行数（1行22px、余白を考慮）
        LOG_AREA_H   = BATTLE_CMD_H - 20          # ログエリアの縦ピクセル
        MAX_ROWS     = LOG_AREA_H // 22            # 表示できる最大行数

        # ログを新しい順に折り返し展開し、最大行数に収める
        wrapped_rows: list[tuple[str, int]] = []  # (行テキスト, 元ログのインデックス)
        for log_idx, line in enumerate(self.log[:4]):
            for wrap_line in self._wrap_text(line, self.font_sm, LOG_MAX_W):
                wrapped_rows.append((wrap_line, log_idx))
                if len(wrapped_rows) >= MAX_ROWS:
                    break
            if len(wrapped_rows) >= MAX_ROWS:
                break

        # 行を上から描画
        for row_i, (row_text, log_idx) in enumerate(wrapped_rows):
            # 古いログほど薄く表示（log_idx=0 が最新）
            alpha = 255 if log_idx == 0 else safe_alpha(max(100, 200 - log_idx * 40))
            txt   = self.font_sm.render(row_text, True, C_WHITE)
            txt.set_alpha(alpha)
            surface.blit(txt, (log_x, log_y + row_i * 22))

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
        alpha   = lerp_alpha(ANIM_RESULT - self.result_timer, ANIM_RESULT, max_alpha=160)  # safe
        overlay = pygame.Surface((WINDOW_W, BATTLE_TOP_H), pygame.SRCALPHA)
        overlay.fill(make_rgba(0, 0, 0, alpha))
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
