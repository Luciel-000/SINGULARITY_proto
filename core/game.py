"""
============================================================
  core/game.py  ── ゲーム本体（状態管理・メインループ処理）
                   [0.7 Step5-B 更新]

  [0.7 Step5-B 変更点]
    - dialogue_data.py から会話取得関数を import
    - STATE_DIALOGUE / 会話ウィンドウ色定数を import
    - 会話状態管理変数を追加
      （current_dialogue_id / dialogue_lines / dialogue_speaker /
        dialogue_index / talking_npc）
    - Z キーで近くの NPC に話しかける処理を追加
    - STATE_DIALOGUE: Z/Enter/Space で次ページ、Esc/X で閉じる
    - _start_dialogue / _advance_dialogue / _end_dialogue を追加
    - _draw_dialogue_window() を追加
    - draw() に STATE_DIALOGUE の描画分岐を追加
    - on_end == "sage_activate" はまだ未処理（Step5-C 以降）

  [0.7 Step5-A 変更点（継続）]
    - NPC クラスを import、self.npcs リストを追加
    - town で「謎の老人」が表示される

  [0.6 変更点（継続）]
    - current_zone_id / ゾーン遷移 / マップ名 HUD
============================================================
"""

import pygame
import random
from .utils import safe_alpha, make_rgba
from .constants import (
    WINDOW_W,
    WINDOW_H,
    GAME_AREA_H,
    HUD_H,
    TILE,
    STATE_TITLE,
    STATE_PLAY,
    STATE_BATTLE,
    STATE_LEVELUP,
    STATE_GAMEOVER,
    STATE_DIALOGUE,
    STATE_PROLOGUE,  # ★ 0.7 Step5-B / Step5-D
    C_DARK_BG,
    C_WHITE,
    C_GOLD,
    C_CRIMSON_LT,
    C_GREEN_DIM,
    C_GRAY,
    C_DARK_GRAY,
    C_WINDOW_BG,
    C_WINDOW_BORDER,
    C_DIALOGUE_BG,
    C_DIALOGUE_BORDER,  # ★ 0.7 Step5-B: 会話ウィンドウ色
    C_DIALOGUE_NAME,
    C_DIALOGUE_TEXT,  # ★ 0.7 Step5-B
    SLIME_VARIANTS,
)
from . import constants
from .player import Player, DEFAULT_SUPPORT_SYSTEM_NAME
from .enemy import Enemy
from .world import World
from .battle import Battle
from .font_manager import FontManager
from .sprite_manager import SpriteManager
from .job_data import get_job, get_evolutions, all_job_ids, JOB_DATA, DEFAULT_JOB_ID  # ★ 0.4
from .element_system import (
    get_element_name,
    get_element_color,
)  # ★ 0.5: 属性名・属性カラー
from .npc import NPC  # ★ 0.7: NPC
from .dialogue_data import (  # ★ 0.7 Step5-B: 会話データ
    get_dialogue_lines,
    get_dialogue_speaker,
    get_dialogue_on_end,
)
from .job_unlock import get_unlocked_jobs, get_unlock_reasons
from .save_system import save_game, load_game, get_save_info
from .zone_data import get_zone_name, get_zone_exits, DEFAULT_ZONE_ID, all_zone_ids

# ★ 0.4: ジョブチェンジメニューの状態定数
STATE_JOB_MENU = "job_menu"
STATE_SAVE_MENU = "save_menu"
STATE_SUPPORT_NAME_INPUT = "support_name_input"


class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.state = STATE_TITLE

        self.fm = FontManager()
        self.font_lg = self.fm.lg
        self.font_md = self.fm.md
        self.font_sm = self.fm.sm

        self.sprite_mgr = SpriteManager(base_dir=".")

        self.world: World | None = None
        self.player: Player | None = None
        self.enemies: list[Enemy] = []
        self.battle: Battle | None = None
        self.battle_enemy: Enemy | None = None

        self.messages: list[dict] = []
        self.title_timer = 0
        self.gameover_timer = 0

        # ★ 0.6: 現在のゾーンID（ゲーム開始時は "town"）
        self.current_zone_id: str = "town"
        self.current_zone_name: str = ""

        # ★ 0.7 Step5-B: 会話状態管理変数
        self.current_dialogue_id: str = ""  # 現在表示中の会話ID
        self.dialogue_lines: list[str] = []  # セリフリスト
        self.dialogue_speaker: str = ""  # 話者名
        self.dialogue_index: int = 0  # 現在のページ番号
        self.talking_npc: "NPC | None" = None  # 話しかけている NPC

        # ★ 0.4: ジョブチェンジメニュー用
        # job_menu_options : 現在選択可能なジョブIDのリスト
        # job_menu_cursor  : カーソル位置
        self.job_menu_options: list[str] = []
        self.job_menu_cursor: int = 0
        self.save_menu_options: list[str] = ["save", "load", "cancel"]
        self.save_menu_cursor: int = 0
        self.title_menu_options: list[str] = ["new_game", "load_game", "quit"]
        self.title_menu_cursor: int = 0
        self.support_name_input: str = ""
        # 開発用デバッグ表示トグル（F3 / L キー）
        self.show_debug_overlay: bool = False

    # ──────────────────────────────────────────────────────
    #  ゲーム初期化
    # ──────────────────────────────────────────────────────
    def _init_game(self):
        # ★ 0.6: ゲーム開始は「始まりの町」から
        self.current_zone_id = "town"
        self.world = World(self.current_zone_id)
        self.current_zone_name = self.world.zone_name
        px, py = self.world.player_spawn
        self.player = Player(px, py)
        self.enemies = []
        self.npcs = []  # ★ 0.7: NPC リスト
        self.messages = []
        self.battle = None
        self.battle_enemy = None
        self._add_message(f"ここは {self.world.zone_name}", C_GOLD)
        if constants.DEBUG_MODE:
            self._add_message("J キーでジョブチェンジ", C_GRAY)

        # ★ 0.6: has_enemies=True のゾーンだけ敵をスポーン
        if self.world.has_enemies:
            spawn_positions = self.world.get_enemy_spawns(6)
            for i, (ex, ey) in enumerate(spawn_positions):
                self.enemies.append(
                    Enemy(ex, ey, variant_index=i % len(SLIME_VARIANTS))
                )

        # ★ 0.7: NPC をスポーン（town: 謎の老人、field: なし）
        for nx, ny in self.world.get_npc_spawns():
            self.npcs.append(
                NPC(
                    nx,
                    ny,
                    name="謎の老人",
                    dialogue_id="elder_first",
                    repeat_dialogue_id="elder_repeat",
                )
            )

    def load_save_data(self, data: dict) -> None:
        """セーブデータの world 部分を復元する。"""
        if not isinstance(data, dict):
            return

        world_data = data.get("world") if isinstance(data.get("world"), dict) else {}
        zone_id = world_data.get("current_zone_id")
        if not isinstance(zone_id, str) or zone_id not in all_zone_ids():
            zone_id = DEFAULT_ZONE_ID

        self.current_zone_id = zone_id
        self.world = World(self.current_zone_id)
        self.current_zone_name = self.world.zone_name
        self.enemies = []
        self.npcs = []
        self.battle = None
        self.battle_enemy = None

        if self.world.has_enemies:
            spawn_positions = self.world.get_enemy_spawns(6)
            for i, (ex, ey) in enumerate(spawn_positions):
                self.enemies.append(
                    Enemy(ex, ey, variant_index=i % len(SLIME_VARIANTS))
                )

        for nx, ny in self.world.get_npc_spawns():
            self.npcs.append(
                NPC(
                    nx,
                    ny,
                    name="謎の老人",
                    dialogue_id="elder_first",
                    repeat_dialogue_id="elder_repeat",
                )
            )

    def _load_title_save(self) -> None:
        """タイトル画面でロードしたときにセーブデータを復元して探索状態へ遷移する。"""
        if self.player is None:
            # タイトル画面時は player が None のことがあるため先に生成する
            self.player = Player(0, 0)

        ok, reason = load_game(self.player, game=self)
        if ok:
            self.state = STATE_PLAY
            self._add_message("ロードしました", C_GREEN_DIM)
        else:
            if reason == "no_file":
                self._add_message("セーブデータがありません", C_CRIMSON_LT)
            else:
                self._add_message("ロードに失敗しました", C_CRIMSON_LT)

    def _start_new_game(self) -> None:
        self._init_game()
        self._start_prologue()

    def _handle_title_key(self, key: int) -> None:
        if key in (pygame.K_UP, pygame.K_w):
            self.title_menu_cursor = (self.title_menu_cursor - 1) % len(
                self.title_menu_options
            )
            return

        if key in (pygame.K_DOWN, pygame.K_s):
            self.title_menu_cursor = (self.title_menu_cursor + 1) % len(
                self.title_menu_options
            )
            return

        if key == pygame.K_l:
            self._load_title_save()
            return

        if key not in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
            return

        selected = self.title_menu_options[self.title_menu_cursor]
        if selected == "new_game":
            self._start_new_game()
        elif selected == "load_game":
            self._load_title_save()
        elif selected == "quit":
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ──────────────────────────────────────────────────────
    #  イベント処理
    # ──────────────────────────────────────────────────────
    def get_support_system_display_name(self) -> str:
        name = DEFAULT_SUPPORT_SYSTEM_NAME
        if self.player and hasattr(self.player, "support_system_name"):
            player_name = getattr(self.player, "support_system_name", "")
            if isinstance(player_name, str) and player_name.strip():
                name = player_name.strip()
        return f"《{name}》"

    def _handle_support_name_input_key(self, event: pygame.event.Event) -> None:
        key = event.key
        if key in (pygame.K_RETURN, pygame.K_z):
            self._finish_support_name_input(self.support_name_input)
            return

        if key == pygame.K_ESCAPE:
            self._finish_support_name_input("")
            return

        if key == pygame.K_BACKSPACE:
            self.support_name_input = self.support_name_input[:-1]
            return

        char = getattr(event, "unicode", "")
        if char and char.isprintable() and len(self.support_name_input) < 12:
            self.support_name_input += char

    def _finish_support_name_input(self, name: str) -> None:
        if self.player and hasattr(self.player, "set_support_system_name"):
            self.player.set_support_system_name(name)
            display_name = self.player.support_system_name
        else:
            display_name = DEFAULT_SUPPORT_SYSTEM_NAME

        self.support_name_input = ""
        self.current_dialogue_id = ""
        self.dialogue_lines = []
        self.dialogue_speaker = ""
        self.dialogue_index = 0
        self.talking_npc = None
        self.state = STATE_PLAY
        self._add_message(f"観測補助機構名を {display_name} に設定しました", C_GOLD)

    def handle_event(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            # バトル中はバトルへ全イベントを渡す
            if self.state == STATE_BATTLE and self.battle:
                self.battle.handle_event(event)
            return

        key = event.key

        # DEBUG_MODE のときだけ F5/F9 でセーブ/ロードを行う
        if constants.DEBUG_MODE and key == pygame.K_F5:
            ok = save_game(
                self.player, world_data={"current_zone_id": self.current_zone_id}
            )
            if ok:
                self._add_message("セーブしました", C_GRAY)
            else:
                self._add_message("セーブに失敗しました", C_CRIMSON_LT)
            return

        if constants.DEBUG_MODE and key == pygame.K_F9:
            ok, reason = load_game(self.player, game=self)
            if ok:
                self._add_message("ロードしました", C_GREEN_DIM)
            else:
                if reason == "no_file":
                    self._add_message("セーブデータがありません", C_CRIMSON_LT)
                else:
                    self._add_message("ロードに失敗しました", C_CRIMSON_LT)
            return

        if constants.DEBUG_MODE and key == pygame.K_F6:
            if self.player and hasattr(self.player, "set_support_system_name"):
                self.player.set_support_system_name("ルシエル")
                self._add_message(
                    "観測補助機構名を ルシエル に設定しました", C_GOLD
                )
            return

        # ── タイトル
        if self.state == STATE_TITLE:
            self._handle_title_key(key)
            return

        # DEBUG_MODE のときだけ表示トグルを許可（F3 または L）
        if self.state == STATE_SUPPORT_NAME_INPUT:
            self._handle_support_name_input_key(event)
            return

        if constants.DEBUG_MODE and key in (pygame.K_F3, pygame.K_l):
            self.show_debug_overlay = not getattr(self, "show_debug_overlay", False)
            status = "ON" if self.show_debug_overlay else "OFF"
            self._add_message(f"DEBUG OVERLAY {status}", C_GRAY)
            return

        # ── プロローグ
        if self.state == STATE_PROLOGUE:
            if key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
                self._advance_dialogue()
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

        if self.state == STATE_SAVE_MENU:
            self._handle_save_menu_key(key)
            return

        # ── 会話中 ★ 0.7 Step5-B
        if self.state == STATE_DIALOGUE:
            if key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
                self._advance_dialogue()
            elif key in (pygame.K_ESCAPE, pygame.K_x):
                self._end_dialogue()
            return

        # ── 探索マップ中
        if self.state in (STATE_PLAY, STATE_LEVELUP):
            if key == pygame.K_j:
                # J キーでジョブメニューを開く（DEBUG_MODE が有効な場合のみ）
                if constants.DEBUG_MODE:
                    self._open_job_menu()
            elif key == pygame.K_ESCAPE:
                self._open_save_menu()
            elif key == pygame.K_z:
                if self._try_investigate_shrine_altar():
                    return
                if self._try_offer_shrine_fragment():
                    return
                if self._try_collect_shrine_fragment():
                    return
                # ★ 0.7 Step5-B: Z キーで近くの NPC に話しかける
                for npc in self.npcs:
                    if npc.is_near(self.player.rect):
                        self._start_dialogue(npc)
                        break

    def _open_job_menu(self):
        """
        ジョブチェンジメニューを開く。
        現在のジョブから変更できるジョブ一覧を取得して表示する。
        """
        if not self.player:
            return

        # ジョブメニューを開く直前に行動ログで解放判定を行い、
        # 新規解放があれば player.unlocked_jobs に追加して通知する
        if hasattr(self.player, "update_unlocked_jobs"):
            newly = self.player.update_unlocked_jobs()
            for jid in newly:
                job = get_job(jid)
                self._add_message(
                    f"新しいジョブ候補が解放されました：{job['name']}", C_GOLD
                )

        # 現在のジョブから選択可能なジョブを取得
        if constants.DEBUG_MODE:
            # 開発用チート：全ジョブを選択可能にする
            options = [
                jid for jid in all_job_ids() if jid != self.player.current_job_id
            ]
        else:
            # 通常時：解放済みの進化先ジョブのみ表示
            options = [
                jid
                for jid in get_evolutions(self.player.current_job_id)
                if jid in self.player.unlocked_jobs
            ]

        # 現在のジョブも「戻る」として含める（ノービスに戻れるなど）
        # ただし同じジョブへのチェンジは change_job() 側で弾く
        if not options:
            self._add_message("このジョブから変更できるジョブがありません", C_GRAY)
            return

        self.job_menu_options = options
        self.job_menu_cursor = 0
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

        new_job = get_job(new_job_id)
        job_name = new_job["name"]

        if not constants.DEBUG_MODE and not self.player.is_job_unlocked(new_job_id):
            self._add_message("このジョブはまだ解放されていません", C_GRAY)
            return

        if self.player.change_job(new_job_id):
            self.player.action_log.record_job_change()
            self._add_message(f"ジョブチェンジ：{job_name}！", new_job["color"])
        else:
            self._add_message(f"すでに {job_name} です", C_GRAY)

        self.state = STATE_PLAY

    def _open_save_menu(self):
        """探索中に開くセーブ/ロードメニュー。"""
        if not self.player or not self.world:
            return
        self.save_menu_cursor = 0
        self.state = STATE_SAVE_MENU

    def _handle_save_menu_key(self, key: int):
        """セーブ/ロードメニュー中のキー操作。"""
        options = self.save_menu_options

        if key in (pygame.K_UP, pygame.K_w):
            self.save_menu_cursor = (self.save_menu_cursor - 1) % len(options)

        elif key in (pygame.K_DOWN, pygame.K_s):
            self.save_menu_cursor = (self.save_menu_cursor + 1) % len(options)

        elif key in (pygame.K_ESCAPE, pygame.K_x):
            self.state = STATE_PLAY

        elif key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
            chosen = options[self.save_menu_cursor]
            if chosen == "save":
                self._save_current_slot()
            elif chosen == "load":
                self._load_current_slot()
            else:
                self.state = STATE_PLAY

    def _save_current_slot(self):
        """現在の単一スロットに保存する。"""
        if not self.player:
            self._add_message("セーブに失敗しました", C_CRIMSON_LT)
            self.state = STATE_PLAY
            return

        ok = save_game(
            self.player, world_data={"current_zone_id": self.current_zone_id}
        )
        if ok:
            self._add_message("セーブしました", C_GRAY)
        else:
            self._add_message("セーブに失敗しました", C_CRIMSON_LT)
        self.state = STATE_PLAY

    def _load_current_slot(self):
        """現在の単一スロットからロードする。"""
        if self.player is None:
            self.player = Player(0, 0)

        ok, reason = load_game(self.player, game=self)
        if ok:
            self.state = STATE_PLAY
            self._add_message("ロードしました", C_GREEN_DIM)
        else:
            self.state = STATE_PLAY
            if reason == "no_file":
                self._add_message("セーブデータがありません", C_CRIMSON_LT)
            else:
                self._add_message("ロードに失敗しました", C_CRIMSON_LT)

    def _get_save_summary_lines(self) -> list[tuple[str, tuple]]:
        """セーブメニューに表示する単一スロット概要を返す。"""
        exists, info = get_save_info()
        if not exists:
            return [("Slot 1: Empty", C_DARK_GRAY)]

        zone_id = info.get("current_zone_id") or DEFAULT_ZONE_ID
        zone_name = get_zone_name(zone_id)
        job_id = info.get("current_job_id") or DEFAULT_JOB_ID
        if job_id not in JOB_DATA:
            job_id = DEFAULT_JOB_ID
        job = get_job(job_id)
        saved_at = info.get("saved_at") or "Unknown time"
        version = info.get("version") or "unknown"
        return [
            (f"Slot 1: {saved_at}", C_WHITE),
            (f"Zone: {zone_name}   Job: {job['name']}", C_GRAY),
            (f"Version: {version}", C_DARK_GRAY),
        ]

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

        if self.state == STATE_SAVE_MENU:
            return

        if self.state == STATE_PROLOGUE:
            self.messages = [
                {**m, "timer": m["timer"] - 1} for m in self.messages if m["timer"] > 0
            ]
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
                self._set_story_flag("quest_check_field_done", True)
                enemy = self.battle_enemy
                if enemy:
                    leveled = self.player.gain_exp(enemy.exp_val)
                    self._add_message(
                        f"{enemy.name} 撃破！  +{enemy.exp_val} EXP", (100, 220, 100)
                    )
                    if leveled:
                        job = self.player.current_job
                        self._add_message(
                            f"LEVEL UP! Lv{self.player.level}  "
                            f"HP+{job['lv_up_hp']} ATK+{job['lv_up_atk']} DEF+{job['lv_up_def']}",
                            C_GOLD,
                        )
                        self.state = STATE_LEVELUP
                    else:
                        self.state = STATE_PLAY
                else:
                    self.state = STATE_PLAY
                # 行動ログを見て解放候補を更新（自動チェンジは行わない）
                if self.player and hasattr(self.player, "update_unlocked_jobs"):
                    newly = self.player.update_unlocked_jobs()
                    for jid in newly:
                        job = get_job(jid)
                        self._add_message(
                            f"新しいジョブ候補が解放されました：{job['name']}", C_GOLD
                        )
                self.enemies = [e for e in self.enemies if e is not self.battle_enemy]
                self.battle = None
                self.battle_enemy = None
                if not any(e.alive for e in self.enemies):
                    self._respawn_enemies()

            elif result == "lose":
                self.state = STATE_GAMEOVER
                self.gameover_timer = 0
                self.battle = None

            elif result == "escape":
                self.state = STATE_PLAY
                self.battle = None
                self.battle_enemy = None
                self._add_message("逃走した！", C_GRAY)
            return

        if self.state == STATE_PLAY and self.player and self.world:
            self.player.update(self.world.wall_rects)
            self._update_story_progress_by_position()

            # ★ 0.7: NPC を更新（アニメーションタイマー）
            for npc in self.npcs:
                npc.update(self.player.rect)  # ★ 0.6: 出口タイルへの接触でゾーン遷移
            for exit_rect in self.world.exit_rects:
                if self.player.rect.colliderect(exit_rect):
                    self._handle_exit_transition(exit_rect)
                    break

            for enemy in self.enemies:
                enemy.update(self.player.rect, self.world.wall_rects)
                if enemy.alive and enemy.touches_player(self.player.rect):
                    self._start_battle(enemy)
                    break
            self.enemies = [e for e in self.enemies if e.alive or e.death_timer > 0]
            if self.player.is_dead:
                self.state = STATE_GAMEOVER
                self.gameover_timer = 0

        self.messages = [
            {**m, "timer": m["timer"] - 1} for m in self.messages if m["timer"] > 0
        ]

    # ──────────────────────────────────────────────────────
    #  バトル・補充・メッセージ
    # ──────────────────────────────────────────────────────
    def _start_battle(self, enemy: Enemy):
        self.battle_enemy = enemy
        self.battle = Battle(
            player=self.player,
            enemy=enemy,
            font_lg=self.font_lg,
            font_md=self.font_md,
            font_sm=self.font_sm,
            sprite_mgr=self.sprite_mgr,
        )
        self.state = STATE_BATTLE
        self._add_message(f"{enemy.name} が現れた！", C_GOLD)

    def _transition_zone(self, next_zone_id: str):
        """
        ★ 0.6: ゾーンを切り替える。
        新しい World を生成し、プレイヤーをスポーン位置に移動する。
        has_enemies=True のゾーンだけ敵をスポーンする。
        """
        self.current_zone_id = next_zone_id
        self.world = World(next_zone_id)
        self.current_zone_name = self.world.zone_name
        self.enemies = []
        self.npcs = []  # ★ 0.7: NPC をリセット
        self.battle = None
        self.battle_enemy = None

        # プレイヤーを新ゾーンのスポーン位置に移動
        px, py = self.world.player_spawn
        self.player.rect.x = px
        self.player.rect.y = py

        # 敵をスポーン（has_enemies=False の町では何もしない）
        if self.world.has_enemies:
            spawn_positions = self.world.get_enemy_spawns(6)
            for i, (ex, ey) in enumerate(spawn_positions):
                self.enemies.append(
                    Enemy(ex, ey, variant_index=i % len(SLIME_VARIANTS))
                )

        # ★ 0.7: NPC をスポーン（town: 謎の老人、field: なし）
        for nx, ny in self.world.get_npc_spawns():
            self.npcs.append(
                NPC(
                    nx,
                    ny,
                    name="謎の老人",
                    dialogue_id="elder_first",
                    repeat_dialogue_id="elder_repeat",
                )
            )

        zone_name = self.world.zone_name
        self._add_message(f"ここは {zone_name}", C_GOLD)

        if next_zone_id == "shrine_inner" and not self._get_story_flag(
            "shrine_inner_entered", False
        ):
            self._start_shrine_inner_arrival_event()

    def _handle_exit_transition(self, exit_rect: pygame.Rect) -> None:
        if self.current_zone_id == "town":
            if self._is_town_north_exit(exit_rect):
                if self._get_story_flag("quest_go_north_reached", False):
                    self._transition_zone("north_road")
                else:
                    self._add_message("まだ北へ進む理由がないようだ", C_GRAY)
                    self.player.rect.top = exit_rect.bottom + 2
                return

            self._transition_zone("field")
            return

        exits = get_zone_exits(self.current_zone_id)
        if exits:
            self._transition_zone(exits[0]["to"])

    def _is_town_north_exit(self, exit_rect: pygame.Rect) -> bool:
        return exit_rect.centery <= TILE * 4

    # ──────────────────────────────────────────────────────
    #  ★ 0.7 Step5-B: 会話処理
    # ──────────────────────────────────────────────────────
    def _mark_story_event_seen(self, event_id: str):
        if self.player and hasattr(self.player, "mark_event_seen"):
            self.player.mark_event_seen(event_id)

    def _mark_story_event_completed(self, event_id: str):
        if self.player and hasattr(self.player, "mark_event_completed"):
            self.player.mark_event_completed(event_id)

    def _set_story_flag(self, flag_name: str, value: bool = True):
        if self.player and hasattr(self.player, "set_story_flag"):
            self.player.set_story_flag(flag_name, value)

    def _get_story_flag(self, flag_name: str, default: bool = False) -> bool:
        if self.player and hasattr(self.player, "get_story_flag"):
            return self.player.get_story_flag(flag_name, default)
        return default

    def _get_battle_win_count(self) -> int:
        if not self.player:
            return 0
        action_log = getattr(self.player, "action_log", None)
        if action_log and hasattr(action_log, "get_summary"):
            summary = action_log.get_summary()
            return int(summary.get("battle_win_count", 0))
        return 0

    def get_current_objective_text(self) -> str:
        if self._get_story_flag("next_fragment_hint_received", False):
            return "目的：風の吹く場所を探す"
        if self._get_story_flag("shrine_altar_investigated", False):
            return "目的：老人に祭壇のことを報告する"
        if self._get_story_flag("shrine_inner_entered", False) and not self._get_story_flag(
            "shrine_altar_investigated", False
        ):
            return "目的：祠の祭壇を調べる"
        if self._get_story_flag("shrine_seal_reacted", False):
            return "目的：祠の奥へ進む"
        if self._get_story_flag("shrine_fragment_1_obtained", False):
            return "目的：古い祠へ戻る"
        if self._get_story_flag("shrine_hint_received", False):
            return "目的：封印の欠片を探す"
        if self._get_story_flag("shrine_anomaly_seen", False):
            return "目的：老人に祠のことを尋ねる"
        if self._get_story_flag("quest_go_north_reached", False):
            return "目的：北の異変を調べる"
        if self._get_story_flag("quest_go_north", False):
            return "目的：村の北へ向かう"
        if self._get_story_flag("quest_check_field_reported", False):
            return ""
        if self._get_story_flag("quest_check_field_done", False):
            return "目的：老人に報告する"
        if self._get_story_flag("quest_check_field", False):
            return "目的：村の外を確認する"
        return ""

    def _resolve_npc_dialogue_id(self, npc: "NPC") -> str:
        """NPC and player stateから、今回表示する会話IDを決める。"""
        base_dialogue_id = npc.get_current_dialogue_id()
        if npc.dialogue_id != "elder_first" or not self.player:
            return base_dialogue_id

        if self._get_story_flag("next_fragment_hint_received", False):
            return "elder_after_next_fragment_hint"

        if self._get_story_flag("shrine_altar_investigated", False):
            return "elder_after_altar_investigation"

        if self._get_story_flag("shrine_hint_received", False):
            return "elder_after_shrine_hint"

        if self._get_story_flag("shrine_anomaly_seen", False):
            return "elder_after_shrine_anomaly"

        if self._get_story_flag("quest_go_north_reached", False):
            return "elder_after_go_north_reached"

        if self._get_story_flag("quest_check_field_reported", False):
            return "elder_after_report"

        if self._get_story_flag("quest_check_field_done", False):
            return "elder_after_quest_done"

        battle_win_count = self._get_battle_win_count()
        if battle_win_count >= 1:
            self._set_story_flag("quest_check_field_done", True)
            return "elder_after_battle"

        if self._get_story_flag("sage_booted", False):
            if not self._get_story_flag("quest_check_field", False):
                self._set_story_flag("quest_check_field", True)
            return "elder_after_sage"

        return base_dialogue_id

    def _update_story_progress_by_position(self) -> None:
        if not self.player:
            return

        if self.current_zone_id == "north_road":
            self._update_north_road_shrine_progress()
            return

        if self.current_zone_id != "town":
            return

        self._update_town_north_progress()

    def _update_town_north_progress(self) -> None:
        if not self._get_story_flag("quest_go_north", False):
            return
        if self._get_story_flag("quest_go_north_reached", False):
            return

        north_threshold_y = TILE * 5
        if self.player.rect.centery <= north_threshold_y:
            self._set_story_flag("quest_go_north_reached", True)

    def _update_north_road_shrine_progress(self) -> None:
        if not self.world or not self.player:
            return

        for shrine_rect in getattr(self.world, "shrine_rects", []):
            if not self.player.rect.colliderect(shrine_rect):
                continue

            if self._get_story_flag("shrine_seal_reacted", False):
                self._transition_zone("shrine_inner")
                return

            self._update_shrine_anomaly_progress()
            return

    def _update_shrine_anomaly_progress(self) -> None:
        if not self.world or not self.player:
            return
        if not self._get_story_flag("quest_go_north_reached", False):
            return
        if self._get_story_flag("shrine_anomaly_seen", False):
            return

        for shrine_rect in getattr(self.world, "shrine_rects", []):
            if self.player.rect.colliderect(shrine_rect):
                self._start_shrine_anomaly_event()
                return

    def _start_shrine_anomaly_event(self) -> None:
        self._set_story_flag("shrine_anomaly_seen", True)
        self.current_dialogue_id = "shrine_anomaly"
        self.dialogue_lines = get_dialogue_lines("shrine_anomaly")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_anomaly")
        self.state = STATE_DIALOGUE

    def _is_shrine_fragment_available(self) -> bool:
        return (
            self.current_zone_id == "field"
            and self._get_story_flag("shrine_hint_received", False)
            and not self._get_story_flag("shrine_fragment_1_obtained", False)
        )

    def _try_collect_shrine_fragment(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._is_shrine_fragment_available():
            return False

        for fragment_rect in getattr(self.world, "fragment_rects", []):
            if self.player.rect.colliderect(fragment_rect.inflate(TILE, TILE)):
                self._start_shrine_fragment_1_event()
                return True

        return False

    def _start_shrine_fragment_1_event(self) -> None:
        self._set_story_flag("shrine_fragment_1_seen", True)
        self._set_story_flag("shrine_fragment_1_obtained", True)
        self.current_dialogue_id = "shrine_fragment_1_found"
        self.dialogue_lines = get_dialogue_lines("shrine_fragment_1_found")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_fragment_1_found")
        self.state = STATE_DIALOGUE

    def _try_offer_shrine_fragment(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "north_road":
            return False
        if not self._get_story_flag("shrine_fragment_1_obtained", False):
            return False

        for shrine_rect in getattr(self.world, "shrine_rects", []):
            if self.player.rect.colliderect(shrine_rect.inflate(TILE, TILE)):
                if self._get_story_flag("shrine_fragment_1_offered", False):
                    self._add_message("封印はわずかに開いている", C_GRAY)
                else:
                    self._start_shrine_fragment_1_offered_event()
                return True

        return False

    def _start_shrine_fragment_1_offered_event(self) -> None:
        self._set_story_flag("shrine_fragment_1_offered", True)
        self._set_story_flag("shrine_seal_reacted", True)
        self.current_dialogue_id = "shrine_fragment_1_offered"
        self.dialogue_lines = get_dialogue_lines("shrine_fragment_1_offered")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_fragment_1_offered")
        self.state = STATE_DIALOGUE

    def _start_shrine_inner_arrival_event(self) -> None:
        self._set_story_flag("shrine_inner_entered", True)
        self.current_dialogue_id = "shrine_inner_arrival"
        self.dialogue_lines = get_dialogue_lines("shrine_inner_arrival")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_inner_arrival")
        self.state = STATE_DIALOGUE

    def _try_investigate_shrine_altar(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "shrine_inner":
            return False
        if not self._get_story_flag("shrine_inner_entered", False):
            return False

        for altar_rect in getattr(self.world, "altar_rects", []):
            if self.player.rect.colliderect(altar_rect.inflate(TILE, TILE)):
                if self._get_story_flag("shrine_altar_investigated", False):
                    self._add_message("祭壇の光は静かに揺れている", C_GRAY)
                else:
                    self._start_shrine_altar_investigation_event()
                return True

        return False

    def _start_shrine_altar_investigation_event(self) -> None:
        self._set_story_flag("shrine_altar_investigated", True)
        self._set_story_flag("shrine_altar_resonance_seen", True)
        self.current_dialogue_id = "shrine_altar_investigation"
        self.dialogue_lines = get_dialogue_lines("shrine_altar_investigation")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_altar_investigation")
        self.state = STATE_DIALOGUE

    def _start_dialogue(self, npc: "NPC"):
        """
        NPC との会話を開始する。
        NPC が初回未会話なら dialogue_id、
        2回目以降なら repeat_dialogue_id の会話を使う。
        """
        # NPCとplayer状態を見て今回の会話IDを選択
        d_id = self._resolve_npc_dialogue_id(npc)

        self.current_dialogue_id = d_id
        self.dialogue_lines = get_dialogue_lines(d_id)
        self.dialogue_speaker = get_dialogue_speaker(d_id)
        self.dialogue_index = 0
        self.talking_npc = npc
        self._mark_story_event_seen(d_id)
        self.state = STATE_DIALOGUE

    def _start_prologue(self):
        """ゲーム開始直後にプロローグメッセージを表示する。"""
        self.current_dialogue_id = "prologue_intro"
        self.dialogue_lines = get_dialogue_lines("prologue_intro")
        self.dialogue_speaker = get_dialogue_speaker("prologue_intro")
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("prologue_intro")
        self.state = STATE_PROLOGUE

    def _advance_dialogue(self):
        """
        会話を次のページへ進める。
        最後のページに達したら会話を終了する。
        """
        self.dialogue_index += 1
        if self.dialogue_index >= len(self.dialogue_lines):
            self._end_dialogue()

    def _end_dialogue(self):
        """
        会話を終了して探索マップへ戻る。
        on_end イベント処理はここで行う。
        """

        finished_dialogue_id = self.current_dialogue_id

        # on_end の取得
        on_end = get_dialogue_on_end(self.current_dialogue_id)

        # Step5-C: on_end == "sage_activate" → 《観測補助機構》起動イベントを連続表示
        if on_end == "sage_activate":
            self._mark_story_event_completed(finished_dialogue_id)
            if finished_dialogue_id == "elder_first":
                self._mark_story_event_completed("first_elder_talk")
                self._set_story_flag("met_elder", True)
                self._set_story_flag("quest_check_field", True)
            if self.talking_npc:
                self.talking_npc.mark_talked()  # 初回会話フラグを立てる
            self.talking_npc = None
            self.current_dialogue_id = "sage_boot"
            self.dialogue_lines = get_dialogue_lines("sage_boot")
            self.dialogue_speaker = self.get_support_system_display_name()
            self.dialogue_index = 0
            self._mark_story_event_seen("sage_boot")
            return

        if self.talking_npc:
            self.talking_npc.mark_talked()  # 初回会話フラグを立てる

        self._mark_story_event_completed(finished_dialogue_id)
        if finished_dialogue_id == "elder_first":
            self._mark_story_event_completed("first_elder_talk")
            self._set_story_flag("met_elder", True)
            self._set_story_flag("quest_check_field", True)
        if finished_dialogue_id == "elder_after_quest_done":
            self._set_story_flag("quest_check_field_reported", True)
            self._set_story_flag("quest_go_north", True)
        if finished_dialogue_id == "elder_after_shrine_anomaly":
            self._set_story_flag("shrine_hint_received", True)
        if finished_dialogue_id == "elder_after_altar_investigation":
            self._set_story_flag("shrine_altar_reported", True)
            self._set_story_flag("next_fragment_hint_received", True)
        if finished_dialogue_id == "sage_boot" and self.player and hasattr(
            self.player, "set_story_flag"
        ):
            self.player.set_story_flag("sage_booted", True)
            self.support_name_input = ""
            self.current_dialogue_id = ""
            self.dialogue_lines = []
            self.dialogue_speaker = ""
            self.dialogue_index = 0
            self.talking_npc = None
            self.state = STATE_SUPPORT_NAME_INPUT
            return

        # その他は通常通り探索に戻す
        self.current_dialogue_id = ""
        self.dialogue_lines = []
        self.dialogue_speaker = ""
        self.dialogue_index = 0
        self.talking_npc = None
        self.state = STATE_PLAY

    def _respawn_enemies(self):
        if not self.world:
            return
        # ★ 0.6: has_enemies=False のゾーンでは補充しない
        if not self.world.has_enemies:
            return
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
            self._draw_play(surface)
            self._draw_job_menu(surface)
        elif self.state == STATE_SAVE_MENU:
            self._draw_play(surface)
            self._draw_save_menu(surface)
        elif self.state == STATE_DIALOGUE:
            # ★ 0.7 Step5-B: マップの上に会話ウィンドウを重ねる
            self._draw_play(surface)
            self._draw_dialogue_window(surface)
        elif self.state == STATE_PROLOGUE:
            self._draw_play(surface)
            self._draw_dialogue_window(surface)
        elif self.state == STATE_SUPPORT_NAME_INPUT:
            self._draw_play(surface)
            self._draw_support_name_input(surface)
        elif self.state in (STATE_PLAY, STATE_LEVELUP):
            self._draw_play(surface)
        elif self.state == STATE_GAMEOVER:
            self._draw_play(surface)
            self._draw_gameover(surface)

    # ── ★ 0.7 Step5-B: 会話ウィンドウ描画 ───────────────────
    def _draw_dialogue_window(self, surface: pygame.Surface):
        """
        会話ウィンドウを画面下部に描画する。
        ├─ 話者名（上帯）
        └─ セリフ本文（下エリア）
        ページ送りヒントを右下に表示する。
        """
        if not self.dialogue_lines:
            return

        # ── ウィンドウのサイズ・位置
        WIN_W = WINDOW_W - 40  # 左右20pxずつ余白
        WIN_H = 140  # 会話ウィンドウの高さ
        WIN_X = 20
        WIN_Y = GAME_AREA_H - WIN_H - 10  # ゲームエリア下端の少し上

        # ── 背景・枠線
        pygame.draw.rect(
            surface, C_DIALOGUE_BG, (WIN_X, WIN_Y, WIN_W, WIN_H), border_radius=6
        )
        pygame.draw.rect(
            surface, C_DIALOGUE_BORDER, (WIN_X, WIN_Y, WIN_W, WIN_H), 2, border_radius=6
        )

        # ── 話者名帯
        NAME_H = 26
        pygame.draw.rect(
            surface, C_DIALOGUE_BORDER, (WIN_X, WIN_Y, WIN_W, NAME_H), border_radius=6
        )
        name_txt = self.font_md.render(self.dialogue_speaker, True, C_DIALOGUE_NAME)
        surface.blit(name_txt, (WIN_X + 14, WIN_Y + 4))

        # ── セリフ本文（現在のページを折り返して表示）
        current_line = (
            self.dialogue_lines[self.dialogue_index]
            if self.dialogue_index < len(self.dialogue_lines)
            else ""
        )
        TEXT_MAX_W = WIN_W - 28
        wrapped = self._wrap_dialogue(current_line, self.font_md, TEXT_MAX_W)
        for i, row in enumerate(wrapped[:3]):  # 最大3行表示
            txt = self.font_md.render(row, True, C_DIALOGUE_TEXT)
            surface.blit(txt, (WIN_X + 14, WIN_Y + NAME_H + 12 + i * 26))

        # ── ページ送りヒント
        total = len(self.dialogue_lines)
        idx = self.dialogue_index + 1
        is_last = idx >= total
        hint_str = (
            "[ Z / Enter：閉じる ]"
            if is_last
            else f"[ Z / Enter：次へ  {idx}/{total} ]"
        )
        hint_txt = self.font_sm.render(hint_str, True, C_DIALOGUE_BORDER)
        surface.blit(
            hint_txt, (WIN_X + WIN_W - hint_txt.get_width() - 12, WIN_Y + WIN_H - 20)
        )

    def _wrap_dialogue(
        self, text: str, font: "pygame.font.Font", max_width: int
    ) -> list[str]:
        """
        会話テキストを max_width に収まるよう1文字ずつ折り返す。
        battle.py の _wrap_text と同じロジックで統一。
        """
        lines: list[str] = []
        current = ""
        for char in text:
            test = current + char
            w, _ = font.size(test)
            if w <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines if lines else [""]

    # ── タイトル画面 ──────────────────────────────────────
    def _draw_support_name_input(self, surface: pygame.Surface):
        overlay = pygame.Surface((WINDOW_W, GAME_AREA_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        box_w, box_h = 620, 210
        box_x = WINDOW_W // 2 - box_w // 2
        box_y = GAME_AREA_H // 2 - box_h // 2
        pygame.draw.rect(
            surface, C_WINDOW_BG, (box_x, box_y, box_w, box_h), border_radius=6
        )
        pygame.draw.rect(
            surface, C_WINDOW_BORDER, (box_x, box_y, box_w, box_h), 2, border_radius=6
        )

        title = self.font_md.render(
            "この観測補助機構に名前を付けてください", True, C_GOLD
        )
        name = self.support_name_input
        if (self.title_timer // 30) % 2 == 0:
            name += "_"
        name_text = self.font_md.render(f"名前：{name}", True, C_WHITE)
        enter_hint = self.font_sm.render("Enter/Z：決定", True, C_GRAY)
        backspace_hint = self.font_sm.render("Backspace：削除", True, C_GRAY)
        cancel_hint = self.font_sm.render(
            "Esc：観測補助機構として決定", True, C_DARK_GRAY
        )

        surface.blit(title, (WINDOW_W // 2 - title.get_width() // 2, box_y + 34))
        surface.blit(name_text, (box_x + 70, box_y + 86))
        surface.blit(enter_hint, (box_x + 70, box_y + 138))
        surface.blit(backspace_hint, (box_x + 250, box_y + 138))
        surface.blit(cancel_hint, (box_x + 70, box_y + 166))

    def _draw_title(self, surface: pygame.Surface):
        surface.fill(C_DARK_BG)
        pygame.draw.line(surface, C_GOLD, (40, 80), (WINDOW_W - 40, 80), 1)
        pygame.draw.line(
            surface, C_GOLD, (40, WINDOW_H - 80), (WINDOW_W - 40, WINDOW_H - 80), 1
        )

        t1 = self.font_lg.render("SINGULARITY", True, C_WHITE)
        t2 = self.font_md.render("- Chronicle of Origin -", True, C_GOLD)
        t3 = self.font_sm.render("Prototype  1.0", True, C_GRAY)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, 110))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, 158))
        surface.blit(t3, (WINDOW_W // 2 - t3.get_width() // 2, 192))

        img = self.sprite_mgr.get_player("novice_m", size=(64, 64))
        if img:
            surface.blit(img, (WINDOW_W // 2 - 32, 222))
        else:
            pygame.draw.circle(surface, C_WHITE, (WINDOW_W // 2, 250), 18)
            pygame.draw.rect(
                surface,
                C_WHITE,
                pygame.Rect(WINDOW_W // 2 - 10, 267, 20, 30),
                border_radius=4,
            )

        desc = self.font_sm.render("主人公：ノービス", True, C_GRAY)
        surface.blit(desc, (WINDOW_W // 2 - desc.get_width() // 2, 298))

        labels = {
            "new_game": "NEW GAME",
            "load_game": "LOAD GAME",
            "quit": "QUIT",
        }
        menu_y = 350
        for i, option in enumerate(self.title_menu_options):
            selected = i == self.title_menu_cursor
            color = C_GOLD if selected else C_GRAY
            cursor = "> " if selected else "  "
            text = self.font_md.render(f"{cursor}{labels[option]}", True, color)
            surface.blit(text, (WINDOW_W // 2 - text.get_width() // 2, menu_y + i * 36))

        guide_lines = [
            "Up / Down : Select",
            "Z / Enter / Space : Confirm",
            "L : Load Game",
        ]
        for i, line in enumerate(guide_lines):
            txt = self.font_sm.render(line, True, C_GRAY)
            surface.blit(txt, (WINDOW_W // 2 - txt.get_width() // 2, 474 + i * 20))

    # ── 探索マップ ────────────────────────────────────────
    def _draw_play(self, surface: pygame.Surface):
        if not self.world or not self.player:
            return
        self.world.draw(
            surface,
            shrine_seal_reacted=self._get_story_flag("shrine_seal_reacted", False),
        )
        self._draw_shrine_fragment(surface)
        for enemy in self.enemies:
            enemy.draw(surface, self.font_sm, self.sprite_mgr)
        # ★ 0.7: NPC を描画（プレイヤーが近いと「！」が出る）
        for npc in self.npcs:
            npc.draw(surface, self.font_sm, self.font_md, self.player.rect)
        self.player.draw(surface, self.sprite_mgr)
        if self.state == STATE_LEVELUP:
            self._draw_levelup_overlay(surface)
        if self.state == STATE_PLAY:
            self._draw_current_objective(surface)
        self._draw_hud(surface)

    def _draw_shrine_fragment(self, surface: pygame.Surface):
        if not self.world or not self._is_shrine_fragment_available():
            return

        pulse = (self.title_timer // 10) % 2
        for rect in getattr(self.world, "fragment_rects", []):
            glow = rect.inflate(12 + pulse * 4, 12 + pulse * 4)
            pygame.draw.ellipse(surface, make_rgba(160, 220, 255, 70), glow)
            pygame.draw.polygon(
                surface,
                (185, 235, 255),
                [
                    rect.midtop,
                    (rect.right - 7, rect.centery),
                    rect.midbottom,
                    (rect.left + 7, rect.centery),
                ],
            )
            pygame.draw.polygon(
                surface,
                C_WHITE,
                [
                    rect.midtop,
                    (rect.right - 7, rect.centery),
                    rect.midbottom,
                    (rect.left + 7, rect.centery),
                ],
                1,
            )

    def _draw_current_objective(self, surface: pygame.Surface):
        objective = self.get_current_objective_text()
        if not objective:
            return

        txt = self.font_sm.render(objective, True, C_WHITE)
        pad_x, pad_y = 10, 6
        box_w = txt.get_width() + pad_x * 2
        box_h = txt.get_height() + pad_y * 2
        box_x = WINDOW_W - box_w - 12
        box_y = 12

        box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box.fill(make_rgba(8, 6, 14, 190))
        surface.blit(box, (box_x, box_y))
        pygame.draw.rect(
            surface,
            C_WINDOW_BORDER,
            pygame.Rect(box_x, box_y, box_w, box_h),
            1,
            border_radius=4,
        )
        surface.blit(txt, (box_x + pad_x, box_y + pad_y))

    def _draw_levelup_overlay(self, surface: pygame.Surface):
        overlay = pygame.Surface((WINDOW_W, GAME_AREA_H), pygame.SRCALPHA)
        overlay.fill(make_rgba(0, 0, 0, 110))
        surface.blit(overlay, (0, 0))
        job = self.player.current_job
        t1 = self.font_lg.render("LEVEL UP !", True, C_GOLD)
        t2 = self.font_md.render(
            f"Lv {self.player.level}  "
            f"HP+{job['lv_up_hp']}  ATK+{job['lv_up_atk']}  DEF+{job['lv_up_def']}",
            True,
            C_WHITE,
        )
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, GAME_AREA_H // 2 - 40))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, GAME_AREA_H // 2 + 12))

    # ── HUD（★ 0.4: ジョブ表示を追加） ──────────────────
    def _draw_hud(self, surface: pygame.Surface):
        p = self.player
        pygame.draw.rect(
            surface, (10, 8, 18), pygame.Rect(0, GAME_AREA_H, WINDOW_W, HUD_H)
        )
        pygame.draw.line(surface, C_GOLD, (0, GAME_AREA_H), (WINDOW_W, GAME_AREA_H), 1)

        bar_x, bar_y, bar_w = 12, GAME_AREA_H + 10, 180

        # HP バー
        hp_label = self.font_sm.render(f"HP  {p.hp} / {p.max_hp}", True, C_WHITE)
        surface.blit(hp_label, (bar_x, bar_y))
        ratio = max(0.0, p.hp / p.max_hp)
        hp_color = C_CRIMSON_LT if ratio > 0.3 else (255, 50, 50)
        pygame.draw.rect(
            surface, (50, 15, 15), (bar_x, bar_y + 18, bar_w, 10), border_radius=3
        )
        pygame.draw.rect(
            surface,
            hp_color,
            (bar_x, bar_y + 18, int(bar_w * ratio), 10),
            border_radius=3,
        )

        # EXP バー
        exp_label = self.font_sm.render(
            f"EXP {p.exp}  ( next: {p.exp_to_next()} )", True, C_GOLD
        )
        surface.blit(exp_label, (bar_x, bar_y + 34))
        pygame.draw.rect(
            surface, (20, 40, 20), (bar_x, bar_y + 52, bar_w, 6), border_radius=3
        )
        pygame.draw.rect(
            surface,
            C_GREEN_DIM,
            (bar_x, bar_y + 52, int(bar_w * p.exp_progress()), 6),
            border_radius=3,
        )

        # レベル・ステータス
        lv_txt = self.font_md.render(f"Lv {p.level}", True, C_GOLD)
        surface.blit(lv_txt, (210, GAME_AREA_H + 10))
        stats_txt = self.font_sm.render(f"ATK {p.atk}   DEF {p.defense}", True, C_GRAY)
        surface.blit(stats_txt, (210, GAME_AREA_H + 34))

        # ★ 0.4: ジョブ名をジョブカラーで表示（レベルの右隣）
        job_txt = self.font_sm.render(f"[ {p.job_name} ]", True, p.job_color)
        surface.blit(job_txt, (210, GAME_AREA_H + 56))

        # ★ 0.5 Step9: 属性名を属性カラーで表示（ジョブ名の直下）
        elem_name = get_element_name(p.element)  # 例: "火" / "無"
        elem_color = get_element_color(p.element)  # 属性ごとのRGBカラー
        elem_txt = self.font_sm.render(f"属性：{elem_name}", True, elem_color)
        surface.blit(elem_txt, (210, GAME_AREA_H + 72))

        # ヒント（右端）: ★ 0.6 マップ名を追加
        zone_name = self.world.zone_name if self.world else ""
        hint_text = f"[ {zone_name} ]"
        if constants.DEBUG_MODE:
            hint_text += "  J：ジョブチェンジ"
        hint_text += "  Esc：セーブ"
        hint = self.font_sm.render(hint_text, True, C_DARK_GRAY)
        surface.blit(hint, (WINDOW_W - hint.get_width() - 10, GAME_AREA_H + 10))

        # メッセージログ（最新3件）
        msg_x = WINDOW_W - 10
        for i, msg in enumerate(self.messages[:3]):
            alpha = safe_alpha(min(255, msg["timer"] * 2))
            txt = self.font_sm.render(msg["text"], True, msg["color"])
            txt.set_alpha(alpha)
            surface.blit(txt, (msg_x - txt.get_width(), GAME_AREA_H + 30 + i * 18))

        # ── デバッグオーバーレイ（DEBUG_MODE が True のときのみ）
        if constants.DEBUG_MODE and getattr(self, "show_debug_overlay", False):
            try:
                al = p.action_log.get_summary()
            except Exception:
                al = {}
            lines = []
            lines.append("ACTION LOG")
            lines.append(f"Normal Attack: {al.get('normal_attack_count', 0)}")
            lines.append(f"Skill Use: {al.get('skill_use_count', 0)}")
            lines.append(f"Observe: {al.get('observe_count', 0)}")
            lines.append(f"Magic Skill: {al.get('magic_skill_count', 0)}")
            lines.append(f"Physical Skill: {al.get('physical_skill_count', 0)}")
            lines.append(f"Escape: {al.get('escape_count', 0)}")
            lines.append(f"Win: {al.get('battle_win_count', 0)}")
            lines.append(f"Lose: {al.get('battle_lose_count', 0)}")
            lines.append(f"Job Changes: {al.get('job_change_count', 0)}")
            lines.append("")
            lines.append(f"Current Job: {p.current_job_id}")
            lines.append("Unlocked: " + ", ".join(p.unlocked_jobs))

            box_w = 220
            box_h = 18 * len(lines) + 12
            bx = WINDOW_W - box_w - 8
            by = 8
            overlay = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            overlay.fill(make_rgba(6, 6, 8, 200))
            surface.blit(overlay, (bx, by))
            for i, line in enumerate(lines):
                col = C_GOLD if i == 0 else C_WHITE
                txt = self.font_sm.render(line, True, col)
                surface.blit(txt, (bx + 8, by + 6 + i * 18))

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
        wx = WINDOW_W // 2 - WIN_W // 2
        wy = GAME_AREA_H // 2 - WIN_H // 2
        pygame.draw.rect(surface, C_WINDOW_BG, (wx, wy, WIN_W, WIN_H), border_radius=6)
        pygame.draw.rect(
            surface, C_WINDOW_BORDER, (wx, wy, WIN_W, WIN_H), 2, border_radius=6
        )
        pygame.draw.line(
            surface, C_GOLD, (wx + 1, wy + 42), (wx + WIN_W - 1, wy + 42), 1
        )

        # タイトル
        title = self.font_md.render("ジョブチェンジ", True, C_GOLD)
        surface.blit(title, (wx + WIN_W // 2 - title.get_width() // 2, wy + 12))

        p = self.player
        # 現在のジョブ表示
        cur_txt = self.font_sm.render(
            f"現在：{p.job_name}  Lv {p.level}  ATK {p.atk}  DEF {p.defense}",
            True,
            p.job_color,
        )
        surface.blit(cur_txt, (wx + 16, wy + 52))

        # ── 選択肢リスト
        opt_y = wy + 88
        for i, job_id in enumerate(self.job_menu_options):
            job = get_job(job_id)
            is_sel = i == self.job_menu_cursor
            jcolor = job["color"]

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
            name_line = self.font_md.render(f"{job['name']}  {tier_mark}", True, jcolor)
            surface.blit(name_line, (wx + 38, opt_y + i * 66))

            # ステータスプレビュー（ボーナス差分を表示）
            hp_d = job.get("hp_bonus", 0) - p.current_job.get("hp_bonus", 0)
            atk_d = job.get("atk_bonus", 0) - p.current_job.get("atk_bonus", 0)
            def_d = job.get("def_bonus", 0) - p.current_job.get("def_bonus", 0)

            def _sign(v):
                return f"+{v}" if v >= 0 else str(v)

            preview = self.font_sm.render(
                f"HP {_sign(hp_d)}  ATK {_sign(atk_d)}  DEF {_sign(def_d)}  "
                f"| {job['desc'][:16]}…",
                True,
                C_GRAY,
            )
            surface.blit(preview, (wx + 38, opt_y + i * 66 + 26))

        # 操作ヒント
        hint = self.font_sm.render(
            "↑↓ 選択   Z/Enter 決定   Esc/X キャンセル", True, C_DARK_GRAY
        )
        surface.blit(hint, (wx + WIN_W // 2 - hint.get_width() // 2, wy + WIN_H - 26))

    def _draw_save_menu(self, surface: pygame.Surface):
        """探索マップの上にセーブ/ロードメニューを表示する。"""
        overlay = pygame.Surface((WINDOW_W, GAME_AREA_H), pygame.SRCALPHA)
        overlay.fill(make_rgba(0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        WIN_W, WIN_H = 460, 300
        wx = WINDOW_W // 2 - WIN_W // 2
        wy = GAME_AREA_H // 2 - WIN_H // 2
        pygame.draw.rect(surface, C_WINDOW_BG, (wx, wy, WIN_W, WIN_H), border_radius=6)
        pygame.draw.rect(
            surface, C_WINDOW_BORDER, (wx, wy, WIN_W, WIN_H), 2, border_radius=6
        )
        pygame.draw.line(
            surface, C_GOLD, (wx + 1, wy + 42), (wx + WIN_W - 1, wy + 42), 1
        )

        title = self.font_md.render("SAVE / LOAD", True, C_GOLD)
        surface.blit(title, (wx + WIN_W // 2 - title.get_width() // 2, wy + 12))

        summary_y = wy + 58
        for i, (line, color) in enumerate(self._get_save_summary_lines()):
            txt = self.font_sm.render(line, True, color)
            surface.blit(txt, (wx + 24, summary_y + i * 22))

        label_map = {
            "save": "Save",
            "load": "Load",
            "cancel": "Cancel",
        }
        opt_y = wy + 146
        for i, option in enumerate(self.save_menu_options):
            is_sel = i == self.save_menu_cursor
            row = pygame.Rect(wx + 18, opt_y + i * 36 - 5, WIN_W - 36, 32)
            if is_sel:
                pygame.draw.rect(surface, (35, 28, 55), row, border_radius=4)
                pygame.draw.rect(surface, C_GOLD, row, 1, border_radius=4)
                cursor = self.font_md.render(">", True, C_GOLD)
                surface.blit(cursor, (wx + 34, opt_y + i * 36 - 2))

            color = C_GOLD if is_sel else C_WHITE
            text = self.font_md.render(label_map.get(option, option), True, color)
            surface.blit(text, (wx + 62, opt_y + i * 36 - 1))

        hint = self.font_sm.render(
            "↑↓ 選択   Z/Enter 決定   Esc/X キャンセル", True, C_DARK_GRAY
        )
        surface.blit(hint, (wx + WIN_W // 2 - hint.get_width() // 2, wy + WIN_H - 26))

    # ── ゲームオーバー ────────────────────────────────────
    def _draw_gameover(self, surface: pygame.Surface):
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        alpha = safe_alpha(min(180, self.gameover_timer * 3))
        overlay.fill(make_rgba(0, 0, 0, alpha))
        surface.blit(overlay, (0, 0))
        if self.gameover_timer < 20:
            return
        t1 = self.font_lg.render("GAME  OVER", True, C_CRIMSON_LT)
        t2 = self.font_md.render(
            f"到達レベル：{self.player.level}  ジョブ：{self.player.job_name}  EXP：{self.player.exp}",
            True,
            C_WHITE,
        )
        t3 = self.font_sm.render("[ SPACE ] でタイトルへ戻る", True, C_GRAY)
        surface.blit(t1, (WINDOW_W // 2 - t1.get_width() // 2, WINDOW_H // 2 - 60))
        surface.blit(t2, (WINDOW_W // 2 - t2.get_width() // 2, WINDOW_H // 2 + 10))
        surface.blit(t3, (WINDOW_W // 2 - t3.get_width() // 2, WINDOW_H // 2 + 50))
