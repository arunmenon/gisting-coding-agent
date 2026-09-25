"""Scene 8: The instrument was wrong.

One idea: an external review found our load generator capped connections
at 100. Lifting the cap showed more than 100 sessions resident and
withdrew our explanation. It also lowered throughput in three of four
cells. At the two overload points tested, the compressed prompt held up
better. Cause still open. About 30 seconds.

Persistent object: the client gate / connection-count line, transformed
across the scene (gate opens with the first beat, dots appear above it,
then the line gives way to paired bars). A colour legend (petrol = full
prompt, plum = Steno) is introduced with the bars, since that is where the
two colours first appear side by side in this scene.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Dot,
    FadeIn,
    FadeOut,
    Line,
    Rectangle,
    VGroup,
    Write,
)
from manim_voiceover import VoiceoverScene

from style import (
    BACKGROUND,
    CAVEAT,
    FULL_PROMPT,
    SAFE_BOTTOM,
    STENO,
    TEXT_COLOR,
    body_text,
    number_label,
    title_text,
)
from voice import SayService


class Scene8(VoiceoverScene):
    def construct(self):
        self.camera.background_color = BACKGROUND
        self.set_speech_service(SayService(voice="Samantha", rate_wpm=175))

        heading = title_text("The instrument was wrong", font_size=38)
        heading.to_edge(UP, buff=0.4)

        # --- Beat 8.1: gate at 100, opens with the first beat (no dead air) ---
        gate_line = Line(LEFT * 3.7, RIGHT * 3.7, color=TEXT_COLOR, stroke_width=4)
        gate_line.shift(UP * 0.9)
        gate_mark = Rectangle(width=0.16, height=0.8, color=CAVEAT, fill_color=CAVEAT, fill_opacity=0.85)
        gate_mark.move_to(gate_line.get_center())
        gate_label = number_label("cap: 100", color=CAVEAT, font_size=32)
        gate_label.next_to(gate_mark, UP, buff=0.3)

        old_claim = body_text("old explanation: residency ceiling reached", font_size=30)
        old_claim.next_to(gate_line, DOWN, buff=0.7)

        with self.voiceover(
            text=(
                "A correction. Our own load generator capped connections "
                "at one hundred, in both arms. Our earlier explanation "
                "used that number. It is withdrawn."
            )
        ) as tracker:
            self.play(
                Write(heading),
                FadeIn(gate_line),
                FadeIn(gate_mark),
                Write(gate_label),
                run_time=1.3,
            )
            self.play(Write(old_claim), run_time=1.3)
            withdrawn = body_text("explanation withdrawn", font_size=32, color=CAVEAT)
            withdrawn.move_to(old_claim.get_center())
            self.play(FadeOut(old_claim), FadeIn(withdrawn), run_time=1.2)
            self.wait(max(0.1, tracker.duration - 3.8))

        cap_qualifier = body_text("maximum sampled counts, not hardware ceilings", font_size=30)
        cap_qualifier.next_to(withdrawn, DOWN, buff=0.45)

        # --- Beat 8.2: cap lifted, dots above the line, "more than 100" ---
        dots = [Dot(radius=0.09, color=STENO) for _ in range(11)]
        for i, dot in enumerate(dots):
            dot.move_to(gate_line.get_center() + RIGHT * (i - 5) * 0.62 + UP * (0.45 + 0.06 * (i % 3)))
        more_than_label = number_label("more than 100 (123-137 sampled)", color=STENO, font_size=30)
        more_than_label.next_to(gate_line, UP, buff=1.1)

        with self.voiceover(
            text=(
                "Cap lifted, sampled counts showed more than one hundred "
                "sessions resident: one hundred twenty three to one "
                "hundred thirty seven."
            )
        ) as tracker:
            self.play(FadeOut(gate_label), FadeIn(*dots), run_time=1.4)
            self.play(Write(more_than_label), Write(cap_qualifier), run_time=1.5)
            self.wait(max(0.1, tracker.duration - 2.9))

        self.play(
            FadeOut(gate_line),
            FadeOut(gate_mark),
            FadeOut(withdrawn),
            FadeOut(more_than_label),
            *[FadeOut(d) for d in dots],
            FadeOut(cap_qualifier),
            run_time=0.8,
        )

        # --- Beat 8.3: legend, then two overload points as paired bars ---
        # Order within each pair is full prompt then Steno, matching the
        # narration order ("forty seven against eighty point seven").
        # Bars sit on a fixed baseline low enough to clear the legend above
        # and high enough that captions and the caveat both clear the
        # safe-area bottom margin (plan section 3).
        BAR_BASE_Y = 1.3
        BAR_MAX_HEIGHT = 1.7
        BAR_WIDTH = 0.8

        legend_petrol_swatch = Rectangle(
            width=0.45, height=0.32, color=FULL_PROMPT, fill_color=FULL_PROMPT, fill_opacity=0.85
        )
        legend_petrol_label = body_text("full prompt", font_size=28)
        legend_petrol_label.next_to(legend_petrol_swatch, RIGHT, buff=0.2)
        legend_petrol = VGroup(legend_petrol_swatch, legend_petrol_label)

        legend_steno_swatch = Rectangle(
            width=0.45, height=0.32, color=STENO, fill_color=STENO, fill_opacity=0.85
        )
        legend_steno_label = body_text("Steno", font_size=28)
        legend_steno_label.next_to(legend_steno_swatch, RIGHT, buff=0.2)
        legend_steno = VGroup(legend_steno_swatch, legend_steno_label)

        legend = VGroup(legend_petrol, legend_steno).arrange(RIGHT, buff=0.8)
        legend.move_to([0, 2.3, 0])

        def paired_bars(label_text, full_val, steno_val, max_val, x_shift):
            full_bar = Rectangle(
                width=BAR_WIDTH,
                height=max(0.15, BAR_MAX_HEIGHT * full_val / max_val),
                color=FULL_PROMPT,
                fill_color=FULL_PROMPT,
                fill_opacity=0.85,
            )
            steno_bar = Rectangle(
                width=BAR_WIDTH,
                height=max(0.15, BAR_MAX_HEIGHT * steno_val / max_val),
                color=STENO,
                fill_color=STENO,
                fill_opacity=0.85,
            )
            bars = VGroup(full_bar, steno_bar)
            bars.arrange(RIGHT, buff=0.4, aligned_edge=DOWN)
            bars.move_to([x_shift, BAR_BASE_Y, 0])
            bars.align_to([x_shift, BAR_BASE_Y - BAR_MAX_HEIGHT, 0], DOWN)

            full_num = number_label(f"{full_val}", color=FULL_PROMPT, font_size=30)
            full_num.next_to(full_bar, UP, buff=0.15)
            steno_num = number_label(f"{steno_val}", color=STENO, font_size=30)
            steno_num.next_to(steno_bar, UP, buff=0.15)

            caption = body_text(label_text, font_size=30)
            caption.next_to(bars, DOWN, buff=0.3)

            return VGroup(bars, full_num, steno_num, caption)

        group_128 = paired_bars("128 offered", 47.0, 80.7, 90, -3.0)
        group_256 = paired_bars("256 offered", 46.3, 56.7, 90, 3.0)

        caveat_line1 = body_text(
            "one run per condition; lifting the cap lowered throughput in three of four cells",
            font_size=28,
            color=CAVEAT,
        )
        caveat_line2 = body_text("cause still open", font_size=28, color=CAVEAT)
        caveat = VGroup(caveat_line1, caveat_line2).arrange(DOWN, buff=0.15)
        # Position explicitly (rather than to_edge) so it clears SAFE_BOTTOM,
        # which already reserves caption space at the very bottom of frame.
        caveat.move_to([0, SAFE_BOTTOM + caveat.height / 2 + 0.15, 0])

        with self.voiceover(
            text=(
                "Lifting the cap lowered throughput in three of four "
                "cells. At two tested overload points, one run each, the "
                "compressed prompt held up better: forty seven against "
                "eighty point seven at one hundred twenty eight offered, "
                "forty six point three against fifty six point seven at "
                "two hundred fifty six. Cause still open."
            )
        ) as tracker:
            self.play(FadeIn(legend), run_time=0.8)
            self.play(FadeIn(group_128), run_time=1.3)
            self.play(FadeIn(group_256), run_time=1.3)
            self.play(Write(caveat), run_time=1.5)
            self.wait(max(0.1, tracker.duration - 4.9))
