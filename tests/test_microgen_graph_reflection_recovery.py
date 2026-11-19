"""Offline negative tests for genuine multi-panel graph-reflection cue recovery."""
import unittest

from microgen_timed_cue_planner import (
    _lexical_match, graph_slope_reflection_source_block,
    question_reflection_source_block, salient, QUESTION_REFLECTION_ROLE
)


LABELS = [
    "Concept Check: Matching Graphs",
    "Question: Match each velocity-time (vx-t) graph (a, b, c) "
    "with the corresponding acceleration-time (ax-t) graph (d, e, f).",
    "Graph (a): Horizontal line with constant non-zero velocity.",
    "Graph (b): Straight line with a positive slope.",
    "Graph (c): Straight line with a negative slope.",
]
SPOKEN = "Consider what each slope implies about acceleration."


def blocks(labels=LABELS):
    return [([10.0, 25.0+i*30, 320.0, 40.0+i*30],
             label, salient(label)) for i,label in enumerate(labels)]


class GraphReflectionRecovery(unittest.TestCase):
    def test_exact_printed_graph_quiz_and_nonassertive_final_cue(self):
        source=blocks()
        self.assertEqual(graph_slope_reflection_source_block(
            SPOKEN, 5, 5, source), 1)
        self.assertEqual(question_reflection_source_block(
            SPOKEN, 5, 5, source), 1)
        cues, unresolved=_lexical_match(
            13, ["The graph is a matching concept check.",
                 "Graph panel a is horizontal.", SPOKEN],
            source, allow_unanchored=True)
        self.assertEqual(unresolved, [])
        self.assertEqual(
            cues[-1]["question_context_role"], QUESTION_REFLECTION_ROLE)
        self.assertEqual(cues[-1]["pdf_text"], LABELS[1])

    def test_nonfinal_and_numeric_claim_never_reclassified(self):
        src=blocks()
        self.assertIsNone(question_reflection_source_block(
            SPOKEN, 4, 5, src))
        self.assertIsNone(question_reflection_source_block(
            "Consider what each slope implies about acceleration equals 3.",
            5, 5, src))
        self.assertIsNone(question_reflection_source_block(
            "Graph b definitely indicates positive acceleration.", 5, 5, src))

    def test_absent_or_mislabeled_graphs_do_not_create_fake_evidence(self):
        for labels in (
            LABELS[:-1],
            LABELS[:4]+[LABELS[3]],
            LABELS[:3]+[LABELS[4],LABELS[3]],
            LABELS[:1]+["Question: Match each color with another color."]+LABELS[2:],
            LABELS[1:],
            LABELS[:2]+["Graph (a): unrelated.",
                         "Graph (b): unrelated.","Graph (c): unrelated."],
        ):
            with self.subTest(labels=labels):
                self.assertIsNone(question_reflection_source_block(
                    SPOKEN, 5, 5, blocks(labels)))

    def test_unrelated_prompt_and_source_drift_abstain(self):
        src=blocks()
        for text in (
            "Consider what each slope implies about taxes.",
            "Consider how each line proves acceleration is negative.",
            "Reflect on whether the force is always constant.",
            "Consider what each slope implies about acceleration? ",
        ):
            with self.subTest(text=text):
                self.assertIsNone(question_reflection_source_block(
                    text, 5, 5, src))


if __name__ == "__main__":
    unittest.main()
