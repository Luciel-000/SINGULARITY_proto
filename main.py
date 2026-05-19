"""
============================================================
  SINGULARITY - Chronicle of Origin -  Prototype 0.2
  main.py  ── ゲームの起動ファイル

  【実行方法】
    python main.py

  【必要ライブラリのインストール】
    pip install pygame

  【操作方法】
    移動  : WASD キー または 矢印キー
    攻撃  : Z キー
    終了  : ウィンドウの × ボタン
============================================================
"""

import sys
import pygame

# core フォルダの中にあるファイルを読み込む
from core.game      import Game
from core.constants import WINDOW_W, WINDOW_H, TITLE, FPS


def main():
    # ── Step 1: Pygame を初期化（必ず最初に呼ぶ）
    pygame.init()

    # ── Step 2: ウィンドウを作成
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(TITLE)

    # ── Step 3: FPS を制御するクロックを作成
    clock = pygame.time.Clock()

    # ── Step 4: ゲームオブジェクトを生成
    game = Game(screen)

    # ── Step 5: メインループ（ゲームが動き続ける心臓部）
    while True:

        # 5-a) イベント処理（キー入力・ウィンドウ閉じるなど）
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # × ボタンで終了
                pygame.quit()
                sys.exit()
            game.handle_event(event)

        # 5-b) ゲームの状態を更新（移動・戦闘計算など）
        game.update()

        # 5-c) 画面を描画
        screen.fill((0, 0, 0))      # まず黒で塗りつぶし
        game.draw(screen)           # ゲームの内容を描く
        pygame.display.flip()       # 描いた内容を画面に反映

        # 5-d) FPS を一定に保つ（60FPS）
        clock.tick(FPS)


# このファイルを直接実行したときだけ main() を呼ぶ
if __name__ == "__main__":
    main()
