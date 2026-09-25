"""Step 0 smoke test: text, a number, an arrow, one voiceover block, and an
.srt caption file. Nothing else in this project starts until this passes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from manim import LEFT, RIGHT, UP, Create, FadeIn, Write
from manim_voiceover import VoiceoverScene

from style import (
    BACKGROUND,
    FULL_PROMPT,
    TEXT_COLOR,
    arrow,
    body_text,
    number_label,
    title_text,
)
from voice import SayService


class SmokeScene(VoiceoverScene):
    def construct(self):
        self.camera.background_color = BACKGROUND
        self.set_speech_service(SayService(voice="Samantha", rate_wpm=175))

        heading = title_text("Steno smoke test", font_size=40)
        heading.to_edge(UP, buff=0.6)

        value = number_label("17.5k", color=FULL_PROMPT, font_size=56)
        value.shift(LEFT * 2)

        caption = body_text("fixed preamble, about 17.5k tokens", font_size=28)
        caption.next_to(value, direction=UP, buff=0.4)

        the_arrow = arrow(LEFT * 0.3, RIGHT * 2.3, color=TEXT_COLOR)
        the_arrow.move_to(value.get_center())
        the_arrow.next_to(value, RIGHT, buff=0.5)

        elapsed = 0.0
        with self.voiceover(
            text=(
                "This is a ten second smoke test for the Steno explainer "
                "pipeline: text, a number, an arrow, one voiceover block, "
                "and a caption file, all rendered locally."
            )
        ) as tracker:
            run_time_1 = min(1.5, tracker.duration * 0.2)
            self.play(Write(heading), run_time=run_time_1)
            run_time_2 = min(1.5, tracker.duration * 0.2)
            self.play(FadeIn(value), Write(caption), run_time=run_time_2)
            run_time_3 = max(0.5, tracker.duration * 0.2)
            self.play(Create(the_arrow), run_time=run_time_3)
            elapsed = run_time_1 + run_time_2 + run_time_3
            remaining_in_beat = max(0.0, tracker.duration - elapsed)
            if remaining_in_beat > 0:
                self.wait(remaining_in_beat)
                elapsed += remaining_in_beat

        # Hold the final frame so the smoke scene reaches its 10-second
        # budget even though the narration itself is shorter.
        final_hold = max(0.1, 10.0 - elapsed)
        self.wait(final_hold)
