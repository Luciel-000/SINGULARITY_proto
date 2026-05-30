"""
============================================================
  core/utils.py  ── 共通ユーティリティ関数  [0.3.1 新規]

  作成目的:
    pygame の RGBA/alpha 値は「0〜255 の整数」でなければならない。
    float や範囲外の値を渡すと ValueError が発生する。
    このファイルに変換関数を集約し、全ファイルから呼ぶことで
    alpha エラーを一箇所で完全に防ぐ。

  ── 確認済みの危険パターン ──────────────────────────────
    HIGH:  alpha - i * 30   → alpha=0 のとき i>=1 で負数になる
    HIGH:  float 混入       → sin/cos の計算結果をそのまま使うと float
    MED:   255 * life / max → life が max を超えると 255 超になる
    MED:   (*color, alpha)  → color の各要素が 0-255 外なら即エラー

  ── 使い方 ──────────────────────────────────────────────
    from .utils import safe_alpha, safe_color, make_rgba, lerp_alpha

    # 単体の alpha 値を安全にする
    a = safe_alpha(255 * some_float)     # float → int → clamp

    # RGBA タプルをまとめて安全にする
    color = make_rgba(201, 168, 76, alpha_value)

    # 既存カラー定数 + alpha を安全に合成する
    color = make_rgba(*C_GOLD, alpha_value)

    # life/max から 0.0-1.0 の比率を安全に計算する
    a = lerp_alpha(life, max_life, max_alpha=200)
============================================================
"""


def safe_alpha(value) -> int:
    """
    alpha 値を「0〜255 の整数」に安全に変換する。

    以下をまとめて処理:
      - float → int への変換（小数点以下は切り捨て）
      - 負数  → 0 にクランプ
      - 255超 → 255 にクランプ

    引数:
        value : int / float / その他の数値

    戻り値:
        int   0〜255 に収まった整数

    使用例:
        safe_alpha(300)       → 255
        safe_alpha(-10)       → 0
        safe_alpha(127.9)     → 127
        safe_alpha(0.3 * 200) → 60   (float の乗算結果も安全)
    """
    try:
        return max(0, min(255, int(value)))
    except (TypeError, ValueError):
        # 万一 None や変換不能な値が来ても 0 を返して続行
        return 0


def safe_color(r, g, b) -> tuple[int, int, int]:
    """
    RGB 3値をそれぞれ 0〜255 の整数に安全に変換する。

    引数:
        r, g, b : 各チャンネルの値（int / float）

    戻り値:
        (int, int, int) : 安全な RGB タプル

    使用例:
        safe_color(201, 168, 76)       → (201, 168, 76)
        safe_color(300, -10, 128.5)    → (255,   0, 128)
    """
    return (safe_alpha(r), safe_alpha(g), safe_alpha(b))


def make_rgba(r, g, b, a) -> tuple[int, int, int, int]:
    """
    RGBA 4値をすべて 0〜255 の整数に安全に変換する。

    引数:
        r, g, b, a : 各チャンネルの値（int / float）

    戻り値:
        (int, int, int, int) : 安全な RGBA タプル

    使用例:
        # C_GOLD = (201, 168, 76) と alpha を組み合わせる
        make_rgba(*C_GOLD, 160)             → (201, 168, 76, 160)
        make_rgba(*C_GOLD, 300)             → (201, 168, 76, 255)  ← クランプ
        make_rgba(*C_GOLD, -10)             → (201, 168, 76,   0)  ← クランプ
        make_rgba(*C_GOLD, 0.5 * 200)       → (201, 168, 76, 100)  ← float 対応

        # Surface.fill() に渡すとき
        surface.fill(make_rgba(0, 0, 0, alpha))

        # draw.circle の color 引数に渡すとき
        pygame.draw.circle(s, make_rgba(*self.color, alpha), center, r)
    """
    return (safe_alpha(r), safe_alpha(g), safe_alpha(b), safe_alpha(a))


def lerp_alpha(current: float, maximum: float,
               max_alpha: int = 255,
               min_alpha: int = 0) -> int:
    """
    「現在値 / 最大値」の比率から alpha 値を計算する。

    ライフタイム（残り寿命）やタイマーのフェードに使う。
    ゼロ除算・負数・255超をすべて防ぐ。

    引数:
        current   : 現在の値（life, timer など）
        maximum   : 最大値（life の初期値など）
        max_alpha : alpha の最大値（デフォルト 255）
        min_alpha : alpha の最小値（デフォルト 0）

    戻り値:
        int : 0〜255 に収まった alpha 値

    使用例:
        # life=40/50 のとき alpha を 0〜255 でフェード
        a = lerp_alpha(ft["life"], 50)             → 204

        # 最大 200 でフェード
        a = lerp_alpha(death_timer, 30, max_alpha=200)

        # 逆フェード（増えていくもの）
        a = lerp_alpha(ANIM_RESULT - result_timer, ANIM_RESULT, max_alpha=160)
    """
    if maximum <= 0:
        return safe_alpha(min_alpha)
    ratio = max(0.0, min(1.0, current / maximum))  # 0.0〜1.0 にクランプ
    value = min_alpha + (max_alpha - min_alpha) * ratio
    return safe_alpha(value)
