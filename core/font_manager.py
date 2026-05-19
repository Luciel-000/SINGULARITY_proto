"""
============================================================
  core/font_manager.py  ── 日本語フォント管理  [0.3 新規]

  担当:
    - 日本語が表示できるフォントを自動で探して返す
    - 見つからない場合は英数字フォントにフォールバック
    - ゲーム全体で共有する Font オブジェクトを一元管理

  優先フォント順（日本語対応）:
    1. meiryo（メイリオ）
    2. yugothic（游ゴシック）
    3. msgothic（ＭＳ ゴシック）
    4. ipagothic（IPAゴシック / Linux 環境）
    5. notosanscjkjp（Noto Sans CJK JP / Linux 環境）
    6. monospace（最終フォールバック：日本語は□になるが動作は維持）

  使い方:
    from core.font_manager import FontManager
    fm = FontManager()               # 初期化（自動でフォント検索）
    txt = fm.md.render("攻撃", True, (255,255,255))  # 日本語OK

  フォント種類:
    fm.lg  : 大（タイトル・勝利など）
    fm.md  : 中（コマンド・名前など）
    fm.sm  : 小（ログ・ステータスなど）
============================================================
"""

import pygame


# ── 日本語対応フォントの優先リスト ──────────────────────
# pygame.font.SysFont はフォント名を小文字・スペースなしで検索する
JP_FONT_PRIORITY = [
    "meiryo",           # Windows: メイリオ（最も一般的）
    "meiryoui",         # Windows: Meiryo UI
    "yugothic",         # Windows: 游ゴシック
    "yugothicui",       # Windows: 游ゴシック UI
    "msgothic",         # Windows: ＭＳ ゴシック
    "mspgothic",        # Windows: ＭＳ Ｐゴシック
    "ipagothic",        # Linux/Mac: IPA ゴシック
    "ipapgothic",       # Linux: IPA P ゴシック
    "notosanscjkjp",    # Linux: Noto Sans CJK JP
    "hiragino kaku gothic pro",  # Mac: ヒラギノ角ゴ
    "hiraginokakugothicpro",     # Mac（スペースなし）
]


def find_jp_font() -> str | None:
    """
    システムにインストールされた日本語フォントを探して名前を返す。
    見つからなければ None を返す。
    """
    # システムにあるフォント名をすべて取得（小文字に変換して比較）
    available = {f.lower() for f in pygame.font.get_fonts()}

    for candidate in JP_FONT_PRIORITY:
        # フォント名のスペースを除いたものも試す
        if candidate in available or candidate.replace(" ", "") in available:
            return candidate

    return None  # 見つからなかった


class FontManager:
    """
    ゲーム全体で使うフォントをまとめて管理するクラス。

    属性:
        jp_font_name : 実際に使われているフォント名（デバッグ用）
        is_jp        : 日本語フォントが使えているか（True / False）
        lg           : 大フォント（サイズ 34）
        md           : 中フォント（サイズ 20）
        sm           : 小フォント（サイズ 14）
        sm_bold      : 小フォント（太字）
    """

    def __init__(self):
        # 日本語フォントを探す
        jp_name = find_jp_font()

        if jp_name:
            self.jp_font_name = jp_name
            self.is_jp        = True
            print(f"[FontManager] 日本語フォント使用: {jp_name}")
        else:
            self.jp_font_name = "monospace"
            self.is_jp        = False
            print("[FontManager] 日本語フォントが見つかりません。英数字フォントを使用します。")
            print("             日本語テキストが □ になる場合は README を参照してください。")

        # ── フォントオブジェクトを生成
        # ★ サイズを変えたいときはここの数値を調整してください
        self.lg     = self._make(jp_name, 34, bold=True)   # 大：タイトル・勝利
        self.md     = self._make(jp_name, 20, bold=True)   # 中：コマンド・名前
        self.sm     = self._make(jp_name, 14, bold=False)  # 小：ログ・ステータス
        self.sm_bold = self._make(jp_name, 14, bold=True)  # 小太字：HP数値など

    def _make(self, name: str | None, size: int, bold: bool) -> pygame.font.Font:
        """
        フォントオブジェクトを生成する内部メソッド。
        name が None の場合は monospace にフォールバック。
        """
        font_name = name if name else "monospace"
        try:
            return pygame.font.SysFont(font_name, size, bold=bold)
        except Exception:
            # 万一エラーが出ても続行できるようにフォールバック
            return pygame.font.SysFont("monospace", size, bold=bold)
