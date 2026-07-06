"""
Japanese-capable font selection for pygame text rendering.

The game renders Japanese in HUD, dialogue, objectives, help text, and game-over
screens.  pygame's default font often lacks Japanese glyphs, especially on macOS,
so this module resolves an installed CJK font path first and uses it everywhere.
"""

from __future__ import annotations

from pathlib import Path

import pygame


FONT_CANDIDATES: tuple[str, ...] = (
    # Windows
    r"C:\Windows\Fonts\meiryo.ttc",
    r"C:\Windows\Fonts\msgothic.ttc",
    r"C:\Windows\Fonts\YuGothM.ttc",
    r"C:\Windows\Fonts\YuGothR.ttc",
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
)


def find_jp_font_path() -> str | None:
    """Return the first existing Japanese-capable font file path."""
    missing: list[str] = []
    failed: list[str] = []
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                pygame.font.Font(candidate, 16)
            except Exception as exc:
                failed.append(f"{candidate} ({exc})")
                continue
            else:
                print(f"[FontManager] Japanese font selected: {candidate}")
                return candidate
        missing.append(candidate)

    print("[FontManager] Japanese font file was not found.")
    print("[FontManager] Tried candidates:")
    for candidate in missing:
        print(f"[FontManager]   - {candidate}")
    for candidate in failed:
        print(f"[FontManager]   - load failed: {candidate}")
    print("[FontManager] Falling back to pygame default font; Japanese may render as boxes.")
    return None


class FontManager:
    """Create and share fonts used across the game."""

    def __init__(self):
        self.jp_font_path = find_jp_font_path()
        self.is_jp = self.jp_font_path is not None

        self.lg = self._make(34, bold=True)
        self.md = self._make(20, bold=True)
        self.sm = self._make(14, bold=False)
        self.sm_bold = self._make(14, bold=True)

    def _make(self, size: int, bold: bool) -> pygame.font.Font:
        if self.jp_font_path:
            try:
                font = pygame.font.Font(self.jp_font_path, size)
                font.set_bold(bold)
                return font
            except Exception as exc:
                print(
                    f"[FontManager] Failed to load Japanese font: {self.jp_font_path} ({exc})"
                )

        font = pygame.font.Font(None, size)
        font.set_bold(bold)
        return font
