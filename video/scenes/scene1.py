"""Scene 1: The re-read.

One idea: the agent re-sends the same fixed preamble on every call; prefix
caching already absorbs part of that cost. Steno is named here as the
shrinking of that block, not the block itself.

Persistent object: the fixed block (petrol), transformed across the scene
(reappears per turn, then labelled with its token range, then visibly
shrunk to about one eighth its width and recoloured plum to become Steno).
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
    Circle,
    Create,
    FadeIn,
    FadeOut,
    Line,
    Rectangle,
    Square,
    VGroup,
    Write,
)
from manim_voiceover import VoiceoverScene

from style import (
    BACKGROUND,
    CAVEAT,
    FULL_PROMPT,
    PASSING,
    SAFE_BOTTOM,
    STENO,
    TEXT_COLOR,
    body_text,
    fit_width,
    number_label,
    title_text,
)
from voice import SayService


def make_fixed_block(label_text: str = "fixed block", width: float = 3.0, height: float = 1.25):
    block = Rectangle(width=width, height=height, color=FULL_PROMPT, fill_color=FULL_PROMPT, fill_opacity=0.25)
    label = body_text(label_text, font_size=30, color=TEXT_COLOR)
    fit_width(label, width - 0.3)
    label.move_to(block.get_center())
    return VGroup(block, label)


class Scene1(VoiceoverScene):
    def construct(self):
        self.camera.background_color = BACKGROUND
        self.set_speech_service(SayService(voice="Samantha", rate_wpm=175))

        heading = title_text("The re-read", font_size=40)
        heading.to_edge(UP, buff=0.4)
        self.play(Write(heading), run_time=1.0)

        # --- Beat 1.1: agent and model icons, scaled up to use more of the frame ---
        agent_icon = Square(side_length=1.7, color=TEXT_COLOR)
        agent_label = body_text("agent", font_size=30)
        agent_label.next_to(agent_icon, DOWN, buff=0.3)
        agent_group = VGroup(agent_icon, agent_label).move_to(LEFT * 5.2 + UP * 0.5)

        model_icon = Circle(radius=1.05, color=STENO)
        model_label = body_text("Qwen model\n(self-hosted)", font_size=30)
        model_label.next_to(model_icon, DOWN, buff=0.3)
        model_group = VGroup(model_icon, model_label).move_to(RIGHT * 5.2 + UP * 0.5)

        connector = Line(agent_icon.get_right(), model_icon.get_left(), color=TEXT_COLOR)

        caption_pair = body_text("one pair, studied closely", font_size=32)
        caption_pair.next_to(connector, UP, buff=0.4)

        with self.voiceover(
            text=(
                "Here is a coding agent, Claude Code, talking to a model we "
                "host ourselves, a Qwen model. We looked closely at one pair "
                "like this."
            )
        ) as tracker:
            self.play(FadeIn(agent_group), FadeIn(model_group), run_time=1.2)
            self.play(Create(connector), Write(caption_pair), run_time=1.5)
            self.wait(max(0.1, tracker.duration - 2.7))

        # Clear the intro icons before the turns take over the frame, so
        # nothing from beat 1.1 can collide with the turn boxes or labels.
        self.play(
            FadeOut(agent_group),
            FadeOut(model_group),
            FadeOut(connector),
            FadeOut(caption_pair),
            run_time=0.6,
        )

        # --- Beat 1.2: three real turns, plus a separate repeat-marker slot ---
        # Turn slots occupy the left two thirds of the safe width; the
        # repeat marker gets its own slot on the right so it never overlaps
        # a turn box or (since they are already gone) the model icon.
        turn_row_y = 1.6
        turn_xs = [-4.6, -1.2, 2.2]
        fixed_blocks = []
        question_blocks = []
        turns_group = VGroup()

        with self.voiceover(
            text=(
                "Turn one. The agent sends a long fixed block before it "
                "ever asks its real question. Turn two, the same block "
                "again. Turn three, again."
            )
        ) as tracker:
            per_turn_time = max(0.6, tracker.duration / 3.2)
            for i, x in enumerate(turn_xs):
                fixed = make_fixed_block("fixed block")
                fixed.move_to([x, turn_row_y, 0])
                question = Rectangle(width=2.2, height=1.0, color=TEXT_COLOR)
                q_label = body_text(f"turn {i + 1}", font_size=30)
                fit_width(q_label, 1.9)
                q_label.move_to(question.get_center())
                question_group = VGroup(question, q_label)
                question_group.next_to(fixed, DOWN, buff=0.4)

                fixed_blocks.append(fixed)
                question_blocks.append(question_group)
                turns_group.add(fixed, question_group)

                self.play(FadeIn(fixed), run_time=per_turn_time * 0.5)
                self.play(FadeIn(question_group), run_time=per_turn_time * 0.5)
            self.wait(max(0.1, tracker.duration - per_turn_time * 3))

        # --- Beat 1.3: repeat marker (its own slot) + fixed block token range ---
        repeat_marker = body_text("repeats\neach turn", font_size=30, color=CAVEAT)
        repeat_marker.move_to([5.1, turn_row_y, 0])

        stat = number_label("17.5k-21k tokens", color=FULL_PROMPT, font_size=36)
        stat_qualifier = body_text(
            "across the configurations we measured, over 90% tool schemas",
            font_size=30,
        )
        stat_group = VGroup(stat, stat_qualifier).arrange(DOWN, buff=0.22)
        stat_group.move_to([0, -1.3, 0])

        with self.voiceover(
            text=(
                "Across the configurations we measured, that fixed block "
                "runs about seventeen and a half thousand to twenty one "
                "thousand tokens, and over ninety percent of it is tool "
                "schemas, not conversation."
            )
        ) as tracker:
            self.play(Write(repeat_marker), run_time=1.0)
            self.play(FadeIn(stat_group), run_time=1.5)
            self.wait(max(0.1, tracker.duration - 2.5))

        # --- Beat 1.4: caching, then Steno as the shrinking, not the block ---
        cache_note = body_text("prefix caching absorbs part of this cost", font_size=30, color=PASSING)
        cache_note.move_to([0, max(SAFE_BOTTOM + 0.4, -2.2), 0])

        with self.voiceover(
            text=(
                "Some of that cost is already absorbed by prefix caching. "
                "But resending it, and re-processing it, still adds up. "
                "Steno is how we shrink that block."
            )
        ) as tracker:
            self.play(FadeIn(cache_note), run_time=1.3)

            shrink_anims = []
            glows = []
            for fb in fixed_blocks:
                rect, label = fb[0], fb[1]
                center = rect.get_center()
                shrink_width = rect.width / 8
                glow = Rectangle(
                    width=shrink_width * 3,
                    height=rect.height * 1.3,
                    stroke_opacity=0,
                    fill_color=STENO,
                    fill_opacity=0.20,
                )
                glow.move_to(center)
                glows.append(glow)
                self.add(glow)
                self.bring_to_back(glow)
                shrink_anims.append(FadeOut(label))
                shrink_anims.append(
                    rect.animate.stretch_to_fit_width(shrink_width)
                    .set_stroke(STENO)
                    .set_fill(STENO, opacity=0.9)
                )
                shrink_anims.append(FadeIn(glow))

            self.play(*shrink_anims, run_time=1.6)

            steno_label = body_text("Steno", font_size=36, color=STENO)
            steno_label.next_to(fixed_blocks[1], UP, buff=0.3)
            self.play(Write(steno_label), run_time=1.0)
            self.wait(max(0.1, tracker.duration - 3.9))
