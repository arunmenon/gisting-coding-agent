"""Shared visual language for the Steno explainer video.

Palette, verified fonts, safe-area constants and Text-based helpers for
numbers and axis ticks. No LaTeX is used anywhere in this project: this
machine has no LaTeX installed, so every numeric or symbolic label must be
built from plain Text mobjects, never Tex, MathTex or Brace.
"""

from __future__ import annotations

import manimpango
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Arrow,
    Line,
    Mobject,
    Text,
    VGroup,
    config,
)

# ---------------------------------------------------------------------------
# Palette (matches the deck; see plan section 3)
# ---------------------------------------------------------------------------

BACKGROUND = "#0e1417"
FULL_PROMPT = "#3fb0c6"   # petrol: the full fixed prompt
STENO = "#c39be0"         # plum: Steno / the shorthand
PER_SESSION = "#e08a4c"   # copper: per-session raw values
PASSING = "#57c08a"       # green: passing / success
CAVEAT = "#e3b24c"        # amber: caveats and residual risk
TEXT_COLOR = "#f2f2f2"    # near-white body text on the dark ground
DIM_OPACITY = 0.30        # "dim and reveal": everything not in focus


# ---------------------------------------------------------------------------
# Fonts, verified against manimpango.list_fonts() with declared fallbacks
# ---------------------------------------------------------------------------

_AVAILABLE_FONTS = set(manimpango.list_fonts())


def _verified_font(preferred: str, fallback: str) -> str:
    """Return preferred font if installed, else the declared fallback.

    Both preferred and fallback are checked against manimpango's local font
    list per the no-LaTeX rules in plan section 3. If neither is present,
    Manim's own default system font is used (still Text, never Tex).
    """
    if preferred in _AVAILABLE_FONTS:
        return preferred
    if fallback in _AVAILABLE_FONTS:
        return fallback
    return "Helvetica Neue" if "Helvetica Neue" in _AVAILABLE_FONTS else preferred


TITLE_FONT = _verified_font("Georgia", "Helvetica Neue")
NUMBER_FONT = _verified_font("Menlo", "Courier New")
BODY_FONT = _verified_font("Helvetica Neue", "Arial")


# ---------------------------------------------------------------------------
# Safe area: 5 percent margins on every side, plus caption space at bottom
# ---------------------------------------------------------------------------

FRAME_WIDTH = config.frame_width
FRAME_HEIGHT = config.frame_height

SAFE_MARGIN_RATIO = 0.05
SAFE_MARGIN_X = FRAME_WIDTH * SAFE_MARGIN_RATIO
SAFE_MARGIN_Y = FRAME_HEIGHT * SAFE_MARGIN_RATIO

# Extra headroom reserved at the bottom for burned-in / external captions.
CAPTION_HEIGHT_RATIO = 0.12
CAPTION_HEIGHT = FRAME_HEIGHT * CAPTION_HEIGHT_RATIO

SAFE_LEFT = -FRAME_WIDTH / 2 + SAFE_MARGIN_X
SAFE_RIGHT = FRAME_WIDTH / 2 - SAFE_MARGIN_X
SAFE_TOP = FRAME_HEIGHT / 2 - SAFE_MARGIN_Y
SAFE_BOTTOM = -FRAME_HEIGHT / 2 + SAFE_MARGIN_Y + CAPTION_HEIGHT

SAFE_WIDTH = SAFE_RIGHT - SAFE_LEFT
SAFE_HEIGHT = SAFE_TOP - SAFE_BOTTOM

# Minimum on-screen text size at 1080p, per plan section 3.
MIN_FONT_SIZE = 28


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def fit_width(mobject: Mobject, max_width: float = SAFE_WIDTH) -> Mobject:
    """Scale mobject down (never up) so it fits within max_width. In place."""
    if mobject.width > max_width:
        mobject.scale_to_fit_width(max_width)
    return mobject


def dim_others(focus: Mobject, others: list[Mobject], opacity: float = DIM_OPACITY):
    """Return the animations that dim every mobject in others except focus.

    Caller is expected to `self.play(*dim_others(focus, others))`. This
    implements the "dim and reveal" rule: when a part is discussed,
    everything else drops to 30 percent opacity.
    """
    from manim import ApplyMethod

    anims = []
    for mob in others:
        if mob is focus:
            continue
        anims.append(ApplyMethod(mob.set_opacity, opacity))
    return anims


def reset_opacity(mobjects: list[Mobject]):
    """Return animations restoring full opacity to a list of mobjects."""
    from manim import ApplyMethod

    return [ApplyMethod(mob.set_opacity, 1.0) for mob in mobjects]


# ---------------------------------------------------------------------------
# Text-based number and axis helpers (no LaTeX, ever)
# ---------------------------------------------------------------------------

def number_label(
    value: str,
    color: str = TEXT_COLOR,
    font_size: int = 40,
    font: str | None = None,
) -> Text:
    """A plain-Text stand-in for DecimalNumber/Integer.

    DecimalNumber and Integer default to a LaTeX-rendered mobject class.
    Per the no-LaTeX rules, this project never instantiates them without
    mob_class=Text; in practice it is simpler and safer to render numeric
    labels directly as Text, which is what this helper does. `value` is
    passed in as an already-formatted string (e.g. "0.72", "8:1", "24.3k").
    """
    return Text(value, font=font or NUMBER_FONT, font_size=font_size, color=color)


def axis_line(
    start,
    end,
    color: str = TEXT_COLOR,
    stroke_width: float = 3,
) -> Line:
    """A plain line for an axis or number line, with include_numbers=False
    semantics: ticks and labels are added separately as Text via tick_label.
    """
    return Line(start, end, color=color, stroke_width=stroke_width)


def tick_label(
    value: str,
    position,
    font_size: int = MIN_FONT_SIZE,
    color: str = TEXT_COLOR,
    font: str | None = None,
) -> Text:
    """A hand-placed axis tick label, replacing Axes(include_numbers=True)."""
    label = Text(value, font=font or NUMBER_FONT, font_size=font_size, color=color)
    label.move_to(position)
    return label


def arrow(start, end, color: str = TEXT_COLOR, stroke_width: float = 4) -> Arrow:
    """A simple arrow primitive (used for icons: never emoji, per section 3)."""
    return Arrow(start, end, color=color, stroke_width=stroke_width, buff=0.0)


def title_text(text: str, font_size: int = 48, color: str = TEXT_COLOR) -> Text:
    return Text(text, font=TITLE_FONT, font_size=font_size, color=color)


def body_text(text: str, font_size: int = MIN_FONT_SIZE, color: str = TEXT_COLOR) -> Text:
    return Text(text, font=BODY_FONT, font_size=font_size, color=color)


__all__ = [
    "BACKGROUND",
    "FULL_PROMPT",
    "STENO",
    "PER_SESSION",
    "PASSING",
    "CAVEAT",
    "TEXT_COLOR",
    "DIM_OPACITY",
    "TITLE_FONT",
    "NUMBER_FONT",
    "BODY_FONT",
    "SAFE_LEFT",
    "SAFE_RIGHT",
    "SAFE_TOP",
    "SAFE_BOTTOM",
    "SAFE_WIDTH",
    "SAFE_HEIGHT",
    "MIN_FONT_SIZE",
    "fit_width",
    "dim_others",
    "reset_opacity",
    "number_label",
    "axis_line",
    "tick_label",
    "arrow",
    "title_text",
    "body_text",
]
