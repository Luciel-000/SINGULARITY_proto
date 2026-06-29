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
STATE_PALE_CHOICE = "pale_choice"


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
        self.pale_choice_options: list[tuple[str, str]] = []
        self.pale_choice_cursor: int = 0
        self.pale_choice_prompt_lines: list[str] = []
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

        if self.state == STATE_PALE_CHOICE:
            self._handle_pale_choice_key(key)
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
                if self._try_collect_earth_support_stone():
                    return
                if self._try_investigate_earth_trial_echo():
                    return
                if self._try_investigate_earth_support_trace():
                    return
                if self._try_investigate_earth_seal():
                    return
                if self._try_investigate_stonefield_echo():
                    return
                if self._try_start_stonefield_presence_encounter():
                    return
                if self._try_investigate_stonefield_seal_mark():
                    return
                if self._try_investigate_stonefield_core():
                    return
                if self._try_investigate_stonefield_rock():
                    return
                if self._try_investigate_fire_fragment_light():
                    return
                if self._try_investigate_fire_trial_echo():
                    return
                if self._try_investigate_fire_memory():
                    return
                if self._try_investigate_ember_echo():
                    return
                if self._try_investigate_fire_seal():
                    return
                if self._try_start_ember_presence_encounter():
                    return
                if self._try_investigate_ember_seal_mark():
                    return
                if self._try_investigate_ember_core():
                    return
                if self._try_investigate_ember_heat_point():
                    return
                if self._try_investigate_pale_dual_trace():
                    return
                if self._try_investigate_pale_trial_echo():
                    return
                if self._try_investigate_pale_echo():
                    return
                if self._try_start_pale_presence_encounter():
                    return
                if self._try_investigate_pale_light_center():
                    return
                if self._try_investigate_pale_light():
                    return
                if self._try_investigate_boundary_dual_trace():
                    return
                if self._try_investigate_boundary_center():
                    return
                if self._try_investigate_boundary_resonance():
                    return
                if self._try_investigate_distant_resonance_trace():
                    return
                if self._try_collect_wind_fragment():
                    return
                if self._try_progress_sylph_trial():
                    return
                if self._try_start_sylph_encounter():
                    return
                if self._try_analyze_wind_flow():
                    return
                if self._try_investigate_wind_gorge_anomaly():
                    return
                if self._try_investigate_water_fragment_light():
                    return
                if self._try_investigate_water_seal():
                    return
                if self._try_collect_water_drop():
                    return
                if self._try_investigate_water_trial_echo():
                    return
                if self._try_investigate_water_memory_core():
                    return
                if self._try_reveal_undine_presence():
                    return
                if self._try_investigate_water_memory_trace():
                    return
                if self._try_investigate_water_presence_trace():
                    return
                if self._try_investigate_water_mirror_center():
                    return
                if self._try_investigate_water_reflection_shadow():
                    return
                if self._try_investigate_water_depths_light():
                    return
                if self._try_investigate_water_source():
                    return
                if self._try_investigate_water_mirror():
                    return
                if self._try_investigate_shrine_new_anomaly():
                    return
                if self._try_investigate_shrine_unknown_resonance():
                    return
                if self._try_offer_earth_fragment_to_altar():
                    return
                if self._try_offer_fire_fragment_to_altar():
                    return
                if self._try_offer_water_fragment_to_altar():
                    return
                if self._try_offer_wind_fragment_to_altar():
                    return
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

    def _handle_pale_choice_key(self, key: int) -> None:
        if not self.pale_choice_options:
            self.state = STATE_PLAY
            return

        if key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
            self.pale_choice_cursor = (
                self.pale_choice_cursor - 1
            ) % len(self.pale_choice_options)
            return

        if key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
            self.pale_choice_cursor = (
                self.pale_choice_cursor + 1
            ) % len(self.pale_choice_options)
            return

        if key in (pygame.K_ESCAPE, pygame.K_x):
            self._add_message("中心の光は、まだ答えを待っている。", C_GRAY)
            return

        if key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
            choice_id, _label = self.pale_choice_options[self.pale_choice_cursor]
            self._confirm_pale_center_choice(choice_id)

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

        if self.state == STATE_PALE_CHOICE:
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
            self._update_wind_gorge_transition()
            self._update_water_cave_transition()
            self._update_water_cave_depths_transition()
            self._update_water_cave_source_transition()
            self._update_water_cave_reflection_transition()
            self._update_water_cave_mirror_chamber_transition()
            self._update_ember_path_transition()
            self._update_stonefield_path_transition()
            self._update_pale_path_transition()

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
        if next_zone_id == "wind_gorge" and not self._get_story_flag(
            "wind_gorge_entered", False
        ):
            self._start_wind_gorge_arrival_event()
        if next_zone_id == "water_cave" and not self._get_story_flag(
            "water_cave_entered", False
        ):
            self._start_water_cave_arrival_event()
        if next_zone_id == "water_cave_depths" and not self._get_story_flag(
            "water_depths_entered", False
        ):
            self._start_water_cave_depths_arrival_event()
        if next_zone_id == "water_cave_source" and not self._get_story_flag(
            "water_source_entered", False
        ):
            self._start_water_cave_source_arrival_event()
        if next_zone_id == "water_cave_reflection" and not self._get_story_flag(
            "water_reflection_corridor_entered", False
        ):
            self._start_water_cave_reflection_arrival_event()
        if next_zone_id == "water_cave_mirror_chamber" and not self._get_story_flag(
            "water_mirror_chamber_entered", False
        ):
            self._start_water_cave_mirror_chamber_arrival_event()
        if next_zone_id == "ember_path" and not self._get_story_flag(
            "ember_path_entered", False
        ):
            self._start_ember_path_arrival_event()
        if next_zone_id == "ember_depths" and not self._get_story_flag(
            "ember_depths_entered", False
        ):
            self._start_ember_depths_arrival_event()
        if next_zone_id == "stonefield_path" and not self._get_story_flag(
            "stonefield_path_entered", False
        ):
            self._start_stonefield_path_arrival_event()
        if next_zone_id == "stonefield_depths" and not self._get_story_flag(
            "stonefield_depths_entered", False
        ):
            self._start_stonefield_depths_arrival_event()
        if next_zone_id == "pale_path" and not self._get_story_flag(
            "pale_path_entered", False
        ):
            self._start_pale_path_arrival_event()
        if next_zone_id == "pale_depths" and not self._get_story_flag(
            "pale_depths_entered", False
        ):
            self._start_pale_depths_arrival_event()
        if next_zone_id == "boundary_path" and not self._get_story_flag(
            "boundary_path_entered", False
        ):
            self._start_boundary_path_arrival_event()
        if next_zone_id == "boundary_depths" and not self._get_story_flag(
            "boundary_depths_entered", False
        ):
            self._start_boundary_depths_arrival_event()

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

        if self.current_zone_id == "shrine_inner":
            if self._is_shrine_inner_boundary_exit(exit_rect):
                if self._get_story_flag("shrine_unknown_resonance_stabilized", False):
                    self._transition_zone("boundary_path")
                else:
                    self._add_message(
                        "祭壇の中心は静かに揺れている。まだ、この先へ進むための均衡が整っていないようだ。",
                        C_GRAY,
                    )
                    self.player.rect.top = exit_rect.bottom + 2
                return

            self._transition_zone("north_road")
            return

        if self.current_zone_id == "ember_path":
            if self._is_ember_path_deeper_exit(exit_rect):
                if self._get_story_flag("ember_deeper_path_hint_received", False):
                    self._transition_zone("ember_depths")
                else:
                    self._add_message(
                        "道の奥から強い熱を感じる。だが、まだ進むべき流れを見つけられていない。",
                        C_GRAY,
                    )
                    self.player.rect.top = exit_rect.bottom + 2
                return

            self._transition_zone("field")
            return

        if self.current_zone_id == "stonefield_path":
            if self._is_stonefield_path_deeper_exit(exit_rect):
                if self._get_story_flag("stonefield_deeper_path_hint_received", False):
                    self._transition_zone("stonefield_depths")
                else:
                    self._add_message(
                        "岩盤の奥から重い響きが伝わる。だが、まだ進むべき流れを見つけられていない。",
                        C_GRAY,
                    )
                    self.player.rect.top = exit_rect.bottom + 2
                return

            self._transition_zone("field")
            return

        if self.current_zone_id == "pale_path":
            if self._is_pale_path_deeper_exit(exit_rect):
                if self._get_story_flag("pale_light_trace_hint_received", False):
                    self._transition_zone("pale_depths")
                else:
                    self._add_message(
                        "淡い光の痕跡は、まだ道の奥へ続いている。まずは、その反応を確かめる必要がある。",
                        C_GRAY,
                    )
                    self.player.rect.top = exit_rect.bottom + 2
                return

            self._transition_zone("field")
            return

        if self.current_zone_id == "boundary_path":
            if self._is_boundary_path_deeper_exit(exit_rect):
                if self._get_story_flag("boundary_center_hint_received", False):
                    self._transition_zone("boundary_depths")
                else:
                    self._add_message(
                        "回廊の奥は、まだ静かに閉ざされている。中心へ進むための反応が、十分に整っていないようだ。",
                        C_GRAY,
                    )
                    self.player.rect.top = exit_rect.bottom + 2
                return

            self._transition_zone("shrine_inner")
            return

        exits = get_zone_exits(self.current_zone_id)
        if exits:
            self._transition_zone(exits[0]["to"])

    def _is_town_north_exit(self, exit_rect: pygame.Rect) -> bool:
        return exit_rect.centery <= TILE * 4

    def _is_shrine_inner_boundary_exit(self, exit_rect: pygame.Rect) -> bool:
        return exit_rect.centery <= TILE * 3

    def _is_ember_path_deeper_exit(self, exit_rect: pygame.Rect) -> bool:
        return exit_rect.centery <= TILE * 4

    def _is_stonefield_path_deeper_exit(self, exit_rect: pygame.Rect) -> bool:
        return exit_rect.centery <= TILE * 4

    def _is_pale_path_deeper_exit(self, exit_rect: pygame.Rect) -> bool:
        return exit_rect.centery <= TILE * 4

    def _is_boundary_path_deeper_exit(self, exit_rect: pygame.Rect) -> bool:
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

    def _set_story_value(self, flag_name: str, value):
        if self.player and isinstance(flag_name, str) and flag_name:
            self.player.story_flags[flag_name] = value

    def _get_story_flag(self, flag_name: str, default: bool = False) -> bool:
        if self.player and hasattr(self.player, "get_story_flag"):
            return self.player.get_story_flag(flag_name, default)
        return default

    def _get_story_int(self, flag_name: str, default: int = 0) -> int:
        if not self.player:
            return default
        value = getattr(self.player, "story_flags", {}).get(flag_name, default)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
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
        if self._get_story_flag("next_region_route_hint_received", False):
            return "目的：北の道の先に続く新たな経路を探す"
        if self._get_story_flag("next_region_path_hint_received", False):
            return "目的：遠くから届く反応の手がかりを探す"
        if self._get_story_flag("next_region_anomaly_hint_received", False):
            return "目的：古い祠に現れた新たな反応を調べる"
        if self._get_story_flag("boundary_elder_final_report_hint_received", False):
            return "目的：境界の深部で生まれた静かな均衡を老人へ報告する"
        if self._get_story_flag("boundary_integration_ready", False):
            return "目的：境界の深部で静まった反応を見守る"
        if self._get_story_flag("boundary_center_final_return_hint_received", False):
            return "目的：境界の深部に戻り、二つの反応が中心へ戻る様子を見届ける"
        if self._get_story_flag("boundary_dual_traces_complete", False):
            return "目的：境界の深部にある二つの反応について老人へ報告する"
        if self._get_story_flag("boundary_dual_trace_hint_received", False):
            return "目的：境界の深部に現れた二つの反応を調べる"
        if self._get_story_flag("boundary_center_return_hint_received", False):
            return "目的：境界の深部に戻り、色のない揺らぎの変化を見届ける"
        if self._get_story_flag("boundary_center_report_hint_received", False):
            return "目的：境界の深部で起きた均衡の変化を老人へ報告する"
        if self._get_story_flag("boundary_depths_entered", False):
            return "目的：境界の深部にある色のない揺らぎを調べる"
        if self._get_story_flag("boundary_center_hint_received", False):
            return "目的：境界の回廊の奥にある反応の中心へ進む"
        if self._get_story_flag("boundary_path_entered", False):
            return "目的：境界の回廊にある名のない反応を調べる"
        if self._get_story_flag("shrine_unknown_resonance_investigated", False):
            return "目的：古い祠に生まれた静かな均衡を見守る"
        if self._get_story_flag("shrine_center_return_hint_received", False):
            return "目的：古い祠の中心に現れた未知の反応を調べる"
        if self._get_story_flag("pale_choice_reported_to_elder", False):
            return "目的：古い祠の中心に現れた未知の反応を調べる"
        if self._get_story_flag("pale_choice_recorded", False):
            return "目的：白影の奥で起きた変化を老人へ報告する"
        if self._get_story_flag("pale_center_response_hint_received", False):
            return "目的：色のない光の中心で待つ反応に向き合う"
        if self._get_story_flag("pale_dual_traces_complete", False):
            return "目的：二つの反応について白影の奥にいる存在へ伝える"
        if self._get_story_flag("pale_center_dual_trace_hint_received", False):
            return "目的：白影の道と奥に現れた二つの反応を調べる"
        if self._get_story_flag("pale_trial_reported", False):
            return "目的：色のない光の中心で起きた変化を調べる"
        if self._get_story_flag("pale_trial_echoes_complete", False):
            return "目的：白影の奥にいる存在へ試練の結果を伝える"
        if self._get_story_flag("pale_trial_echoes_active", False):
            return "目的：白影の道と奥に現れた三つの反応を調べる"
        if self._get_story_flag("pale_center_return_hint_received", False):
            return "目的：白影の奥にある色のない光の中心へ戻る"
        if self._get_story_flag("pale_echoes_complete", False):
            return "目的：白影の奥にいる存在へ三つの反応を伝える"
        if self._get_story_flag("pale_presence_request_received", False):
            return "目的：白影の奥に残る三つの反応を調べる"
        if self._get_story_flag("pale_unknown_presence_hint_received", False):
            return "目的：白影の奥にいる気配を探す"
        if self._get_story_flag("pale_depths_entered", False):
            return "目的：白影の奥にある色のない光を調べる"
        if self._get_story_flag("pale_light_trace_hint_received", False):
            return "目的：白影の道の奥へ続く光の痕跡を追う"
        if self._get_story_flag("pale_path_entered", False):
            return "目的：白影の道にある未知の反応を調べる"
        if self._get_story_flag("next_anomaly_hint_received", False):
            return "目的：四属性の共鳴が示す未知の反応を探す"
        if self._get_story_flag("earth_fragment_offered", False):
            return "目的：古い祠の変化を老人へ報告する"
        if self._get_story_flag("earth_fragment_obtained", False):
            return "目的：土の欠片を古い祠へ捧げる"
        if self._get_story_flag("earth_fragment_ready_to_receive", False):
            return "目的：現れた土の欠片についてノームに尋ねる"
        if self._get_story_flag("earth_seal_light_revealed", False):
            return "目的：安定した土の封印に現れた光を調べる"
        if self._get_story_flag("earth_support_stones_collected", False):
            return "目的：三つの支えの石を土の封印へ捧げる"
        if self._get_story_flag("earth_seal_stones_hint_received", False):
            return "目的：岩盤の道と深部に散らばった三つの支えの石を探す"
        if self._get_story_flag("earth_trial_completed", False):
            return "目的：土の封印を安定させる方法を探す"
        if self._get_story_flag("earth_trial_echoes_complete", False):
            return "目的：ノームへ試練の結果を伝える"
        if self._get_story_flag("earth_trial_echoes_active", False):
            return "目的：岩盤の道と深部に現れた三つの試練の反応を調べる"
        if self._get_story_flag("earth_trial_ready", False):
            return "目的：土の封印に触れ、ノームの試練に備える"
        if self._get_story_flag("earth_support_traces_complete", False):
            return "目的：支えの痕跡で得たことをノームへ伝える"
        if self._get_story_flag("earth_trial_path_hint_received", False):
            return "目的：岩盤の道と深部に残る支えの痕跡を探す"
        if self._get_story_flag("earth_seal_resonated", False):
            return "目的：土の封印についてノームに尋ねる"
        if self._get_story_flag("earth_trial_hint_received", False):
            return "目的：岩盤の深部にある封印を調べる"
        if self._get_story_flag("stonefield_echoes_complete", False):
            return "目的：岩盤の深部にいる存在へ大地の揺らぎを伝える"
        if self._get_story_flag("stonefield_presence_request_received", False):
            return "目的：岩盤の深部にある大地の揺らぎを調べる"
        if self._get_story_flag("stonefield_presence_hint_received", False):
            return "目的：岩盤の深部にいる存在を探す"
        if self._get_story_flag("stonefield_core_seal_hint_received", False):
            return "目的：岩盤の深部に残る反応を探す"
        if self._get_story_flag("stonefield_depths_entered", False):
            return "目的：岩盤の深部を調べる"
        if self._get_story_flag("stonefield_deeper_path_hint_received", False):
            return "目的：岩盤の道の奥へ進む"
        if self._get_story_flag("stonefield_path_entered", False):
            return "目的：岩盤の道を調べる"
        if self._get_story_flag("earth_region_hint_received", False):
            return "目的：大地の反応がある場所を探す"
        if self._get_story_flag("fire_fragment_offered", False):
            return "目的：老人に火の欠片の反応を報告する"
        if self._get_story_flag("fire_fragment_obtained", False):
            return "目的：火の欠片を古い祠の祭壇へ奉納する"
        if self._get_story_flag("fire_fragment_ready_to_receive", False):
            return "目的：サラマンダーから火の欠片を受け取る"
        if self._get_story_flag("fire_seal_stabilized", False):
            return "目的：火の封印が示した光を調べる"
        if self._get_story_flag("fire_trial_completed", False):
            return "目的：火の封印をもう一度調べる"
        if self._get_story_flag("fire_trial_echoes_complete", False):
            return "目的：サラマンダーに試練で得た答えを伝える"
        if self._get_story_flag("fire_trial_started", False):
            return "目的：熾火の道と熾火の深部に現れた三つの熱の残響を調べる"
        if self._get_story_flag("fire_trial_ready", False):
            return "目的：火の封印に触れ、試練を受ける"
        if self._get_story_flag("fire_memories_complete", False):
            return "目的：サラマンダーに三つの想いを伝える"
        if self._get_story_flag("fire_trial_path_hint_received", False):
            return "目的：熾火の深部に残る三つの想いを探す"
        if self._get_story_flag("fire_seal_resonated", False):
            return "目的：火の封印についてサラマンダーに尋ねる"
        if self._get_story_flag("fire_trial_hint_received", False):
            return "目的：熾火の深部にある封印を調べる"
        if self._get_story_flag("ember_echoes_complete", False):
            return "目的：熾火の深部にいる存在へ熱の揺らぎを伝える"
        if self._get_story_flag("ember_presence_request_received", False):
            return "目的：熾火の深部にある熱の揺らぎを調べる"
        if self._get_story_flag("ember_presence_hint_received", False):
            return "目的：熾火の深部にいる存在を探す"
        if self._get_story_flag("ember_core_seal_hint_received", False):
            return "目的：熾火の深部に残る反応を探す"
        if self._get_story_flag("ember_depths_entered", False):
            return "目的：熾火の深部を調べる"
        if self._get_story_flag("ember_deeper_path_hint_received", False):
            return "目的：熾火の道の奥へ進む"
        if self._get_story_flag("ember_path_entered", False):
            return "目的：熾火の道を調べる"
        if self._get_story_flag("fire_region_hint_received", False):
            return "目的：熱を帯びた場所を探す"
        if self._get_story_flag("water_fragment_offered", False):
            return "目的：老人に水の欠片の反応を報告する"
        if self._get_story_flag("water_fragment_obtained", False):
            return "目的：水の欠片を古い祠の祭壇へ奉納する"
        if self._get_story_flag("water_fragment_ready_to_receive", False):
            return "目的：ウンディーネから水の欠片を受け取る"
        if self._get_story_flag("water_drops_offered", False):
            return "目的：安定した水の封印の奥を調べる"
        if self._get_story_flag("water_drops_collected", False):
            return "目的：三つの水の雫を水の封印へ捧げる"
        if self._get_story_flag("water_seal_reported_to_undine", False):
            return "目的：水鏡の洞窟に散った三つの水の雫を探す"
        if self._get_story_flag("water_seal_investigated", False):
            return "目的：水の封印に必要なものを探す"
        if self._get_story_flag("water_trial_completed", False):
            return "目的：ウンディーネが示す水の封印を調べる"
        if self._get_story_flag("water_trial_echoes_complete", False):
            return "目的：ウンディーネに三つの記憶を伝える"
        if self._get_story_flag("water_trial_started", False):
            return "目的：水鏡の洞窟に現れた三つの記憶を調べる"
        if self._get_story_flag("water_memory_core_found", False):
            return "目的：記憶の核に触れ、水の試練を受ける"
        if self._get_story_flag("water_memory_reported_to_undine", False):
            return "目的：水鏡の間に残る記憶の核を探す"
        if self._get_story_flag("water_memory_traces_complete", False):
            return "目的：ウンディーネに記憶の断片を伝える"
        if self._get_story_flag("undine_encountered", False):
            return "目的：ウンディーネが感じる水の異変を調べる"
        if self._get_story_flag("water_presence_trace_investigated", False):
            return "目的：水鏡の間に残る声の正体を探す"
        if self._get_story_flag("water_mirror_center_investigated", False):
            return "目的：水鏡に映る存在を探す"
        if self._get_story_flag("water_mirror_chamber_anomaly_seen", False):
            return "目的：水鏡の間を調べる"
        if self._get_story_flag("water_reflection_route_hint_received", False):
            return "目的：水鏡の回廊の奥へ進む"
        if self._get_story_flag("water_reflection_corridor_anomaly_seen", False):
            return "目的：水鏡の回廊を調べる"
        if self._get_story_flag("water_depths_path_opened", False):
            return "目的：光が示した先へ進む"
        if self._get_story_flag("water_next_path_hint_received", False):
            return "目的：水鏡の洞窟の奥にある光を調べる"
        if self._get_story_flag("water_route_hint_received", False):
            return "目的：水源の反応について老人に相談する"
        if self._get_story_flag("water_source_anomaly_seen", False):
            return "目的：水源の反応を調べる"
        if self._get_story_flag("water_depths_anomaly_seen", False):
            return "目的：水鏡の洞窟の奥を調べる"
        if self._get_story_flag("water_mirror_investigated", False):
            return "目的：水鏡に映ったものを追う"
        if self._get_story_flag("water_anomaly_seen", False):
            return "目的：水鏡の洞窟を調べる"
        if self._get_story_flag("water_hint_received", False):
            return "目的：水音のする場所を探す"
        if self._get_story_flag("shrine_second_seal_reacted", False) and not self._get_story_flag(
            "shrine_second_reaction_reported", False
        ):
            return "目的：老人に祭壇の変化を報告する"
        if self._get_story_flag("wind_fragment_2_obtained", False):
            return "目的：古い祠へ戻る"
        if self._get_story_flag("sylph_trial_cleared", False):
            return "目的：風の欠片へ向かう"
        if self._get_story_flag("sylph_trial_started", False):
            return "目的：風の標をたどる"
        if self._get_story_flag("sylph_trial_available", False) and not self._get_story_flag(
            "sylph_trial_cleared", False
        ):
            return "目的：シルフの試練を受ける"
        if self._get_story_flag("wind_center_route_found", False):
            return "目的：風の中心へ向かう"
        if self._get_story_flag("wind_gorge_anomaly_seen", False):
            return "目的：風の流れを調べる"
        if self._get_story_flag("wind_gorge_entered", False) and not self._get_story_flag(
            "wind_gorge_anomaly_seen", False
        ):
            return "目的：峡谷の奥を調べる"
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

        if self._get_story_flag("boundary_silent_balance_reported_to_elder", False):
            return "elder_after_boundary_silent_balance_hint"

        if self._get_story_flag("boundary_elder_final_report_hint_received", False):
            return "elder_after_boundary_silent_balance_report"

        if self._get_story_flag("boundary_dual_traces_reported_to_elder", False):
            return "elder_after_boundary_dual_traces_hint"

        if self._get_story_flag("boundary_dual_traces_complete", False):
            return "elder_after_boundary_dual_traces_report"

        if self._get_story_flag("boundary_center_reported_to_elder", False):
            return "elder_after_boundary_center_hint"

        if self._get_story_flag("boundary_center_report_hint_received", False):
            return "elder_after_boundary_center_report"

        if self._get_story_flag("pale_choice_reported_to_elder", False):
            return "elder_after_pale_choice_hint"

        if self._get_story_flag("pale_center_choice_made", False):
            return "elder_after_pale_choice_report"

        if self._get_story_flag("earth_fragment_reported_to_elder", False):
            return "elder_after_fifth_seal_hint"

        if self._get_story_flag("shrine_fifth_seal_reacted", False) and not self._get_story_flag(
            "earth_fragment_reported_to_elder", False
        ):
            return "elder_after_fifth_seal_reaction"

        if self._get_story_flag("earth_region_hint_received", False):
            return "elder_after_earth_hint"

        if self._get_story_flag("shrine_fourth_seal_reacted", False) and not self._get_story_flag(
            "fire_fragment_reported_to_elder", False
        ):
            return "elder_after_fourth_seal_reaction"

        if self._get_story_flag("fire_region_hint_received", False):
            return "elder_after_fire_hint"

        if self._get_story_flag("shrine_third_seal_reacted", False) and not self._get_story_flag(
            "water_fragment_reported_to_elder", False
        ):
            return "elder_after_third_seal_reaction"

        if self._get_story_flag("water_next_path_hint_received", False):
            return "elder_after_water_source_report"

        if self._get_story_flag("water_route_hint_received", False):
            return "elder_after_water_source_reaction"

        if self._get_story_flag("water_hint_received", False):
            return "elder_after_water_hint"

        if self._get_story_flag("shrine_second_seal_reacted", False) and not self._get_story_flag(
            "shrine_second_reaction_reported", False
        ):
            return "elder_after_second_seal_reaction"

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

    def _update_wind_gorge_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "field":
            return

        for wind_rect in getattr(self.world, "wind_rects", []):
            if not self.player.rect.colliderect(wind_rect):
                continue

            if self._get_story_flag("next_fragment_hint_received", False):
                self._transition_zone("wind_gorge")
            else:
                self._add_message("強い風が吹く方向が気になるが、まだ手がかりが足りない。", C_GRAY)
                self.player.rect.top = wind_rect.bottom + 2
            return

    def _update_water_cave_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "field":
            return

        for water_rect in getattr(self.world, "water_rects", []):
            if not self.player.rect.colliderect(water_rect):
                continue

            if self._get_story_flag("water_hint_received", False):
                self._transition_zone("water_cave")
            else:
                self._add_message(
                    "水音がかすかに聞こえるが、まだ手がかりが足りない。",
                    C_GRAY,
                )
                self.player.rect.top = water_rect.bottom + 2
            return

    def _update_water_cave_depths_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "water_cave":
            return

        for depth_rect in getattr(self.world, "water_depth_rects", []):
            if not self.player.rect.colliderect(depth_rect):
                continue

            if self._get_story_flag("water_reflection_seen", False):
                self._transition_zone("water_cave_depths")
            else:
                self._add_message(
                    "奥へ続く水路がある。だが、どこへ向かうべきか分からない。",
                    C_GRAY,
                )
                self.player.rect.top = depth_rect.bottom + 2
            return

    def _update_water_cave_source_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "water_cave_depths":
            return

        for source_rect in getattr(self.world, "water_source_rects", []):
            if not self.player.rect.colliderect(source_rect):
                continue

            if self._get_story_flag("water_depths_anomaly_seen", False):
                self._transition_zone("water_cave_source")
            else:
                self._add_message(
                    "淡い光は見える。だが、水流の向かう先まではまだ分からない。",
                    C_GRAY,
                )
                self.player.rect.top = source_rect.bottom + 2
            return

    def _update_water_cave_reflection_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "water_cave_depths":
            return

        for reflection_rect in getattr(self.world, "water_reflection_rects", []):
            if not self.player.rect.colliderect(reflection_rect):
                continue

            if self._get_story_flag("water_depths_path_opened", False):
                self._transition_zone("water_cave_reflection")
            else:
                self._add_message(
                    "淡い光が揺れている。だが、まだ進むべき道は見えていない。",
                    C_GRAY,
                )
                self.player.rect.top = reflection_rect.bottom + 2
            return

    def _update_water_cave_mirror_chamber_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "water_cave_reflection":
            return

        for chamber_rect in getattr(self.world, "water_chamber_rects", []):
            if not self.player.rect.colliderect(chamber_rect):
                continue

            if self._get_story_flag("water_reflection_route_hint_received", False):
                self._transition_zone("water_cave_mirror_chamber")
            else:
                self._add_message(
                    "回廊の奥に揺らぎがある。だが、まだ足を踏み入れる理由がない。",
                    C_GRAY,
                )
                self.player.rect.top = chamber_rect.bottom + 2
            return

    def _update_ember_path_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "field":
            return

        for ember_rect in getattr(self.world, "ember_rects", []):
            if not self.player.rect.colliderect(ember_rect):
                continue

            if self._get_story_flag("fire_path_unlocked_hint_received", False):
                self._transition_zone("ember_path")
            else:
                self._add_message(
                    "遠くに熱を感じる。だが、まだどこへ向かうべきか分からない。",
                    C_GRAY,
                )
                self.player.rect.top = ember_rect.bottom + 2
            return

    def _update_stonefield_path_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "field":
            return

        for stonefield_rect in getattr(self.world, "stonefield_rects", []):
            if not self.player.rect.colliderect(stonefield_rect):
                continue

            if self._get_story_flag("earth_path_unlocked_hint_received", False):
                self._transition_zone("stonefield_path")
            else:
                self._add_message(
                    "足元の奥から、かすかな大地の反応を感じる。だが、まだ向かうべき場所を見つけられていない。",
                    C_GRAY,
                )
                self.player.rect.top = stonefield_rect.bottom + 2
            return

    def _update_pale_path_transition(self) -> None:
        if not self.world or not self.player:
            return
        if self.current_zone_id != "field":
            return

        for pale_rect in getattr(self.world, "pale_rects", []):
            if not self.player.rect.colliderect(pale_rect):
                continue

            if self._get_story_flag("next_anomaly_hint_received", False):
                self._transition_zone("pale_path")
            else:
                self._add_message(
                    "まだ、この先へ続く反応を捉えられていない。四つの響きが示した場所を探す必要がある。",
                    C_GRAY,
                )
                self.player.rect.top = pale_rect.bottom + 2
            return

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

    def _try_investigate_distant_resonance_trace(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "north_road":
            return False
        if not self._get_story_flag("next_region_path_hint_received", False):
            return False

        trace_rect = pygame.Rect(17 * TILE, 7 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(trace_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("distant_resonance_trace_found", False):
            self._add_message(
                "細い反応の痕跡は、北の道のさらに先へ続いている。まだ見えない場所が、静かに応えているようだ。",
                C_GRAY,
            )
        else:
            self._start_distant_resonance_trace_event()
        return True

    def _start_distant_resonance_trace_event(self) -> None:
        self._set_story_flag("distant_resonance_trace_found", True)
        self._set_story_flag("distant_resonance_direction_seen", True)
        self._set_story_flag("next_region_route_hint_received", True)
        self.current_dialogue_id = "distant_resonance_trace"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("distant_resonance_trace")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("distant_resonance_trace")
        self.state = STATE_DIALOGUE

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

    def _start_wind_gorge_arrival_event(self) -> None:
        self._set_story_flag("wind_gorge_entered", True)
        self.current_dialogue_id = "wind_gorge_arrival"
        self.dialogue_lines = get_dialogue_lines("wind_gorge_arrival")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("wind_gorge_arrival")
        self.state = STATE_DIALOGUE

    def _start_water_cave_arrival_event(self) -> None:
        self._set_story_flag("water_cave_entered", True)
        self._set_story_flag("water_anomaly_seen", True)
        self.current_dialogue_id = "water_cave_arrival"
        self.dialogue_lines = get_dialogue_lines("water_cave_arrival")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_cave_arrival")
        self.state = STATE_DIALOGUE

    def _start_water_cave_depths_arrival_event(self) -> None:
        self._set_story_flag("water_depths_entered", True)
        self._set_story_flag("water_depths_anomaly_seen", True)
        self.current_dialogue_id = "water_cave_depths_arrival"
        self.dialogue_lines = get_dialogue_lines("water_cave_depths_arrival")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_cave_depths_arrival")
        self.state = STATE_DIALOGUE

    def _start_water_cave_source_arrival_event(self) -> None:
        self._set_story_flag("water_source_entered", True)
        self._set_story_flag("water_source_anomaly_seen", True)
        self.current_dialogue_id = "water_cave_source_arrival"
        self.dialogue_lines = get_dialogue_lines("water_cave_source_arrival")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_cave_source_arrival")
        self.state = STATE_DIALOGUE

    def _start_water_cave_reflection_arrival_event(self) -> None:
        self._set_story_flag("water_reflection_corridor_entered", True)
        self._set_story_flag("water_reflection_corridor_anomaly_seen", True)
        self.current_dialogue_id = "water_cave_reflection_arrival"
        self.dialogue_lines = get_dialogue_lines("water_cave_reflection_arrival")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_cave_reflection_arrival")
        self.state = STATE_DIALOGUE

    def _start_water_cave_mirror_chamber_arrival_event(self) -> None:
        self._set_story_flag("water_mirror_chamber_entered", True)
        self._set_story_flag("water_mirror_chamber_anomaly_seen", True)
        self.current_dialogue_id = "water_cave_mirror_chamber_arrival"
        self.dialogue_lines = get_dialogue_lines("water_cave_mirror_chamber_arrival")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_cave_mirror_chamber_arrival")
        self.state = STATE_DIALOGUE

    def _start_ember_path_arrival_event(self) -> None:
        self._set_story_flag("ember_path_entered", True)
        self._set_story_flag("ember_path_heat_anomaly_seen", True)
        self.current_dialogue_id = "ember_path_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("ember_path_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("ember_path_arrival")
        self.state = STATE_DIALOGUE

    def _start_ember_depths_arrival_event(self) -> None:
        self._set_story_flag("ember_depths_entered", True)
        self._set_story_flag("ember_depths_anomaly_seen", True)
        self.current_dialogue_id = "ember_depths_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("ember_depths_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("ember_depths_arrival")
        self.state = STATE_DIALOGUE

    def _start_stonefield_path_arrival_event(self) -> None:
        self._set_story_flag("stonefield_path_entered", True)
        self._set_story_flag("stonefield_ground_anomaly_seen", True)
        self.current_dialogue_id = "stonefield_path_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("stonefield_path_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("stonefield_path_arrival")
        self.state = STATE_DIALOGUE

    def _start_stonefield_depths_arrival_event(self) -> None:
        self._set_story_flag("stonefield_depths_entered", True)
        self._set_story_flag("stonefield_depths_anomaly_seen", True)
        self.current_dialogue_id = "stonefield_depths_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("stonefield_depths_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("stonefield_depths_arrival")
        self.state = STATE_DIALOGUE

    def _start_pale_path_arrival_event(self) -> None:
        self._set_story_flag("pale_path_entered", True)
        self._set_story_flag("pale_path_anomaly_seen", True)
        self.current_dialogue_id = "pale_path_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_path_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_path_arrival")
        self.state = STATE_DIALOGUE

    def _start_pale_depths_arrival_event(self) -> None:
        self._set_story_flag("pale_depths_entered", True)
        self._set_story_flag("pale_depths_anomaly_seen", True)
        self.current_dialogue_id = "pale_depths_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_depths_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_depths_arrival")
        self.state = STATE_DIALOGUE

    def _start_boundary_path_arrival_event(self) -> None:
        self._set_story_flag("boundary_path_entered", True)
        self._set_story_flag("boundary_path_resonance_seen", True)
        self.current_dialogue_id = "boundary_path_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("boundary_path_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("boundary_path_arrival")
        self.state = STATE_DIALOGUE

    def _start_boundary_depths_arrival_event(self) -> None:
        self._set_story_flag("boundary_depths_entered", True)
        self._set_story_flag("boundary_depths_center_seen", True)
        self.current_dialogue_id = "boundary_depths_arrival"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("boundary_depths_arrival")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("boundary_depths_arrival")
        self.state = STATE_DIALOGUE

    def _try_investigate_boundary_resonance(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "boundary_path":
            return False
        if not self._get_story_flag("boundary_path_resonance_seen", False):
            return False

        resonance_rect = pygame.Rect(12 * TILE, 7 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(resonance_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("boundary_resonance_investigated", False):
            self._add_message(
                "四つの反応と色のない揺らぎは、回廊の奥へ続いている。その先に、まだ見えない中心があるようだ。",
                C_GRAY,
            )
        else:
            self._start_boundary_resonance_event()
        return True

    def _try_investigate_boundary_center(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "boundary_depths":
            return False
        if not self._get_story_flag("boundary_depths_center_seen", False):
            return False

        center_rect = pygame.Rect(12 * TILE, 8 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(center_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("boundary_integration_ready", False):
            if self._get_story_flag("boundary_silent_balance_observed", False):
                self._add_message(
                    "異なる反応は、互いを消そうとしていない。色のない揺らぎの中心で、静かな均衡を保っている。",
                    C_GRAY,
                )
            else:
                self._start_boundary_silent_balance_event()
            return True

        if self._get_story_flag("boundary_center_final_return_hint_received", False):
            if self._get_story_flag("boundary_integration_event_seen", False):
                self._add_message(
                    "二つの余韻は、互いを消さずに中心へ戻っている。色のない揺らぎは、まだ静かに何かを待っている。",
                    C_GRAY,
                )
            else:
                self._start_boundary_integration_event()
            return True

        if self._get_story_flag("boundary_center_return_hint_received", False):
            if self._get_story_flag("boundary_center_change_seen", False):
                self._add_message(
                    "色のない揺らぎから生まれた二つの余韻は、まだ同じ中心を離れずに残っている。",
                    C_GRAY,
                )
            else:
                self._start_boundary_center_change_event()
            return True

        if self._get_story_flag("boundary_center_investigated", False):
            self._add_message(
                "四つの反応は、色のない揺らぎを閉じ込めてはいない。崩れないように、静かに支え続けている。",
                C_GRAY,
            )
        else:
            self._start_boundary_center_investigation_event()
        return True

    def _start_boundary_center_investigation_event(self) -> None:
        self._set_story_flag("boundary_center_investigated", True)
        self._set_story_flag("boundary_center_balance_seen", True)
        self._set_story_flag("boundary_center_report_hint_received", True)
        self.current_dialogue_id = "boundary_center_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("boundary_center_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("boundary_center_investigation")
        self.state = STATE_DIALOGUE

    def _start_boundary_center_change_event(self) -> None:
        self._set_story_flag("boundary_center_change_seen", True)
        self._set_story_flag("boundary_dual_resonance_revealed", True)
        self._set_story_flag("boundary_dual_trace_hint_received", True)
        self.current_dialogue_id = "boundary_center_change"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("boundary_center_change")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("boundary_center_change")
        self.state = STATE_DIALOGUE

    def _start_boundary_integration_event(self) -> None:
        self._set_story_flag("boundary_integration_event_seen", True)
        self._set_story_flag("boundary_dual_traces_returned", True)
        self._set_story_flag("boundary_integration_ready", True)
        self.current_dialogue_id = "boundary_integration_event"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("boundary_integration_event")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("boundary_integration_event")
        self.state = STATE_DIALOGUE

    def _start_boundary_silent_balance_event(self) -> None:
        self._set_story_flag("boundary_silent_balance_observed", True)
        self._set_story_flag("boundary_center_stabilized", True)
        self._set_story_flag("boundary_elder_final_report_hint_received", True)
        self.current_dialogue_id = "boundary_silent_balance_observation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("boundary_silent_balance_observation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("boundary_silent_balance_observation")
        self.state = STATE_DIALOGUE

    def _try_investigate_boundary_dual_trace(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "boundary_depths":
            return False
        if not self._get_story_flag("boundary_dual_trace_hint_received", False):
            return False

        targets = (
            (
                "forward",
                pygame.Rect(8 * TILE, 8 * TILE, TILE, TILE),
                "boundary_forward_trace_investigated",
                "細い余韻は、急かすことなく前方へ伸びている。",
            ),
            (
                "stillness",
                pygame.Rect(16 * TILE, 8 * TILE, TILE, TILE),
                "boundary_stillness_trace_investigated",
                "静かな余韻は、消えずに中心の近くへ残っている。",
            ),
        )
        for trace_id, trace_rect, flag_name, repeat_message in targets:
            if not self.player.rect.colliderect(trace_rect.inflate(TILE, TILE)):
                continue
            if self._get_story_flag(flag_name, False):
                self._add_message(repeat_message, C_GRAY)
            else:
                self._start_boundary_dual_trace_event(trace_id, flag_name)
            return True
        return False

    def _start_boundary_dual_trace_event(self, trace_id: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        if (
            self._get_story_flag("boundary_forward_trace_investigated", False)
            and self._get_story_flag("boundary_stillness_trace_investigated", False)
        ):
            self._set_story_flag("boundary_dual_traces_complete", True)

        dialogue_id = f"boundary_dual_trace_{trace_id}"
        self.current_dialogue_id = dialogue_id
        lines = list(get_dialogue_lines(dialogue_id))
        if self._get_story_flag("boundary_dual_traces_complete", False):
            lines.extend(get_dialogue_lines("boundary_dual_traces_complete"))
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in lines
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _start_boundary_resonance_event(self) -> None:
        self._set_story_flag("boundary_resonance_investigated", True)
        self._set_story_flag("boundary_resonance_converged", True)
        self._set_story_flag("boundary_center_hint_received", True)
        self.current_dialogue_id = "boundary_resonance_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("boundary_resonance_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("boundary_resonance_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_pale_light_center(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "pale_depths":
            return False
        if not self._get_story_flag("pale_depths_anomaly_seen", False):
            return False

        pale_light_center_rect = pygame.Rect(12 * TILE, 6 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(pale_light_center_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("pale_center_choice_made", False):
            self._add_message(
                "色のない光は、静かに揺れている。あの時に選んだ答えは、まだ終わりではないようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("pale_center_response_hint_received", False):
            self._start_pale_center_choice_event()
            return True

        if self._get_story_flag("pale_center_reexamined", False):
            self._add_message(
                "色のない光は、二つの淡い反応を待っている。どちらかだけでは、この中心を支えられないようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("pale_trial_completed", False):
            self._start_pale_center_reexamination_event()
            return True

        if self._get_story_flag("pale_trial_started", False):
            self._add_message(
                "色のない光は、淡い影と静かに重なっている。三つの反応は、すでに白影のどこかで待っているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("pale_center_return_hint_received", False):
            self._start_pale_trial_start_event()
            return True

        if self._get_story_flag("pale_light_center_investigated", False):
            self._add_message(
                "色のない光は、足元の影と静かに重なっている。この奥には、まだ見えない気配が残っているようだ。",
                C_GRAY,
            )
            return True

        self._start_pale_light_center_investigation_event()
        return True

    def _start_pale_light_center_investigation_event(self) -> None:
        self._set_story_flag("pale_light_center_investigated", True)
        self._set_story_flag("pale_light_center_resonated", True)
        self._set_story_flag("pale_unknown_presence_hint_received", True)
        self.current_dialogue_id = "pale_light_center_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_light_center_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_light_center_investigation")
        self.state = STATE_DIALOGUE

    def _start_pale_trial_start_event(self) -> None:
        self._set_story_flag("pale_trial_started", True)
        self._set_story_flag("pale_trial_light_shadow_shift_seen", True)
        self._set_story_flag("pale_trial_echoes_active", True)
        self.current_dialogue_id = "pale_trial_start"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_trial_start")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_trial_start")
        self.state = STATE_DIALOGUE

    def _start_pale_center_reexamination_event(self) -> None:
        self._set_story_flag("pale_center_reexamined", True)
        self._set_story_flag("pale_center_balance_hint_received", True)
        self._set_story_flag("pale_center_dual_trace_hint_received", True)
        self.current_dialogue_id = "pale_center_reexamination"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_center_reexamination")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_center_reexamination")
        self.state = STATE_DIALOGUE

    def _start_pale_center_choice_event(self) -> None:
        self.current_dialogue_id = "pale_center_choice"
        self.dialogue_speaker = self.get_support_system_display_name()
        self.pale_choice_prompt_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_center_choice_prompt")
        ]
        self.pale_choice_options = [
            ("forward", "前へ進むための光を信じる"),
            ("stillness", "失ったものを抱えたまま進む"),
            ("integration", "どちらも切り捨てずに進む"),
        ]
        self.pale_choice_cursor = 0
        self.dialogue_lines = []
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_center_choice")
        self.state = STATE_PALE_CHOICE

    def _confirm_pale_center_choice(self, choice_id: str) -> None:
        self._set_story_flag("pale_center_choice_made", True)
        self._set_story_flag("pale_choice_recorded", True)
        self._set_story_flag("pale_choice_forward_selected", choice_id == "forward")
        self._set_story_flag("pale_choice_stillness_selected", choice_id == "stillness")
        self._set_story_flag("pale_choice_integration_selected", choice_id == "integration")

        dialogue_id = {
            "forward": "pale_center_choice_forward",
            "stillness": "pale_center_choice_stillness",
            "integration": "pale_center_choice_integration",
        }.get(choice_id, "pale_center_choice_integration")
        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self.pale_choice_options = []
        self.pale_choice_cursor = 0
        self.pale_choice_prompt_lines = []
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_start_pale_presence_encounter(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "pale_depths":
            return False
        if not self._get_story_flag("pale_unknown_presence_hint_received", False):
            return False

        pale_presence_rect = pygame.Rect(16 * TILE, 6 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(pale_presence_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("pale_dual_traces_reported", False):
            self._add_message(
                "輪郭のない気配は、以前より静かに揺れている。中心の光は、まだお前の答えを待っているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("pale_dual_traces_complete", False):
            self._start_pale_dual_traces_report_event()
            return True

        if self._get_story_flag("pale_trial_reported", False):
            self._add_message(
                "輪郭のない気配は、以前より静かに揺れている。だが、中心の光にはまだ確かめるべきことが残っているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("pale_trial_echoes_complete", False):
            self._start_pale_trial_report_event()
            return True

        if self._get_story_flag("pale_echoes_reported", False):
            self._add_message(
                "輪郭のない気配は、淡い光と影の間に立っている。答えは、まだ中心の光の奥にあるようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("pale_echoes_complete", False):
            self._start_pale_echoes_report_event()
            return True

        if self._get_story_flag("pale_presence_encountered", False):
            self._add_message(
                "輪郭のない気配は、淡い光と影の間に残っている。まだ何も答えず、こちらを見ているようだ。",
                C_GRAY,
            )
            return True

        self._start_pale_presence_encounter_event()
        return True

    def _start_pale_presence_encounter_event(self) -> None:
        self._set_story_flag("pale_presence_encountered", True)
        self._set_story_flag("pale_unknown_presence_revealed", True)
        self._set_story_flag("pale_presence_request_received", True)
        self.current_dialogue_id = "pale_presence_encounter"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_presence_encounter")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_presence_encounter")
        self.state = STATE_DIALOGUE

    def _start_pale_echoes_report_event(self) -> None:
        self._set_story_flag("pale_echoes_reported", True)
        self._set_story_flag("pale_trial_hint_received", True)
        self._set_story_flag("pale_center_return_hint_received", True)
        self.current_dialogue_id = "pale_echoes_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_echoes_report")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_echoes_report")
        self.state = STATE_DIALOGUE

    def _start_pale_trial_report_event(self) -> None:
        self._set_story_flag("pale_trial_reported", True)
        self._set_story_flag("pale_trial_completed", True)
        self._set_story_flag("pale_memory_accepted", True)
        self.current_dialogue_id = "pale_trial_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_trial_report")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_trial_report")
        self.state = STATE_DIALOGUE

    def _start_pale_dual_traces_report_event(self) -> None:
        self._set_story_flag("pale_dual_traces_reported", True)
        self._set_story_flag("pale_choice_prepared", True)
        self._set_story_flag("pale_center_response_hint_received", True)
        self.current_dialogue_id = "pale_dual_traces_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_dual_traces_report")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_dual_traces_report")
        self.state = STATE_DIALOGUE

    def _try_investigate_pale_dual_trace(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("pale_center_dual_trace_hint_received", False):
            return False

        for location, target_rect, flag_name in self._get_pale_dual_trace_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "二つの反応は、別々の場所で静かに揺れている。どちらも、中心の光へ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_pale_dual_trace_event(location, flag_name)
            return True

        return False

    def _get_pale_dual_trace_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "pale_path":
            return [
                ("forward", pygame.Rect(18 * TILE, 5 * TILE, TILE, TILE), "pale_dual_trace_forward_seen"),
            ]

        if self.current_zone_id == "pale_depths":
            return [
                ("stillness", pygame.Rect(6 * TILE, 10 * TILE, TILE, TILE), "pale_dual_trace_stillness_seen"),
            ]

        return []

    def _start_pale_dual_trace_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "pale_dual_trace_forward_seen",
                "pale_dual_trace_stillness_seen",
            )
        )
        if completed:
            self._set_story_flag("pale_dual_traces_complete", True)

        dialogue_id = f"pale_dual_trace_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("pale_dual_traces_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_pale_trial_echo(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("pale_trial_echoes_active", False):
            return False

        for location, target_rect, flag_name in self._get_pale_trial_echo_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "淡い反応は、静かに落ち着いている。試練で得た答えは、あの存在のもとへ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_pale_trial_echo_event(location, flag_name)
            return True

        return False

    def _get_pale_trial_echo_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "pale_path":
            return [
                ("path", pygame.Rect(6 * TILE, 9 * TILE, TILE, TILE), "pale_trial_echo_path_seen"),
                ("balance", pygame.Rect(15 * TILE, 6 * TILE, TILE, TILE), "pale_trial_echo_balance_seen"),
            ]

        if self.current_zone_id == "pale_depths":
            return [
                ("depths", pygame.Rect(19 * TILE, 8 * TILE, TILE, TILE), "pale_trial_echo_depths_seen"),
            ]

        return []

    def _start_pale_trial_echo_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "pale_trial_echo_path_seen",
                "pale_trial_echo_balance_seen",
                "pale_trial_echo_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("pale_trial_echoes_complete", True)

        dialogue_id = f"pale_trial_echo_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("pale_trial_echoes_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_pale_echo(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("pale_presence_request_received", False):
            return False

        for location, target_rect, flag_name in self._get_pale_echo_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "淡い反応は静かになっている。受け取った気配は、あの存在のもとへ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_pale_echo_event(location, flag_name)
            return True

        return False

    def _get_pale_echo_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "pale_path":
            return [
                ("shadow", pygame.Rect(8 * TILE, 5 * TILE, TILE, TILE), "pale_echo_shadow_seen"),
                ("balance", pygame.Rect(17 * TILE, 10 * TILE, TILE, TILE), "pale_echo_balance_seen"),
            ]

        if self.current_zone_id == "pale_depths":
            return [
                ("depths", pygame.Rect(15 * TILE, 11 * TILE, TILE, TILE), "pale_echo_depths_seen"),
            ]

        return []

    def _start_pale_echo_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "pale_echo_shadow_seen",
                "pale_echo_balance_seen",
                "pale_echo_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("pale_echoes_complete", True)

        dialogue_id = f"pale_echo_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("pale_echoes_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_pale_light(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "pale_path":
            return False
        if not self._get_story_flag("pale_path_anomaly_seen", False):
            return False

        pale_light_rect = pygame.Rect(12 * TILE, 5 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(pale_light_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("pale_light_investigated", False):
            self._add_message(
                "淡い光は、道の奥へ向かって静かに揺れている。その先に、まだ見えない何かがあるようだ。",
                C_GRAY,
            )
            return True

        self._start_pale_light_investigation_event()
        return True

    def _start_pale_light_investigation_event(self) -> None:
        self._set_story_flag("pale_light_investigated", True)
        self._set_story_flag("pale_light_resonated", True)
        self._set_story_flag("pale_light_trace_hint_received", True)
        self.current_dialogue_id = "pale_light_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("pale_light_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("pale_light_investigation")
        self.state = STATE_DIALOGUE

    def _try_start_stonefield_presence_encounter(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "stonefield_depths":
            return False
        if not self._get_story_flag("stonefield_presence_hint_received", False):
            return False

        presence_rect = pygame.Rect(14 * TILE, 11 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(presence_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("earth_fragment_obtained", False):
            self._add_message(
                "その欠片は、ただ守るための石ではない。お前が誰と支え合うかを、これからも問い続けるだろう。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_fragment_ready_to_receive", False):
            self._start_earth_fragment_grant_event()
            return True

        if self._get_story_flag("earth_trial_reported_to_gnome", False):
            self._add_message(
                "支えるとは、重さに耐えることだけではない。お前が選び、誰かと分け合う意志もまた、大地を支える。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_trial_echoes_complete", False):
            self._start_earth_trial_report_event()
            return True

        if self._get_story_flag("earth_support_traces_reported", False):
            self._add_message(
                "重さを恐れるな。だが、一人で抱えることを強さと取り違えるな。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_support_traces_complete", False):
            self._start_earth_support_traces_report_event()
            return True

        if self._get_story_flag("earth_seal_reported_to_gnome", False):
            self._add_message(
                "支えるとは、ただ耐えることではない。何を守り、誰と重さを分けるかを選ぶことだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_seal_resonated", False):
            self._start_earth_seal_report_event()
            return True

        if self._get_story_flag("stonefield_echoes_reported", False):
            self._add_message(
                "強く立つだけでは足りぬ。支えるものを知り、支えられることも受け入れよ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("stonefield_echoes_complete", False):
            self._start_stonefield_echoes_report_event()
            return True

        if self._get_story_flag("stonefield_presence_encountered", False):
            self._add_message(
                "大地は、ただ重いだけではない。その重さの中で、何を支えるのかを忘れるな。",
                C_GRAY,
            )
            return True

        self._start_stonefield_presence_encounter_event()
        return True

    def _start_stonefield_presence_encounter_event(self) -> None:
        self._set_story_flag("stonefield_presence_encountered", True)
        self._set_story_flag("earth_spirit_presence_revealed", True)
        self._set_story_flag("stonefield_presence_request_received", True)
        self.current_dialogue_id = "stonefield_presence_encounter"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("stonefield_presence_encounter")
        ]
        self.dialogue_speaker = "？？？"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("stonefield_presence_encounter")
        self.state = STATE_DIALOGUE

    def _start_stonefield_echoes_report_event(self) -> None:
        self._set_story_flag("stonefield_echoes_reported", True)
        self._set_story_flag("gnome_revealed", True)
        self._set_story_flag("earth_trial_hint_received", True)
        self.current_dialogue_id = "stonefield_echoes_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("stonefield_echoes_report")
        ]
        self.dialogue_speaker = "ノーム"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("stonefield_echoes_report")
        self.state = STATE_DIALOGUE

    def _start_earth_seal_report_event(self) -> None:
        self._set_story_flag("earth_seal_reported_to_gnome", True)
        self._set_story_flag("earth_trial_requirement_hint_received", True)
        self._set_story_flag("earth_trial_path_hint_received", True)
        self.current_dialogue_id = "earth_seal_report_to_gnome"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_seal_report_to_gnome")
        ]
        self.dialogue_speaker = "ノーム"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_seal_report_to_gnome")
        self.state = STATE_DIALOGUE

    def _start_earth_support_traces_report_event(self) -> None:
        self._set_story_flag("earth_support_traces_reported", True)
        self._set_story_flag("earth_trial_ready", True)
        self._set_story_flag("earth_trial_resonance_seen", True)
        self.current_dialogue_id = "earth_support_traces_report_to_gnome"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_support_traces_report_to_gnome")
        ]
        self.dialogue_speaker = "ノーム"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_support_traces_report_to_gnome")
        self.state = STATE_DIALOGUE

    def _start_earth_trial_report_event(self) -> None:
        self._set_story_flag("earth_trial_reported_to_gnome", True)
        self._set_story_flag("earth_trial_completed", True)
        self._set_story_flag("earth_memory_accepted", True)
        self.current_dialogue_id = "earth_trial_report_to_gnome"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_trial_report_to_gnome")
        ]
        self.dialogue_speaker = "ノーム"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_trial_report_to_gnome")
        self.state = STATE_DIALOGUE

    def _start_earth_fragment_grant_event(self) -> None:
        self._set_story_flag("earth_fragment_granted", True)
        self._set_story_flag("earth_fragment_obtained", True)
        self._set_story_flag("earth_fragment_return_hint_received", True)
        self.current_dialogue_id = "earth_fragment_grant"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_fragment_grant")
        ]
        self.dialogue_speaker = "ノーム"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_fragment_grant")
        self.state = STATE_DIALOGUE

    def _try_collect_earth_support_stone(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("earth_seal_stones_hint_received", False):
            return False

        for location, target_rect, flag_name in self._get_earth_support_stone_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "ここにあった支えの石は、すでに封印へ向けて共鳴している。三つの石を捧げる時が来ているようだ。",
                    C_GRAY,
                )
            else:
                self._start_earth_support_stone_event(location, flag_name)
            return True

        return False

    def _get_earth_support_stone_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "stonefield_path":
            return [
                ("path", pygame.Rect(18 * TILE, 7 * TILE, TILE, TILE), "earth_support_stone_path_found"),
                ("pillar", pygame.Rect(8 * TILE, 10 * TILE, TILE, TILE), "earth_support_stone_pillar_found"),
            ]

        if self.current_zone_id == "stonefield_depths":
            return [
                ("depths", pygame.Rect(19 * TILE, 10 * TILE, TILE, TILE), "earth_support_stone_depths_found"),
            ]

        return []

    def _start_earth_support_stone_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "earth_support_stone_path_found",
                "earth_support_stone_pillar_found",
                "earth_support_stone_depths_found",
            )
        )
        if completed:
            self._set_story_flag("earth_support_stones_collected", True)

        dialogue_id = f"earth_support_stone_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("earth_support_stones_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_earth_trial_echo(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("earth_trial_echoes_active", False):
            return False

        for location, target_rect, flag_name in self._get_earth_trial_echo_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "大地の反応は、静かに落ち着いている。試練で得た答えは、ノームのもとへ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_earth_trial_echo_event(location, flag_name)
            return True

        return False

    def _get_earth_trial_echo_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "stonefield_path":
            return [
                ("path", pygame.Rect(6 * TILE, 8 * TILE, TILE, TILE), "earth_trial_echo_path_seen"),
                ("pillar", pygame.Rect(14 * TILE, 6 * TILE, TILE, TILE), "earth_trial_echo_pillar_seen"),
            ]

        if self.current_zone_id == "stonefield_depths":
            return [
                ("depths", pygame.Rect(7 * TILE, 6 * TILE, TILE, TILE), "earth_trial_echo_depths_seen"),
            ]

        return []

    def _start_earth_trial_echo_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "earth_trial_echo_path_seen",
                "earth_trial_echo_pillar_seen",
                "earth_trial_echo_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("earth_trial_echoes_complete", True)

        dialogue_id = f"earth_trial_echo_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("earth_trial_echoes_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_earth_support_trace(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("earth_trial_path_hint_received", False):
            return False

        for location, target_rect, flag_name in self._get_earth_support_trace_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "岩は静かに重なり、今も地を支えている。受け取った想いは、ノームのもとへ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_earth_support_trace_event(location, flag_name)
            return True

        return False

    def _get_earth_support_trace_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "stonefield_path":
            return [
                ("path", pygame.Rect(16 * TILE, 5 * TILE, TILE, TILE), "earth_support_trace_path_seen"),
                ("pillar", pygame.Rect(17 * TILE, 10 * TILE, TILE, TILE), "earth_support_trace_pillar_seen"),
            ]

        if self.current_zone_id == "stonefield_depths":
            return [
                ("depths", pygame.Rect(18 * TILE, 8 * TILE, TILE, TILE), "earth_support_trace_depths_seen"),
            ]

        return []

    def _start_earth_support_trace_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "earth_support_trace_path_seen",
                "earth_support_trace_pillar_seen",
                "earth_support_trace_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("earth_support_traces_complete", True)

        dialogue_id = f"earth_support_trace_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("earth_support_traces_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_stonefield_echo(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("stonefield_presence_request_received", False):
            return False

        for location, target_rect, flag_name in self._get_stonefield_echo_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "大地の揺らぎは静かになっている。受け取った重みは、あの存在のもとへ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_stonefield_echo_event(location, flag_name)
            return True

        return False

    def _get_stonefield_echo_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "stonefield_path":
            return [
                ("path", pygame.Rect(7 * TILE, 5 * TILE, TILE, TILE), "stonefield_echo_path_seen"),
                ("pillar", pygame.Rect(13 * TILE, 9 * TILE, TILE, TILE), "stonefield_echo_pillar_seen"),
            ]

        if self.current_zone_id == "stonefield_depths":
            return [
                ("depths", pygame.Rect(8 * TILE, 11 * TILE, TILE, TILE), "stonefield_echo_depths_seen"),
            ]

        return []

    def _start_stonefield_echo_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "stonefield_echo_path_seen",
                "stonefield_echo_pillar_seen",
                "stonefield_echo_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("stonefield_echoes_complete", True)

        dialogue_id = f"stonefield_echo_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("stonefield_echoes_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_earth_seal(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "stonefield_depths":
            return False
        if not self._get_story_flag("earth_trial_hint_received", False):
            return False

        seal_rect = self._get_earth_seal_rect()
        if not self.player.rect.colliderect(seal_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("earth_fragment_seen", False):
            self._add_message(
                "土の欠片は、封印の中心で静かに浮かんでいる。その光は、ノームの意思を待っているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_seal_light_revealed", False):
            self._start_earth_fragment_revelation_event()
            return True

        if self._get_story_flag("earth_support_stones_offered", False):
            self._add_message(
                "三つの支えの石は、封印と静かに共鳴している。中心に残る微かな光が、何かを待っているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_support_stones_collected", False):
            self._start_earth_support_stones_offering_event()
            return True

        if self._get_story_flag("earth_seal_reexamined", False):
            self._add_message(
                "封印は、三つの支えを待っている。大地に散った反応を見つけなければならない。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_trial_completed", False):
            self._start_earth_seal_reexamination_event()
            return True

        if self._get_story_flag("earth_trial_started", False):
            self._add_message(
                "封印は静かに脈打っている。三つの反応は、すでに大地のどこかで待っているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("earth_trial_ready", False):
            self._start_earth_trial_start_event()
            return True

        if self._get_story_flag("earth_seal_investigated", False):
            self._add_message(
                "封印は今も、大地の深い場所で静かに脈打っている。この重さを受け止める方法を、ノームは知っているようだ。",
                C_GRAY,
            )
            return True

        self._start_earth_seal_investigation_event()
        return True

    def _get_earth_seal_rect(self) -> pygame.Rect:
        return pygame.Rect(16 * TILE, 6 * TILE, TILE, TILE)

    def _start_earth_seal_investigation_event(self) -> None:
        self._set_story_flag("earth_seal_found", True)
        self._set_story_flag("earth_seal_investigated", True)
        self._set_story_flag("earth_seal_resonated", True)
        self.current_dialogue_id = "earth_seal_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_seal_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_seal_investigation")
        self.state = STATE_DIALOGUE

    def _start_earth_seal_reexamination_event(self) -> None:
        self._set_story_flag("earth_seal_reexamined", True)
        self._set_story_flag("earth_seal_requirement_hint_received", True)
        self._set_story_flag("earth_seal_stones_hint_received", True)
        self.current_dialogue_id = "earth_seal_reexamination"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_seal_reexamination")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_seal_reexamination")
        self.state = STATE_DIALOGUE

    def _start_earth_support_stones_offering_event(self) -> None:
        self._set_story_flag("earth_support_stones_offered", True)
        self._set_story_flag("earth_seal_stabilized", True)
        self._set_story_flag("earth_seal_light_revealed", True)
        self.current_dialogue_id = "earth_support_stones_offering"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_support_stones_offering")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_support_stones_offering")
        self.state = STATE_DIALOGUE

    def _start_earth_fragment_revelation_event(self) -> None:
        self._set_story_flag("earth_fragment_revealed", True)
        self._set_story_flag("earth_fragment_seen", True)
        self._set_story_flag("earth_fragment_ready_to_receive", True)
        self.current_dialogue_id = "earth_fragment_revelation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_fragment_revelation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_fragment_revelation")
        self.state = STATE_DIALOGUE

    def _start_earth_trial_start_event(self) -> None:
        self._set_story_flag("earth_trial_started", True)
        self._set_story_flag("earth_trial_ground_shift_seen", True)
        self._set_story_flag("earth_trial_echoes_active", True)
        self.current_dialogue_id = "earth_trial_start"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("earth_trial_start")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("earth_trial_start")
        self.state = STATE_DIALOGUE

    def _try_investigate_stonefield_seal_mark(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "stonefield_depths":
            return False
        if not self._get_story_flag("stonefield_core_seal_hint_received", False):
            return False

        seal_rect = pygame.Rect(16 * TILE, 9 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(seal_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("stonefield_seal_mark_investigated", False):
            self._add_message(
                "古い刻印は、今も重さを抱え込んでいる。その奥にいる何かは、まだ姿を見せない。",
                C_GRAY,
            )
            return True

        self._start_stonefield_seal_mark_investigation_event()
        return True

    def _start_stonefield_seal_mark_investigation_event(self) -> None:
        self._set_story_flag("stonefield_seal_mark_investigated", True)
        self._set_story_flag("stonefield_seal_voice_heard", True)
        self._set_story_flag("stonefield_presence_hint_received", True)
        self.current_dialogue_id = "stonefield_seal_mark_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("stonefield_seal_mark_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("stonefield_seal_mark_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_stonefield_core(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "stonefield_depths":
            return False
        if not self._get_story_flag("stonefield_depths_anomaly_seen", False):
            return False

        core_rect = pygame.Rect(12 * TILE, 6 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(core_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("stonefield_core_investigated", False):
            self._add_message(
                "岩盤の奥で、重い鼓動が続いている。近づくには、まだ何かが足りないようだ。",
                C_GRAY,
            )
            return True

        self._start_stonefield_core_investigation_event()
        return True

    def _start_stonefield_core_investigation_event(self) -> None:
        self._set_story_flag("stonefield_core_investigated", True)
        self._set_story_flag("stonefield_core_pulse_seen", True)
        self._set_story_flag("stonefield_core_seal_hint_received", True)
        self.current_dialogue_id = "stonefield_core_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("stonefield_core_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("stonefield_core_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_stonefield_rock(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "stonefield_path":
            return False
        if not self._get_story_flag("stonefield_ground_anomaly_seen", False):
            return False

        rock_rect = pygame.Rect(9 * TILE, 5 * TILE, TILE, TILE)
        if not self.player.rect.colliderect(rock_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("stonefield_rock_investigated", False):
            self._add_message(
                "岩盤は今も静かに震えている。この重い響きは、道のさらに奥へ続いているようだ。",
                C_GRAY,
            )
            return True

        self._start_stonefield_rock_investigation_event()
        return True

    def _start_stonefield_rock_investigation_event(self) -> None:
        self._set_story_flag("stonefield_rock_investigated", True)
        self._set_story_flag("stonefield_ground_resonance_seen", True)
        self._set_story_flag("stonefield_deeper_path_hint_received", True)
        self.current_dialogue_id = "stonefield_rock_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("stonefield_rock_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("stonefield_rock_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_fire_trial_echo(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("fire_trial_echoes_active", False):
            return False

        for location, target_rect, flag_name in self._get_fire_trial_echo_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "熱の残響は静かになっている。試練は、サラマンダーのもとへ答えを持ち帰るよう促している。",
                    C_GRAY,
                )
            else:
                self._start_fire_trial_echo_event(location, flag_name)
            return True

        return False

    def _get_fire_trial_echo_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "ember_path":
            return [
                ("path", pygame.Rect(8 * TILE, 3 * TILE, TILE, TILE), "fire_trial_echo_path_seen"),
                ("rock", pygame.Rect(16 * TILE, 3 * TILE, TILE, TILE), "fire_trial_echo_rock_seen"),
            ]

        if self.current_zone_id == "ember_depths":
            return [
                ("depths", pygame.Rect(17 * TILE, 3 * TILE, TILE, TILE), "fire_trial_echo_depths_seen"),
            ]

        return []

    def _start_fire_trial_echo_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "fire_trial_echo_path_seen",
                "fire_trial_echo_rock_seen",
                "fire_trial_echo_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("fire_trial_echoes_complete", True)

        dialogue_id = f"fire_trial_echo_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("fire_trial_echoes_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_fire_fragment_light(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "ember_depths":
            return False
        if not self._get_story_flag("fire_seal_light_revealed", False):
            return False

        light_rect = self._get_fire_fragment_light_rect()
        if not self.player.rect.colliderect(light_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("fire_fragment_seen", False):
            self._add_message(
                "赤い光は静かに揺れている。欠片は、主人公が何を選ぶのかを待っているようだ。",
                C_GRAY,
            )
            return True

        self._start_fire_fragment_light_event()
        return True

    def _get_fire_fragment_light_rect(self) -> pygame.Rect:
        return pygame.Rect(17 * TILE, 11 * TILE, TILE, TILE)

    def _start_fire_fragment_light_event(self) -> None:
        self._set_story_flag("fire_fragment_revealed", True)
        self._set_story_flag("fire_fragment_seen", True)
        self._set_story_flag("fire_fragment_ready_to_receive", True)
        self.current_dialogue_id = "fire_fragment_light_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("fire_fragment_light_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("fire_fragment_light_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_fire_memory(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("fire_trial_path_hint_received", False):
            return False

        for location, target_rect, flag_name in self._get_fire_memory_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "残された熱は静かになっている。受け取った想いは、サラマンダーのもとへ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_fire_memory_event(location, flag_name)
            return True

        return False

    def _get_fire_memory_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if self.current_zone_id == "ember_path":
            return [
                ("ember_path", pygame.Rect(10 * TILE, 11 * TILE, TILE, TILE), "fire_memory_ember_path_seen"),
                ("ember_rock", pygame.Rect(15 * TILE, 10 * TILE, TILE, TILE), "fire_memory_ember_rock_seen"),
            ]

        if self.current_zone_id == "ember_depths":
            return [
                ("ember_depths", pygame.Rect(7 * TILE, 4 * TILE, TILE, TILE), "fire_memory_ember_depths_seen"),
            ]

        return []

    def _start_fire_memory_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "fire_memory_ember_path_seen",
                "fire_memory_ember_rock_seen",
                "fire_memory_ember_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("fire_memories_complete", True)

        dialogue_id = f"fire_memory_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("fire_memories_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_ember_echo(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("ember_presence_request_received", False):
            return False

        for location, target_rect, flag_name in self._get_ember_echo_targets():
            if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
                continue

            if self._get_story_flag(flag_name, False):
                self._add_message(
                    "熱の揺らぎは静かになっている。残された気配は、あの存在のもとへ続いているようだ。",
                    C_GRAY,
                )
            else:
                self._start_ember_echo_event(location, flag_name)
            return True

        return False

    def _get_ember_echo_targets(self) -> list[tuple[str, pygame.Rect, str]]:
        if not self.world:
            return []
        ember_rects = getattr(self.world, "ember_rects", [])
        if not ember_rects:
            return []

        if self.current_zone_id == "ember_path":
            lower_rects = sorted(
                [rect for rect in ember_rects if rect.centery > GAME_AREA_H // 3],
                key=lambda rect: rect.centerx,
            )
            if len(lower_rects) < 2:
                return []
            return [
                ("path", lower_rects[0], "ember_echo_path_seen"),
                ("rock", lower_rects[-1], "ember_echo_rock_seen"),
            ]

        if self.current_zone_id == "ember_depths":
            bottom_rects = sorted(
                ember_rects,
                key=lambda rect: (-rect.centery, abs(rect.centerx - WINDOW_W // 2), rect.centerx),
            )
            return [("depths", bottom_rects[0], "ember_echo_depths_seen")]

        return []

    def _start_ember_echo_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "ember_echo_path_seen",
                "ember_echo_rock_seen",
                "ember_echo_depths_seen",
            )
        )
        if completed:
            self._set_story_flag("ember_echoes_complete", True)

        dialogue_id = f"ember_echo_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("ember_echoes_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_fire_seal(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "ember_depths":
            return False
        if not self._get_story_flag("fire_trial_hint_received", False):
            return False

        seal_rect = self._get_fire_seal_rect()
        if not seal_rect:
            return False
        if not self.player.rect.colliderect(seal_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("fire_seal_stabilized", False):
            self._add_message(
                "火の封印は静かに熱を抱えている。その奥で、小さな光が主人公を待っているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("fire_trial_completed", False):
            self._start_fire_seal_stabilization_event()
            return True

        if self._get_story_flag("fire_trial_started", False):
            self._add_message(
                "火の封印は静かに脈打っている。試されるべきものは、すでに周囲へ現れているようだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("fire_trial_ready", False):
            self._start_fire_trial_start_event()
            return True

        if self._get_story_flag("fire_seal_investigated", False):
            self._add_message(
                "火の封印は、今も熱を抱え込んでいる。この熱を受け止めるには、まだ理解が足りないようだ。",
                C_GRAY,
            )
            return True

        self._start_fire_seal_investigation_event()
        return True

    def _get_fire_seal_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        ember_rects = getattr(self.world, "ember_rects", [])
        if not ember_rects:
            return None
        return sorted(
            ember_rects,
            key=lambda rect: (
                -rect.centery,
                -rect.centerx,
                abs(rect.centerx - WINDOW_W // 2),
            ),
        )[0]

    def _start_fire_seal_investigation_event(self) -> None:
        self._set_story_flag("fire_seal_found", True)
        self._set_story_flag("fire_seal_investigated", True)
        self._set_story_flag("fire_seal_resonated", True)
        self.current_dialogue_id = "fire_seal_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("fire_seal_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("fire_seal_investigation")
        self.state = STATE_DIALOGUE

    def _start_fire_trial_start_event(self) -> None:
        self._set_story_flag("fire_trial_started", True)
        self._set_story_flag("fire_trial_flame_shift_seen", True)
        self._set_story_flag("fire_trial_echoes_active", True)
        self.current_dialogue_id = "fire_trial_start"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("fire_trial_start")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("fire_trial_start")
        self.state = STATE_DIALOGUE

    def _start_fire_seal_stabilization_event(self) -> None:
        self._set_story_flag("fire_seal_stabilized", True)
        self._set_story_flag("fire_seal_light_revealed", True)
        self._set_story_flag("fire_fragment_hint_received", True)
        self.current_dialogue_id = "fire_seal_stabilization"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("fire_seal_stabilization")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("fire_seal_stabilization")
        self.state = STATE_DIALOGUE

    def _try_start_ember_presence_encounter(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "ember_depths":
            return False
        if not self._get_story_flag("ember_presence_hint_received", False):
            return False

        presence_rect = self._get_ember_presence_rect()
        if not presence_rect:
            return False
        if not self.player.rect.colliderect(presence_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("fire_fragment_obtained", False):
            self._add_message(
                "炎は、お前の望みだけを燃やすものではない。お前が残すと選んだものもまた、その熱に映る。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("fire_fragment_ready_to_receive", False):
            self._start_fire_fragment_grant_event()
            return True

        if self._get_story_flag("fire_trial_reported_to_salamander", False):
            self._add_message(
                "お前は、炎をただ力として見なかった。ならば今度は、封印が何を求めているかを見届けろ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("fire_trial_echoes_complete", False):
            self._start_fire_trial_report_event()
            return True

        if self._get_story_flag("fire_memories_reported_to_salamander", False):
            self._add_message(
                "炎を手にするとは、力を得ることではない。残すものを選び、そのために燃え続けることだ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("fire_memories_complete", False):
            self._start_fire_memories_report_event()
            return True

        if self._get_story_flag("fire_seal_reported_to_salamander", False):
            self._add_message(
                "燃やせるかではない。燃やさずに残すものを選べるか……それを見せろ。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("fire_seal_resonated", False):
            self._start_fire_seal_report_event()
            return True

        if self._get_story_flag("ember_echoes_reported", False):
            self._add_message(
                "炎は、すべてを焼くためだけにあるのではない。お前が残したいものを見失うな。",
                C_GRAY,
            )
            return True

        if self._get_story_flag("ember_echoes_complete", False):
            self._start_ember_echoes_report_event()
            return True

        if self._get_story_flag("ember_presence_encountered", False):
            self._add_message(
                "熱は、ただ焼くためにあるのではない。何を守るために燃えるのか……それを見失うな。",
                C_GRAY,
            )
            return True

        self._start_ember_presence_encounter_event()
        return True

    def _get_ember_presence_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        ember_rects = getattr(self.world, "ember_rects", [])
        if not ember_rects:
            return None
        return sorted(
            ember_rects,
            key=lambda rect: (
                rect.centery,
                abs(rect.centerx - WINDOW_W // 2),
                rect.centerx,
            ),
        )[0]

    def _start_ember_presence_encounter_event(self) -> None:
        self._set_story_flag("ember_presence_encountered", True)
        self._set_story_flag("fire_spirit_presence_revealed", True)
        self._set_story_flag("ember_presence_request_received", True)
        self.current_dialogue_id = "ember_presence_encounter"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("ember_presence_encounter")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("ember_presence_encounter")
        self.state = STATE_DIALOGUE

    def _start_ember_echoes_report_event(self) -> None:
        self._set_story_flag("ember_echoes_reported", True)
        self._set_story_flag("salamander_revealed", True)
        self._set_story_flag("fire_trial_hint_received", True)
        self.current_dialogue_id = "ember_echoes_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("ember_echoes_report")
        ]
        self.dialogue_speaker = "サラマンダー"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("ember_echoes_report")
        self.state = STATE_DIALOGUE

    def _start_fire_seal_report_event(self) -> None:
        self._set_story_flag("fire_seal_reported_to_salamander", True)
        self._set_story_flag("fire_trial_requirement_hint_received", True)
        self._set_story_flag("fire_trial_path_hint_received", True)
        self.current_dialogue_id = "fire_seal_report_to_salamander"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("fire_seal_report_to_salamander")
        ]
        self.dialogue_speaker = "サラマンダー"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("fire_seal_report_to_salamander")
        self.state = STATE_DIALOGUE

    def _start_fire_memories_report_event(self) -> None:
        self._set_story_flag("fire_memories_reported_to_salamander", True)
        self._set_story_flag("fire_trial_ready", True)
        self._set_story_flag("fire_trial_resonance_seen", True)
        self.current_dialogue_id = "fire_memories_report_to_salamander"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("fire_memories_report_to_salamander")
        ]
        self.dialogue_speaker = "サラマンダー"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("fire_memories_report_to_salamander")
        self.state = STATE_DIALOGUE

    def _start_fire_trial_report_event(self) -> None:
        self._set_story_flag("fire_trial_reported_to_salamander", True)
        self._set_story_flag("fire_trial_completed", True)
        self._set_story_flag("fire_memory_accepted", True)
        self.current_dialogue_id = "fire_trial_report_to_salamander"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("fire_trial_report_to_salamander")
        ]
        self.dialogue_speaker = "サラマンダー"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("fire_trial_report_to_salamander")
        self.state = STATE_DIALOGUE

    def _start_fire_fragment_grant_event(self) -> None:
        self._set_story_flag("fire_fragment_granted", True)
        self._set_story_flag("fire_fragment_obtained", True)
        self._set_story_flag("fire_fragment_return_hint_received", True)
        self.current_dialogue_id = "salamander_grants_fire_fragment"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("salamander_grants_fire_fragment")
        ]
        self.dialogue_speaker = "サラマンダー"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("salamander_grants_fire_fragment")
        self.state = STATE_DIALOGUE

    def _try_investigate_ember_seal_mark(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "ember_depths":
            return False
        if not self._get_story_flag("ember_core_seal_hint_received", False):
            return False

        seal_rect = self._get_ember_seal_mark_rect()
        if not seal_rect:
            return False
        if not self.player.rect.colliderect(seal_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("ember_seal_mark_investigated", False):
            self._add_message(
                "焦げた刻印は、今も熱を抱え込んでいる。その奥にいる何かは、まだ姿を見せない。",
                C_GRAY,
            )
            return True

        self._start_ember_seal_mark_investigation_event()
        return True

    def _get_ember_seal_mark_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        ember_rects = getattr(self.world, "ember_rects", [])
        if not ember_rects:
            return None
        map_mid_y = GAME_AREA_H // 2
        return sorted(
            ember_rects,
            key=lambda rect: (
                -rect.centerx,
                abs(rect.centery - map_mid_y),
                rect.centery,
            ),
        )[0]

    def _start_ember_seal_mark_investigation_event(self) -> None:
        self._set_story_flag("ember_seal_mark_investigated", True)
        self._set_story_flag("ember_seal_voice_heard", True)
        self._set_story_flag("ember_presence_hint_received", True)
        self.current_dialogue_id = "ember_seal_mark_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("ember_seal_mark_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("ember_seal_mark_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_ember_core(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "ember_depths":
            return False
        if not self._get_story_flag("ember_depths_anomaly_seen", False):
            return False

        core_rect = self._get_ember_core_rect()
        if not core_rect:
            return False
        if not self.player.rect.colliderect(core_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("ember_core_investigated", False):
            self._add_message(
                "地割れの奥で、熱は今も脈打っている。近づくには、まだ何かが足りないようだ。",
                C_GRAY,
            )
            return True

        self._start_ember_core_investigation_event()
        return True

    def _get_ember_core_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        ember_rects = getattr(self.world, "ember_rects", [])
        if not ember_rects:
            return None
        map_center = (WINDOW_W // 2, GAME_AREA_H // 2)
        return sorted(
            ember_rects,
            key=lambda rect: (
                abs(rect.centerx - map_center[0]) + abs(rect.centery - map_center[1]),
                rect.centery,
                rect.centerx,
            ),
        )[0]

    def _start_ember_core_investigation_event(self) -> None:
        self._set_story_flag("ember_core_investigated", True)
        self._set_story_flag("ember_core_pulse_seen", True)
        self._set_story_flag("ember_core_seal_hint_received", True)
        self.current_dialogue_id = "ember_core_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("ember_core_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("ember_core_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_ember_heat_point(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "ember_path":
            return False
        if not self._get_story_flag("ember_path_heat_anomaly_seen", False):
            return False

        heat_rect = self._get_ember_heat_point_rect()
        if not heat_rect:
            return False
        if not self.player.rect.colliderect(heat_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag("ember_heat_point_investigated", False):
            self._add_message(
                "岩はまだ熱を帯びている。この熱は、道のさらに奥へ続いているようだ。",
                C_GRAY,
            )
            return True

        self._start_ember_heat_point_investigation_event()
        return True

    def _get_ember_heat_point_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        ember_rects = getattr(self.world, "ember_rects", [])
        if not ember_rects:
            return None
        return sorted(ember_rects, key=lambda rect: (rect.centery, rect.centerx))[0]

    def _start_ember_heat_point_investigation_event(self) -> None:
        self._set_story_flag("ember_heat_point_investigated", True)
        self._set_story_flag("ember_heat_resonance_seen", True)
        self._set_story_flag("ember_deeper_path_hint_received", True)
        self.current_dialogue_id = "ember_heat_point_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("ember_heat_point_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("ember_heat_point_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_water_mirror_center(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_mirror_chamber":
            return False
        if not self._get_story_flag("water_mirror_chamber_entered", False):
            return False

        for mirror_rect in getattr(self.world, "water_shadow_rects", []):
            if self.player.rect.colliderect(mirror_rect.inflate(TILE, TILE)):
                if self._get_story_flag("water_mirror_center_investigated", False):
                    self._add_message(
                        "水面は静かだ。だが、その奥には確かに誰かの気配が残っている。",
                        C_GRAY,
                    )
                else:
                    self._start_water_mirror_center_event()
                return True

        return False

    def _start_water_mirror_center_event(self) -> None:
        self._set_story_flag("water_mirror_center_investigated", True)
        self._set_story_flag("water_mirror_center_resonated", True)
        self._set_story_flag("water_spirit_presence_detected", True)
        self.current_dialogue_id = "water_mirror_center_investigation"
        self.dialogue_lines = get_dialogue_lines("water_mirror_center_investigation")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_mirror_center_investigation")
        self.state = STATE_DIALOGUE

    def _get_water_presence_trace_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        chamber_rects = getattr(self.world, "water_chamber_rects", [])
        if not chamber_rects:
            return None
        max_right = max(rect.right for rect in chamber_rects)
        right_edge_rects = [rect for rect in chamber_rects if rect.right == max_right]
        return sorted(right_edge_rects, key=lambda rect: rect.centery)[len(right_edge_rects) // 2]

    def _try_investigate_water_presence_trace(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_mirror_chamber":
            return False
        if not self._get_story_flag("water_spirit_presence_detected", False):
            return False

        trace_rect = self._get_water_presence_trace_rect()
        if trace_rect and self.player.rect.colliderect(trace_rect.inflate(TILE // 2, TILE // 2)):
            if self._get_story_flag("water_presence_trace_investigated", False):
                self._add_message(
                    "波紋は消えかけている。だが、誰かの想いだけが水面に残っている。",
                    C_GRAY,
                )
            else:
                self._start_water_presence_trace_event()
            return True

        return False

    def _start_water_presence_trace_event(self) -> None:
        self._set_story_flag("water_presence_trace_investigated", True)
        self._set_story_flag("water_presence_memory_resonated", True)
        self._set_story_flag("water_presence_call_heard", True)
        self.current_dialogue_id = "water_presence_trace_investigation"
        self.dialogue_lines = get_dialogue_lines("water_presence_trace_investigation")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_presence_trace_investigation")
        self.state = STATE_DIALOGUE

    def _get_undine_presence_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        chamber_rects = getattr(self.world, "water_chamber_rects", [])
        if not chamber_rects:
            return None
        min_left = min(rect.left for rect in chamber_rects)
        left_edge_rects = [rect for rect in chamber_rects if rect.left == min_left]
        return sorted(left_edge_rects, key=lambda rect: rect.centery)[len(left_edge_rects) // 2]

    def _try_reveal_undine_presence(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_mirror_chamber":
            return False
        if not self._get_story_flag("water_presence_call_heard", False):
            return False

        presence_rect = self._get_undine_presence_rect()
        if presence_rect and self.player.rect.colliderect(presence_rect.inflate(TILE // 2, TILE // 2)):
            if self._get_story_flag("water_fragment_ready_to_receive", False) and not self._get_story_flag(
                "water_fragment_granted", False
            ):
                self._start_water_fragment_grant_event()
            elif self._get_story_flag("water_seal_resonated", False) and not self._get_story_flag(
                "water_seal_reported_to_undine", False
            ):
                self._start_water_seal_report_event()
            elif self._get_story_flag("water_trial_echoes_complete", False) and not self._get_story_flag(
                "water_trial_reported_to_undine", False
            ):
                self._start_water_trial_report_event()
            elif self._get_story_flag("water_memory_traces_complete", False) and not self._get_story_flag(
                "water_memory_reported_to_undine", False
            ):
                self._start_water_memory_report_event()
            elif self._get_story_flag("undine_encountered", False):
                self._start_undine_repeat_dialogue()
            else:
                self._start_undine_first_encounter_event()
            return True

        return False

    def _start_undine_first_encounter_event(self) -> None:
        self._set_story_flag("undine_presence_revealed", True)
        self._set_story_flag("undine_encountered", True)
        self._set_story_flag("water_spirit_request_received", True)
        self.current_dialogue_id = "undine_first_encounter"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("undine_first_encounter")
        ]
        self.dialogue_speaker = "ウンディーネ"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("undine_first_encounter")
        self.state = STATE_DIALOGUE

    def _start_undine_repeat_dialogue(self) -> None:
        dialogue_id = (
            "undine_after_water_fragment_grant"
            if self._get_story_flag("water_fragment_granted", False)
            else "undine_after_seal_report"
            if self._get_story_flag("water_seal_reported_to_undine", False)
            else "undine_after_trial_report"
            if self._get_story_flag("water_trial_reported_to_undine", False)
            else "undine_after_memory_report"
            if self._get_story_flag("water_memory_reported_to_undine", False)
            else "undine_after_encounter"
        )
        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = get_dialogue_lines(dialogue_id)
        self.dialogue_speaker = "ウンディーネ"
        self.dialogue_index = 0
        self.talking_npc = None
        self.state = STATE_DIALOGUE

    def _start_water_fragment_grant_event(self) -> None:
        self._set_story_flag("water_fragment_granted", True)
        self._set_story_flag("water_fragment_obtained", True)
        self._set_story_flag("water_fragment_return_hint_received", True)
        self.current_dialogue_id = "undine_water_fragment_grant"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("undine_water_fragment_grant")
        ]
        self.dialogue_speaker = "ウンディーネ"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("undine_water_fragment_grant")
        self.state = STATE_DIALOGUE

    def _start_water_memory_report_event(self) -> None:
        self._set_story_flag("water_memory_reported_to_undine", True)
        self._set_story_flag("water_memory_truth_hint_received", True)
        self._set_story_flag("water_trial_path_hint_received", True)
        self.current_dialogue_id = "undine_memory_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("undine_memory_report")
        ]
        self.dialogue_speaker = "ウンディーネ"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("undine_memory_report")
        self.state = STATE_DIALOGUE

    def _start_water_trial_report_event(self) -> None:
        self._set_story_flag("water_trial_reported_to_undine", True)
        self._set_story_flag("water_trial_completed", True)
        self._set_story_flag("water_memory_accepted", True)
        self.current_dialogue_id = "undine_trial_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("undine_trial_report")
        ]
        self.dialogue_speaker = "ウンディーネ"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("undine_trial_report")
        self.state = STATE_DIALOGUE

    def _start_water_seal_report_event(self) -> None:
        self._set_story_flag("water_seal_reported_to_undine", True)
        self._set_story_flag("water_seal_requirement_hint_received", True)
        self._set_story_flag("water_seal_drops_hint_received", True)
        self.current_dialogue_id = "undine_water_seal_report"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("undine_water_seal_report")
        ]
        self.dialogue_speaker = "ウンディーネ"
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("undine_water_seal_report")
        self.state = STATE_DIALOGUE

    def _get_water_seal_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        chamber_rects = getattr(self.world, "water_chamber_rects", [])
        if not chamber_rects:
            return None
        max_bottom = max(rect.bottom for rect in chamber_rects)
        bottom_edge_rects = [rect for rect in chamber_rects if rect.bottom == max_bottom]
        return sorted(bottom_edge_rects, key=lambda rect: rect.centerx)[len(bottom_edge_rects) // 2]

    def _try_investigate_water_seal(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_mirror_chamber":
            return False
        if not self._get_story_flag("water_trial_completed", False):
            return False

        seal_rect = self._get_water_seal_rect()
        if seal_rect and self.player.rect.colliderect(seal_rect.inflate(TILE // 2, TILE // 2)):
            if self._get_story_flag("water_drops_offered", False):
                self._add_message(
                    "水の封印は静かに輝いている。その奥には、まだ確かめるべき反応が残っている。",
                    C_GRAY,
                )
            elif self._get_story_flag("water_drops_collected", False):
                self._start_water_drops_offering_event()
            elif self._get_story_flag("water_seal_investigated", False):
                self._add_message(
                    "水の封印は静かに揺れている。何かが足りないことだけは、確かに感じられる。",
                    C_GRAY,
                )
            else:
                self._start_water_seal_investigation_event()
            return True

        return False

    def _start_water_seal_investigation_event(self) -> None:
        self._set_story_flag("water_seal_found", True)
        self._set_story_flag("water_seal_investigated", True)
        self._set_story_flag("water_seal_resonated", True)
        self.current_dialogue_id = "water_seal_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("water_seal_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_seal_investigation")
        self.state = STATE_DIALOGUE

    def _start_water_drops_offering_event(self) -> None:
        self._set_story_flag("water_drops_offered", True)
        self._set_story_flag("water_seal_stabilized", True)
        self._set_story_flag("water_seal_light_revealed", True)
        self.current_dialogue_id = "water_drops_offering"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("water_drops_offering")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_drops_offering")
        self.state = STATE_DIALOGUE

    def _get_water_fragment_light_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        chamber_rects = getattr(self.world, "water_chamber_rects", [])
        if not chamber_rects:
            return None
        min_top = min(rect.top for rect in chamber_rects)
        top_edge_rects = [rect for rect in chamber_rects if rect.top == min_top]
        return sorted(top_edge_rects, key=lambda rect: rect.centerx)[-1]

    def _try_investigate_water_fragment_light(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_mirror_chamber":
            return False
        if not self._get_story_flag("water_seal_light_revealed", False):
            return False

        light_rect = self._get_water_fragment_light_rect()
        if light_rect and self.player.rect.colliderect(light_rect.inflate(TILE // 2, TILE // 2)):
            if self._get_story_flag("water_fragment_seen", False):
                self._add_message(
                    "水の欠片は静かに浮かんでいる。まだ、誰かの意志を待っているようだ。",
                    C_GRAY,
                )
            else:
                self._start_water_fragment_reveal_event()
            return True

        return False

    def _start_water_fragment_reveal_event(self) -> None:
        self._set_story_flag("water_fragment_revealed", True)
        self._set_story_flag("water_fragment_seen", True)
        self._set_story_flag("water_fragment_ready_to_receive", True)
        self.current_dialogue_id = "water_fragment_reveal"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("water_fragment_reveal")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_fragment_reveal")
        self.state = STATE_DIALOGUE

    def _get_water_memory_core_rect(self) -> pygame.Rect | None:
        if not self.world:
            return None
        chamber_rects = getattr(self.world, "water_chamber_rects", [])
        if not chamber_rects:
            return None
        min_top = min(rect.top for rect in chamber_rects)
        top_edge_rects = [rect for rect in chamber_rects if rect.top == min_top]
        return sorted(top_edge_rects, key=lambda rect: rect.centerx)[len(top_edge_rects) // 2]

    def _try_investigate_water_memory_core(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_mirror_chamber":
            return False
        if not self._get_story_flag("water_trial_path_hint_received", False):
            return False

        core_rect = self._get_water_memory_core_rect()
        if core_rect and self.player.rect.colliderect(core_rect.inflate(TILE // 2, TILE // 2)):
            if self._get_story_flag("water_trial_started", False):
                self._add_message(
                    "記憶の核は静かだ。だが、洞窟のどこかで三つの揺らぎが主人公を待っている。",
                    C_GRAY,
                )
            elif self._get_story_flag("water_trial_ready", False):
                self._start_water_trial_start_event()
            elif self._get_story_flag("water_memory_core_found", False):
                self._add_message(
                    "記憶の核は静かに揺れている。まだ、何かを見届ける者を待っているようだ。",
                    C_GRAY,
                )
            else:
                self._start_water_memory_core_event()
            return True

        return False

    def _start_water_memory_core_event(self) -> None:
        self._set_story_flag("water_memory_core_found", True)
        self._set_story_flag("water_memory_core_resonated", True)
        self._set_story_flag("water_trial_ready", True)
        self.current_dialogue_id = "water_memory_core_investigation"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("water_memory_core_investigation")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_memory_core_investigation")
        self.state = STATE_DIALOGUE

    def _start_water_trial_start_event(self) -> None:
        self._set_story_flag("water_trial_started", True)
        self._set_story_flag("water_trial_memory_shift_seen", True)
        self._set_story_flag("water_trial_echoes_active", True)
        self.current_dialogue_id = "water_trial_start"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("water_trial_start")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_trial_start")
        self.state = STATE_DIALOGUE

    def _get_water_drop_target(self) -> tuple[str, pygame.Rect, str] | None:
        if not self.world:
            return None

        if self.current_zone_id == "water_cave":
            rects = getattr(self.world, "water_mirror_rects", [])
            return ("cave", rects[-1], "water_drop_cave_found") if rects else None
        if self.current_zone_id == "water_cave_depths":
            rects = getattr(self.world, "water_light_rects", [])
            return ("depths", rects[-1], "water_drop_depths_found") if rects else None
        if self.current_zone_id == "water_cave_source":
            rects = getattr(self.world, "water_source_rects", [])
            return ("source", rects[-1], "water_drop_source_found") if rects else None
        return None

    def _try_collect_water_drop(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("water_seal_drops_hint_received", False):
            return False

        target = self._get_water_drop_target()
        if not target:
            return False

        location, target_rect, flag_name = target
        if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag(flag_name, False):
            self._add_message(self._get_water_drop_repeat_message(location), C_GRAY)
        else:
            self._start_water_drop_event(location, flag_name)
        return True

    def _get_water_drop_repeat_message(self, location: str) -> str:
        if location == "cave":
            return "水面は静かだ。ここにあった雫は、すでに封印の反応へ溶け込んでいる。"
        if location == "depths":
            return "淡い光だけが残っている。雫が抱えていた想いは、もう主人公の中にある。"
        return "水源は静かに流れている。雫の祈りは、封印へ届く準備をしているようだ。"

    def _start_water_drop_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "water_drop_cave_found",
                "water_drop_depths_found",
                "water_drop_source_found",
            )
        )
        if completed:
            self._set_story_flag("water_drops_collected", True)

        dialogue_id = f"water_drop_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("water_drops_collected")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _get_water_trial_echo_target(self) -> tuple[str, pygame.Rect, str] | None:
        if not self.world:
            return None
        water_rects = getattr(self.world, "water_rects", [])
        if not water_rects:
            return None

        if self.current_zone_id == "water_cave":
            return ("cave", water_rects[0], "water_trial_echo_cave_seen")
        if self.current_zone_id == "water_cave_depths":
            return ("depths", water_rects[-1], "water_trial_echo_depths_seen")
        if self.current_zone_id == "water_cave_source":
            return ("source", water_rects[-1], "water_trial_echo_source_seen")
        return None

    def _try_investigate_water_trial_echo(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("water_trial_echoes_active", False):
            return False

        target = self._get_water_trial_echo_target()
        if not target:
            return False

        location, target_rect, flag_name = target
        if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag(flag_name, False):
            self._add_message(self._get_water_trial_echo_repeat_message(location), C_GRAY)
        else:
            self._start_water_trial_echo_event(location, flag_name)
        return True

    def _get_water_trial_echo_repeat_message(self, location: str) -> str:
        if location == "cave":
            return "水面の影は消えた。だが、誰かを見送るような気配が残っている。"
        if location == "depths":
            return "伸ばされた手はもう見えない。それでも、水面には届かなかった想いが残っている。"
        return "水源の中心は静かだ。祈りのような揺らぎだけが、そこに留まり続けている。"

    def _start_water_trial_echo_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "water_trial_echo_cave_seen",
                "water_trial_echo_depths_seen",
                "water_trial_echo_source_seen",
            )
        )
        if completed:
            self._set_story_flag("water_trial_echoes_complete", True)

        dialogue_id = f"water_trial_echo_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("water_trial_echoes_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _get_water_memory_trace_target(self) -> tuple[str, pygame.Rect, str] | None:
        if not self.world:
            return None

        if self.current_zone_id == "water_cave":
            rects = getattr(self.world, "water_mirror_rects", [])
            return ("cave", rects[0], "water_memory_trace_cave_investigated") if rects else None
        if self.current_zone_id == "water_cave_depths":
            rects = getattr(self.world, "water_light_rects", [])
            return ("depths", rects[0], "water_memory_trace_depths_investigated") if rects else None
        if self.current_zone_id == "water_cave_source":
            rects = getattr(self.world, "water_source_rects", [])
            return ("source", rects[0], "water_memory_trace_source_investigated") if rects else None
        return None

    def _try_investigate_water_memory_trace(self) -> bool:
        if not self.world or not self.player:
            return False
        if not self._get_story_flag("water_spirit_request_received", False):
            return False

        target = self._get_water_memory_trace_target()
        if not target:
            return False

        location, target_rect, flag_name = target
        if not self.player.rect.colliderect(target_rect.inflate(TILE, TILE)):
            return False

        if self._get_story_flag(flag_name, False):
            self._add_message(self._get_water_memory_trace_repeat_message(location), C_GRAY)
        else:
            self._start_water_memory_trace_event(location, flag_name)
        return True

    def _get_water_memory_trace_repeat_message(self, location: str) -> str:
        if location == "cave":
            return "水面の揺らぎは静まっている。だが、そこにはまだ誰かの想いが残っている。"
        if location == "depths":
            return "淡い光は消えない。記憶の欠片は、まだ洞窟の奥を見つめているようだ。"
        return "水は中心へ集まり続けている。記憶の残滓もまた、同じ場所へ引かれている。"

    def _start_water_memory_trace_event(self, location: str, flag_name: str) -> None:
        self._set_story_flag(flag_name, True)
        completed = all(
            self._get_story_flag(name, False)
            for name in (
                "water_memory_trace_cave_investigated",
                "water_memory_trace_depths_investigated",
                "water_memory_trace_source_investigated",
            )
        )
        if completed:
            self._set_story_flag("water_memory_traces_complete", True)

        dialogue_id = f"water_memory_trace_{location}"
        lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(dialogue_id)
        ]
        if completed:
            lines.extend(
                line.replace("{support_system_name}", self.get_support_system_display_name())
                for line in get_dialogue_lines("water_memory_traces_complete")
            )

        self.current_dialogue_id = dialogue_id
        self.dialogue_lines = lines
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen(dialogue_id)
        self.state = STATE_DIALOGUE

    def _try_investigate_water_reflection_shadow(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_reflection":
            return False
        if not self._get_story_flag("water_reflection_corridor_entered", False):
            return False

        for shadow_rect in getattr(self.world, "water_shadow_rects", []):
            if self.player.rect.colliderect(shadow_rect.inflate(TILE, TILE)):
                if self._get_story_flag("water_reflection_shadow_investigated", False):
                    self._add_message(
                        "水面の揺らぎは消えた。だが、誰かの気配だけが回廊の奥へ続いている。",
                        C_GRAY,
                    )
                else:
                    self._start_water_reflection_shadow_event()
                return True

        return False

    def _start_water_reflection_shadow_event(self) -> None:
        self._set_story_flag("water_reflection_shadow_investigated", True)
        self._set_story_flag("water_reflection_memory_seen", True)
        self._set_story_flag("water_reflection_route_hint_received", True)
        self.current_dialogue_id = "water_reflection_shadow_investigation"
        self.dialogue_lines = get_dialogue_lines("water_reflection_shadow_investigation")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_reflection_shadow_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_water_depths_light(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_depths":
            return False
        if not self._get_story_flag("water_next_path_hint_received", False):
            return False

        for light_rect in getattr(self.world, "water_light_rects", []):
            if self.player.rect.colliderect(light_rect.inflate(TILE, TILE)):
                if self._get_story_flag("water_depths_light_investigated", False):
                    self._add_message(
                        "淡い光は、洞窟のさらに奥へ向かうように静かに揺れている。",
                        C_GRAY,
                    )
                else:
                    self._start_water_depths_light_event()
                return True

        return False

    def _start_water_depths_light_event(self) -> None:
        self._set_story_flag("water_depths_light_investigated", True)
        self._set_story_flag("water_depths_light_reacted", True)
        self._set_story_flag("water_depths_path_opened", True)
        self.current_dialogue_id = "water_depths_light_investigation"
        self.dialogue_lines = get_dialogue_lines("water_depths_light_investigation")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_depths_light_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_water_source(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave_source":
            return False
        if not self._get_story_flag("water_source_entered", False):
            return False

        for source_rect in getattr(self.world, "water_source_rects", []):
            if self.player.rect.colliderect(source_rect.inflate(TILE, TILE)):
                if self._get_story_flag("water_source_investigated", False):
                    self._add_message(
                        "淡い波紋は消えない。水源の反応は、どこか別の場所へ続いているようだ。",
                        C_GRAY,
                    )
                else:
                    self._start_water_source_investigation_event()
                return True

        return False

    def _start_water_source_investigation_event(self) -> None:
        self._set_story_flag("water_source_investigated", True)
        self._set_story_flag("water_source_resonance_seen", True)
        self._set_story_flag("water_route_hint_received", True)
        self.current_dialogue_id = "water_source_investigation"
        self.dialogue_lines = get_dialogue_lines("water_source_investigation")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_source_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_water_mirror(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "water_cave":
            return False
        if not self._get_story_flag("water_cave_entered", False):
            return False

        for mirror_rect in getattr(self.world, "water_mirror_rects", []):
            if self.player.rect.colliderect(mirror_rect.inflate(TILE, TILE)):
                if self._get_story_flag("water_mirror_investigated", False):
                    self._add_message(
                        "水面は静かだ。だが、奥へ向かう流れだけが不自然に揺れている。",
                        C_GRAY,
                    )
                else:
                    self._start_water_mirror_investigation_event()
                return True

        return False

    def _start_water_mirror_investigation_event(self) -> None:
        self._set_story_flag("water_mirror_investigated", True)
        self._set_story_flag("water_reflection_seen", True)
        self.current_dialogue_id = "water_mirror_investigation"
        self.dialogue_lines = get_dialogue_lines("water_mirror_investigation")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("water_mirror_investigation")
        self.state = STATE_DIALOGUE

    def _try_investigate_wind_gorge_anomaly(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "wind_gorge":
            return False
        if not self._get_story_flag("wind_gorge_entered", False):
            return False

        for wind_rect in getattr(self.world, "wind_rects", []):
            if self.player.rect.colliderect(wind_rect.inflate(TILE, TILE)):
                if self._get_story_flag("wind_gorge_anomaly_seen", False):
                    self._add_message("風はなおも光を守るように渦巻いている", C_GRAY)
                else:
                    self._start_wind_gorge_anomaly_event()
                return True

        return False

    def _start_wind_gorge_anomaly_event(self) -> None:
        self._set_story_flag("wind_gorge_anomaly_seen", True)
        self._set_story_flag("wind_gorge_wind_resonance_seen", True)
        self.current_dialogue_id = "wind_gorge_anomaly"
        self.dialogue_lines = get_dialogue_lines("wind_gorge_anomaly")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("wind_gorge_anomaly")
        self.state = STATE_DIALOGUE

    def _try_analyze_wind_flow(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "wind_gorge":
            return False
        if not self._get_story_flag("wind_gorge_anomaly_seen", False):
            return False

        for observation_rect in getattr(self.world, "wind_observation_rects", []):
            if self.player.rect.colliderect(observation_rect.inflate(TILE, TILE)):
                if self._get_story_flag("wind_flow_analyzed", False):
                    self._add_message("風の流れは、一定の間隔で弱まっている", C_GRAY)
                else:
                    self._start_wind_flow_analysis_event()
                return True

        return False

    def _start_wind_flow_analysis_event(self) -> None:
        self._set_story_flag("wind_flow_analyzed", True)
        self._set_story_flag("wind_center_route_found", True)
        self.current_dialogue_id = "wind_flow_analysis"
        self.dialogue_lines = get_dialogue_lines("wind_flow_analysis")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("wind_flow_analysis")
        self.state = STATE_DIALOGUE

    def _try_start_sylph_encounter(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "wind_gorge":
            return False
        if not self._get_story_flag("wind_center_route_found", False):
            return False

        for wind_rect in getattr(self.world, "wind_rects", []):
            if self.player.rect.colliderect(wind_rect.inflate(TILE, TILE)):
                if self._get_story_flag("sylph_trial_cleared", False):
                    self._add_message("シルフ：風はもう、お前を拒まない。中心へ行け。", C_GRAY)
                elif self._get_story_flag("sylph_trial_started", False):
                    self._add_message("シルフ：焦る者は、風に置いていかれる。", C_GRAY)
                elif self._get_story_flag("sylph_trial_available", False):
                    self._start_sylph_trial_start_event()
                else:
                    self._start_sylph_first_encounter_event()
                return True

        return False

    def _start_sylph_first_encounter_event(self) -> None:
        self._set_story_flag("sylph_encountered", True)
        self._set_story_flag("sylph_trial_available", True)
        self.current_dialogue_id = "sylph_first_encounter"
        self.dialogue_lines = get_dialogue_lines("sylph_first_encounter")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("sylph_first_encounter")
        self.state = STATE_DIALOGUE

    def _start_sylph_trial_start_event(self) -> None:
        self._set_story_flag("sylph_trial_started", True)
        self._set_story_value("sylph_trial_step", 0)
        self.current_dialogue_id = "sylph_trial_start"
        self.dialogue_lines = get_dialogue_lines("sylph_trial_start")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("sylph_trial_start")
        self.state = STATE_DIALOGUE

    def _try_progress_sylph_trial(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "wind_gorge":
            return False
        if not self._get_story_flag("sylph_trial_started", False):
            return False
        if self._get_story_flag("sylph_trial_cleared", False):
            return False

        marker_rects = getattr(self.world, "wind_trial_marker_rects", [])
        for index, marker_rect in enumerate(marker_rects):
            if self.player.rect.colliderect(marker_rect.inflate(TILE, TILE)):
                expected_index = self._get_story_int("sylph_trial_step", 0)
                if index == expected_index:
                    self._advance_sylph_trial_step(expected_index)
                else:
                    self._add_message("風はここではない方向へ流れている。", C_GRAY)
                return True

        return False

    def _advance_sylph_trial_step(self, current_step: int) -> None:
        next_step = current_step + 1
        self._set_story_value("sylph_trial_step", next_step)
        if next_step >= 3:
            self._start_sylph_trial_complete_event()
            return

        self._add_message(f"風の標が応えた。流れは次の標へ続いている。({next_step}/3)", C_GRAY)

    def _start_sylph_trial_complete_event(self) -> None:
        self._set_story_flag("sylph_trial_cleared", True)
        self._set_story_flag("sylph_trial_complete_seen", True)
        self.current_dialogue_id = "sylph_trial_complete"
        self.dialogue_lines = get_dialogue_lines("sylph_trial_complete")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("sylph_trial_complete")
        self.state = STATE_DIALOGUE

    def _try_collect_wind_fragment(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "wind_gorge":
            return False
        if not self._get_story_flag("sylph_trial_cleared", False):
            return False

        for wind_rect in getattr(self.world, "wind_rects", []):
            if self.player.rect.colliderect(wind_rect.inflate(TILE, TILE)):
                if self._get_story_flag("wind_fragment_2_obtained", False):
                    self._add_message("シルフ：欠片はすでに、お前の手の中にある。帰るべき場所があるのだろう。", C_GRAY)
                else:
                    self._start_sylph_grants_wind_fragment_event()
                return True

        return False

    def _start_sylph_grants_wind_fragment_event(self) -> None:
        self._set_story_flag("wind_fragment_2_seen", True)
        self._set_story_flag("wind_fragment_2_obtained", True)
        self._set_story_flag("sylph_fragment_granted", True)
        self.current_dialogue_id = "sylph_grants_wind_fragment"
        self.dialogue_lines = get_dialogue_lines("sylph_grants_wind_fragment")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("sylph_grants_wind_fragment")
        self.state = STATE_DIALOGUE

    def _try_investigate_shrine_unknown_resonance(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "shrine_inner":
            return False
        if not self._get_story_flag("shrine_center_return_hint_received", False):
            return False

        for altar_rect in getattr(self.world, "altar_rects", []):
            if self.player.rect.colliderect(altar_rect.inflate(TILE, TILE)):
                if self._get_story_flag("shrine_unknown_resonance_investigated", False):
                    self._add_message(
                        "四つの光は、色のない揺らぎを押し退けてはいない。互いを支えるように、祭壇の中心で静かに共鳴している。",
                        C_GRAY,
                    )
                else:
                    self._start_shrine_unknown_resonance_event()
                return True

        return False

    def _try_investigate_shrine_new_anomaly(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "shrine_inner":
            return False
        if not self._get_story_flag("shrine_boundary_resonance_hint_received", False):
            return False

        for altar_rect in getattr(self.world, "altar_rects", []):
            if self.player.rect.colliderect(altar_rect.inflate(TILE, TILE)):
                if self._get_story_flag("shrine_new_anomaly_investigated", False):
                    self._add_message(
                        "祭壇の中心から伸びる細い反応は、遠いどこかへ静かに続いている。",
                        C_GRAY,
                    )
                else:
                    self._start_shrine_new_anomaly_event()
                return True

        return False

    def _start_shrine_new_anomaly_event(self) -> None:
        self._set_story_flag("shrine_new_anomaly_investigated", True)
        self._set_story_flag("shrine_distant_resonance_seen", True)
        self._set_story_flag("next_region_path_hint_received", True)
        self.current_dialogue_id = "shrine_new_anomaly"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("shrine_new_anomaly")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_new_anomaly")
        self.state = STATE_DIALOGUE

    def _start_shrine_unknown_resonance_event(self) -> None:
        self._set_story_flag("shrine_unknown_resonance_investigated", True)
        self._set_story_flag("shrine_center_light_shadow_seen", True)
        self._set_story_flag("shrine_unknown_resonance_stabilized", True)
        self.current_dialogue_id = "shrine_unknown_resonance"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("shrine_unknown_resonance")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_unknown_resonance")
        self.state = STATE_DIALOGUE

    def _try_offer_earth_fragment_to_altar(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "shrine_inner":
            return False
        if not self._get_story_flag("earth_fragment_obtained", False):
            return False

        for altar_rect in getattr(self.world, "altar_rects", []):
            if self.player.rect.colliderect(altar_rect.inflate(TILE, TILE)):
                if self._get_story_flag("earth_fragment_offered", False):
                    self._add_message(
                        "四つの属性の光が、祭壇の中で静かに共鳴している。祠はまだ、次の答えを待っているようだ。",
                        C_GRAY,
                    )
                else:
                    self._start_shrine_earth_fragment_offering_event()
                return True

        return False

    def _start_shrine_earth_fragment_offering_event(self) -> None:
        self._set_story_flag("earth_fragment_offered", True)
        self._set_story_flag("shrine_fifth_seal_reacted", True)
        self._set_story_flag("shrine_earth_resonance_seen", True)
        self._set_story_flag("earth_fragment_reported", True)
        self.current_dialogue_id = "shrine_earth_fragment_offering"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("shrine_earth_fragment_offering")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_earth_fragment_offering")
        self.state = STATE_DIALOGUE

    def _try_offer_fire_fragment_to_altar(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "shrine_inner":
            return False
        if not self._get_story_flag("fire_fragment_obtained", False):
            return False

        for altar_rect in getattr(self.world, "altar_rects", []):
            if self.player.rect.colliderect(altar_rect.inflate(TILE, TILE)):
                if self._get_story_flag("fire_fragment_offered", False):
                    self._add_message(
                        "四つの欠片は、異なる光と熱を保ちながら共鳴している。祭壇は、まだ次の流れを待っているようだ。",
                        C_GRAY,
                    )
                else:
                    self._start_shrine_fire_fragment_offering_event()
                return True

        return False

    def _start_shrine_fire_fragment_offering_event(self) -> None:
        self._set_story_flag("fire_fragment_offered", True)
        self._set_story_flag("shrine_fourth_seal_reacted", True)
        self._set_story_flag("shrine_fire_resonance_seen", True)
        self._set_story_flag("fire_fragment_reported", True)
        self.current_dialogue_id = "shrine_fire_fragment_offering"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("shrine_fire_fragment_offering")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_fire_fragment_offering")
        self.state = STATE_DIALOGUE

    def _try_offer_water_fragment_to_altar(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "shrine_inner":
            return False
        if not self._get_story_flag("water_fragment_obtained", False):
            return False

        for altar_rect in getattr(self.world, "altar_rects", []):
            if self.player.rect.colliderect(altar_rect.inflate(TILE, TILE)):
                if self._get_story_flag("water_fragment_offered", False):
                    self._add_message(
                        "三つの欠片は静かに共鳴している。祭壇は、まだ次の流れを待っているようだ。",
                        C_GRAY,
                    )
                else:
                    self._start_shrine_water_fragment_offering_event()
                return True

        return False

    def _start_shrine_water_fragment_offering_event(self) -> None:
        self._set_story_flag("water_fragment_offered", True)
        self._set_story_flag("shrine_third_seal_reacted", True)
        self._set_story_flag("shrine_water_resonance_seen", True)
        self._set_story_flag("water_fragment_reported", True)
        self.current_dialogue_id = "shrine_water_fragment_offering"
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines("shrine_water_fragment_offering")
        ]
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_water_fragment_offering")
        self.state = STATE_DIALOGUE

    def _try_offer_wind_fragment_to_altar(self) -> bool:
        if not self.world or not self.player:
            return False
        if self.current_zone_id != "shrine_inner":
            return False
        if not self._get_story_flag("wind_fragment_2_obtained", False):
            return False

        for altar_rect in getattr(self.world, "altar_rects", []):
            if self.player.rect.colliderect(altar_rect.inflate(TILE, TILE)):
                if self._get_story_flag("wind_fragment_2_offered", False):
                    self._add_message("祭壇には、二つの欠片の光が静かに巡っている。", C_GRAY)
                else:
                    self._start_shrine_wind_fragment_offering_event()
                return True

        return False

    def _start_shrine_wind_fragment_offering_event(self) -> None:
        self._set_story_flag("wind_fragment_2_offered", True)
        self._set_story_flag("shrine_second_seal_reacted", True)
        self._set_story_flag("shrine_altar_changed", True)
        self.current_dialogue_id = "shrine_wind_fragment_offering"
        self.dialogue_lines = get_dialogue_lines("shrine_wind_fragment_offering")
        self.dialogue_speaker = self.get_support_system_display_name()
        self.dialogue_index = 0
        self.talking_npc = None
        self._mark_story_event_seen("shrine_wind_fragment_offering")
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
        self.dialogue_lines = [
            line.replace("{support_system_name}", self.get_support_system_display_name())
            for line in get_dialogue_lines(d_id)
        ]
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
        if finished_dialogue_id == "elder_after_second_seal_reaction":
            self._set_story_flag("shrine_second_reaction_reported", True)
            self._set_story_flag("water_hint_received", True)
        if finished_dialogue_id == "elder_after_water_source_reaction":
            self._set_story_flag("water_source_reported", True)
            self._set_story_flag("water_next_path_hint_received", True)
        if finished_dialogue_id == "elder_after_third_seal_reaction":
            self._set_story_flag("water_fragment_reported_to_elder", True)
            self._set_story_flag("fire_region_hint_received", True)
            self._set_story_flag("fire_path_unlocked_hint_received", True)
        if finished_dialogue_id == "elder_after_fourth_seal_reaction":
            self._set_story_flag("fire_fragment_reported_to_elder", True)
            self._set_story_flag("earth_region_hint_received", True)
            self._set_story_flag("earth_path_unlocked_hint_received", True)
        if finished_dialogue_id == "elder_after_fifth_seal_reaction":
            self._set_story_flag("earth_fragment_reported_to_elder", True)
            self._set_story_flag("four_element_resonance_hint_received", True)
            self._set_story_flag("next_anomaly_hint_received", True)
        if finished_dialogue_id == "elder_after_pale_choice_report":
            self._set_story_flag("pale_choice_reported_to_elder", True)
            self._set_story_flag("shrine_unknown_resonance_hint_received", True)
            self._set_story_flag("shrine_center_return_hint_received", True)
        if finished_dialogue_id == "elder_after_boundary_center_report":
            self._set_story_flag("boundary_center_reported_to_elder", True)
            self._set_story_flag("boundary_next_change_hint_received", True)
            self._set_story_flag("boundary_center_return_hint_received", True)
        if finished_dialogue_id == "elder_after_boundary_dual_traces_report":
            self._set_story_flag("boundary_dual_traces_reported_to_elder", True)
            self._set_story_flag("boundary_integration_hint_received", True)
            self._set_story_flag("boundary_center_final_return_hint_received", True)
        if finished_dialogue_id == "elder_after_boundary_silent_balance_report":
            self._set_story_flag("boundary_silent_balance_reported_to_elder", True)
            self._set_story_flag("shrine_boundary_resonance_hint_received", True)
            self._set_story_flag("next_region_anomaly_hint_received", True)
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
        elif self.state == STATE_PALE_CHOICE:
            self._draw_play(surface)
            self._draw_pale_choice_window(surface)
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
            shrine_second_seal_reacted=self._get_story_flag("shrine_second_seal_reacted", False),
            wind_gorge_anomaly_seen=self._get_story_flag("wind_gorge_anomaly_seen", False),
            wind_center_route_found=self._get_story_flag("wind_center_route_found", False),
            sylph_encountered=self._get_story_flag("sylph_encountered", False),
            sylph_trial_started=self._get_story_flag("sylph_trial_started", False),
            sylph_trial_step=self._get_story_int("sylph_trial_step", 0),
            sylph_trial_cleared=self._get_story_flag("sylph_trial_cleared", False),
            wind_fragment_2_obtained=self._get_story_flag("wind_fragment_2_obtained", False),
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

    def _draw_pale_choice_window(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((WINDOW_W, GAME_AREA_H), pygame.SRCALPHA)
        overlay.fill(make_rgba(0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        win_w, win_h = 680, 360
        wx = WINDOW_W // 2 - win_w // 2
        wy = GAME_AREA_H // 2 - win_h // 2
        pygame.draw.rect(surface, C_WINDOW_BG, (wx, wy, win_w, win_h), border_radius=6)
        pygame.draw.rect(
            surface, C_WINDOW_BORDER, (wx, wy, win_w, win_h), 2, border_radius=6
        )
        pygame.draw.line(
            surface, C_GOLD, (wx + 1, wy + 42), (wx + win_w - 1, wy + 42), 1
        )

        title = self.font_md.render("色のない光の中心", True, C_GOLD)
        surface.blit(title, (wx + win_w // 2 - title.get_width() // 2, wy + 12))

        text_y = wy + 58
        for line in self.pale_choice_prompt_lines[:4]:
            for wrapped in self._wrap_dialogue(line, self.font_sm, win_w - 56):
                txt = self.font_sm.render(wrapped, True, C_WHITE)
                surface.blit(txt, (wx + 28, text_y))
                text_y += 22

        opt_y = wy + 178
        for i, (_choice_id, label) in enumerate(self.pale_choice_options):
            is_sel = i == self.pale_choice_cursor
            row = pygame.Rect(wx + 28, opt_y + i * 42 - 5, win_w - 56, 34)
            if is_sel:
                pygame.draw.rect(surface, (35, 28, 55), row, border_radius=4)
                pygame.draw.rect(surface, C_GOLD, row, 1, border_radius=4)
                cursor = self.font_md.render(">", True, C_GOLD)
                surface.blit(cursor, (wx + 44, opt_y + i * 42 - 2))

            color = C_GOLD if is_sel else C_WHITE
            text = self.font_md.render(label, True, color)
            surface.blit(text, (wx + 74, opt_y + i * 42 - 1))

        hint = self.font_sm.render(
            "↑↓ / ←→ 選択   Z/Enter 決定   Esc/X 保留", True, C_DARK_GRAY
        )
        surface.blit(hint, (wx + win_w // 2 - hint.get_width() // 2, wy + win_h - 28))

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
