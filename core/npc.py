"""
============================================================
  core/npc.py  ── NPC クラス  [0.7 新規]

  担当:
    - NPC の座標・名前・会話ID・描画・近接判定を管理
    - talked フラグで初回/2回目以降の会話を切り替える
    - スプライト画像がなくても図形で表示する

  ── 使い方 ──────────────────────────────────────────────
    from core.npc import NPC

    npc = NPC(
        x=200, y=300,
        name="謎の老人",
        dialogue_id="elder_first",
        repeat_dialogue_id="elder_repeat",
    )

    # 近接判定（プレイヤーが近いか）
    if npc.is_near(player.rect):
        print("話しかけられる！")

    # 現在の会話IDを取得（初回 or 2回目以降）
    did = npc.get_current_dialogue_id()

    # 話しかけたことを記録
    npc.mark_talked()

    # 描画（毎フレーム）
    npc.draw(surface, font_sm)

  ── 循環 import の回避 ──────────────────────────────────
    - constants.py のみ import（TILE / C_GOLD / C_WHITE / C_GRAY）
    - dialogue_data.py / game.py / player.py は import しない
============================================================
"""

import pygame
import math
from .constants import TILE, C_GOLD, C_WHITE, C_GRAY, C_DARK_GRAY

# NPC とプレイヤーが「近い」と判定する距離（ピクセル）
# TILE * 2 = 64px（約2マス以内）
NPC_TALK_RADIUS = TILE * 2


class NPC:
    """
    ゲーム内 NPC を表すクラス。

    引数:
        x, y              : 配置座標（ピクセル、左上基準）
        name              : 表示名（頭上ラベルとして使う）
        dialogue_id       : 初回に使う会話ID
        repeat_dialogue_id: 2回目以降に使う会話ID（省略時は初回と同じ）
        talk_radius       : 話しかけられる距離（px）。省略時は NPC_TALK_RADIUS
        color             : NPC の図形色（省略時はグレー）
    """

    def __init__(
        self,
        x: int,
        y: int,
        name: str,
        dialogue_id: str,
        repeat_dialogue_id: str | None = None,
        talk_radius: int = NPC_TALK_RADIUS,
        color: tuple = (160, 150, 170),   # デフォルト：グレー紫
    ):
        # 座標とサイズ（当たり判定・描画位置に使う）
        self.rect = pygame.Rect(x, y, TILE - 4, TILE - 4)

        # 表示名
        self.name = name

        # 会話ID
        # repeat_dialogue_id が None のとき、何度話しかけても dialogue_id を使う
        self.dialogue_id        = dialogue_id
        self.repeat_dialogue_id = repeat_dialogue_id if repeat_dialogue_id else dialogue_id

        # 話しかけた回数のフラグ
        # False = まだ話したことがない（初回）
        # True  = 1度以上話しかけた（2回目以降）
        self.talked = False

        # 話しかけられる距離
        self.talk_radius = talk_radius

        # 図形描画用の色
        self.color = color

        # 頭上のアニメーション用タイマー（浮遊する「！」マーク）
        self._anim_t: float = 0.0

    # ──────────────────────────────────────────────────────
    #  近接判定
    # ──────────────────────────────────────────────────────
    def is_near(self, player_rect: pygame.Rect) -> bool:
        """
        プレイヤーが話しかけられる距離以内にいるか判定する。

        2点間の直線距離（ピクセル）を計算して talk_radius と比較する。

        引数:
            player_rect : プレイヤーの pygame.Rect

        戻り値:
            True  : 近い（Zキーで話しかけられる）
            False : 遠い

        使用例:
            if npc.is_near(player.rect):
                # 話しかけメッセージを表示する
        """
        dx   = self.rect.centerx - player_rect.centerx
        dy   = self.rect.centery - player_rect.centery
        dist = math.hypot(dx, dy)
        return dist <= self.talk_radius

    # ──────────────────────────────────────────────────────
    #  会話ID の取得と状態更新
    # ──────────────────────────────────────────────────────
    def get_current_dialogue_id(self) -> str:
        """
        現在の状況に応じた会話IDを返す。

        talked=False（初回）→ dialogue_id を返す
        talked=True（2回目以降）→ repeat_dialogue_id を返す

        使用例:
            did = npc.get_current_dialogue_id()
            # game.py はこの ID で dialogue_data から会話内容を取得する
        """
        return self.dialogue_id if not self.talked else self.repeat_dialogue_id

    def mark_talked(self):
        """
        話しかけたことを記録する（talked=True にする）。
        game.py が会話ウィンドウを閉じたときに呼ぶ。

        使用例:
            npc.mark_talked()
            # → 次回は repeat_dialogue_id が使われる
        """
        self.talked = True

    def reset_talked(self):
        """
        talked フラグをリセットする（テストやデバッグ用）。
        通常のゲームプレイでは使わない。
        """
        self.talked = False

    # ──────────────────────────────────────────────────────
    #  更新（アニメーション）
    # ──────────────────────────────────────────────────────
    def update(self, player_rect: pygame.Rect):
        """
        毎フレーム呼ぶ。
        現在はアニメーションタイマーだけ更新する。
        将来的に NPC の移動・向きなどを追加できる。
        """
        self._anim_t += 0.06

    # ──────────────────────────────────────────────────────
    #  描画
    # ──────────────────────────────────────────────────────
    def draw(
        self,
        surface: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font | None = None,
        player_rect: pygame.Rect | None = None,
    ):
        """
        NPC を画面に描く（毎フレーム呼ぶ）。
        スプライト画像なしで図形のみで表示する。

        引数:
            surface     : 描画先サーフェス
            font_sm     : 小フォント（名前ラベルに使う）
            font_md     : 中フォント（「！」マークに使う、省略可）
            player_rect : プレイヤーの Rect（近いとき「！」を表示、省略可）
        """
        # ── 体（角丸の矩形）
        pygame.draw.rect(surface, self.color, self.rect, border_radius=6)

        # ── 頭（小さな円）
        head_cx = self.rect.centerx
        head_cy = self.rect.top + 8
        pygame.draw.circle(surface, self.color, (head_cx, head_cy), 7)

        # ── 目（固定：正面向き）
        eye_color = (30, 25, 45)
        pygame.draw.circle(surface, eye_color, (head_cx - 3, head_cy - 1), 2)
        pygame.draw.circle(surface, eye_color, (head_cx + 3, head_cy - 1), 2)

        # ── 名前ラベル（頭上）
        name_txt = font_sm.render(self.name, True, C_GRAY)
        surface.blit(
            name_txt,
            (self.rect.centerx - name_txt.get_width() // 2, self.rect.top - 18)
        )

        # ── 「！」マーク（プレイヤーが近いとき・sin 波で上下にゆれる）
        if player_rect is not None and self.is_near(player_rect):
            mark_font = font_md if font_md else font_sm
            bob_y     = int(math.sin(self._anim_t) * 3)   # ±3px の上下揺れ
            mark_txt  = mark_font.render("！", True, C_GOLD)
            mx = self.rect.centerx - mark_txt.get_width() // 2
            my = self.rect.top - 36 + bob_y
            surface.blit(mark_txt, (mx, my))
