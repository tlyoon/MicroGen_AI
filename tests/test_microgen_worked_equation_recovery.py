"""Adversarial offline replay of source-printed worked physics examples."""
from __future__ import annotations

import copy
import unittest
import fitz

from microgen_source_math_cue import (
    build_exact_source_math_cue, verified_source_math_row,
    source_math_quote_valid,
)


class Page:
    rect = fitz.Rect(0, 0, 362, 272)
    def __init__(self, rows):
        self.rows = rows
    def get_textbox(self, bbox):
        region = fitz.Rect(bbox)
        return "\n".join(
            label for box,label,_ in self.rows
            if region.x0-0.1 <= box[0] and region.y0-0.1 <= box[1]
            and region.x1+0.1 >= box[2] and region.y1+0.1 >= box[3])


def fixture(labels):
    rows = []
    for i, label in enumerate(labels):
        left = 90+i*7; top = 65+i*16
        rows.append(([left,top,285,top+12],label,set()))
    return rows,Page(rows)


class WorkedMathProof(unittest.TestCase):
    def make_cue(self, spoken, labels, *, row_id=1):
        blocks,page=fixture(labels)
        cue=build_exact_source_math_cue(9,row_id,spoken,blocks,page)
        return cue,blocks,page

    def test_printed_initial_velocity_and_time_problem(self):
        spoken=("In Example 2.7, a jet lands on an aircraft carrier with "
                "an initial velocity vee ex eye of approximately 63 "
                "meters per second and stops in 2.0 seconds.")
        labels=["Example 2.7: Carrier Landing (Part A)",
                "Problem: A jet lands on an aircraft carrier at vxi "
                "\u224863 m/s (140 mi/h) and stops (vxf = 0) "
                "in t = 2.0 s. What is its constant acceleration?"]
        cue,blocks,page=self.make_cue(spoken,labels)
        self.assertIsNotNone(cue)
        self.assertTrue(verified_source_math_row(cue,9,1,blocks,page))
        for wrong in [
            labels[1].replace("63 m/s","64 m/s"),
            labels[1].replace("vxf = 0","vxf = 1"),
            labels[1].replace("t = 2.0 s","t = 3.0 s")]:
            with self.subTest(wrong=wrong):
                self.assertIsNone(self.make_cue(spoken,[labels[0],wrong])[0])

    def test_fraction_requires_correct_initial_final_sign_and_denominator(self):
        spoken=("Calculating ay ex equals the fraction v ex final "
                "minus vee ex eye over t gives 0 minus 63 divided by 2.0,")
        labels=["ax = vxf \u2212vxi",
                "t\n= 0 \u221263 m/s",
                "2.0 s\n= \u221232 m/s2"]
        cue,blocks,page=self.make_cue(spoken,labels)
        self.assertIsNotNone(cue)
        self.assertTrue(verified_source_math_row(cue,9,1,blocks,page))
        for i,wrong in [(0,"ax = vxi \u2212vxf"),
                         (1,"t = 0 +63 m/s"),
                         (2,"3.0 s = \u221232 m/s2")]:
            altered=labels.copy();altered[i]=wrong
            self.assertIsNone(self.make_cue(spoken,altered)[0])

    def test_negative_acceleration_requires_same_signed_result_and_units(self):
        spoken="yielding minus 32 meters per second squared."
        label="2.0 s\n= \u221232 m/s2"
        cue,blocks,page=self.make_cue(spoken,[label])
        self.assertIsNotNone(cue)
        self.assertTrue(verified_source_math_row(cue,9,1,blocks,page))
        for source in ("2.0 s = 32 m/s2",
                       "2.0 s = \u221233 m/s2",
                       "2.0 s = \u221232 m/s"):
            self.assertIsNone(self.make_cue(spoken,[source])[0])

    def test_constant_speed_one_second_delay_requires_printed_position(self):
        spoken=("During that one-second delay, the car reaches "
                "position x B of 45.0 meters.")
        label="xB = (45.0 m/s)(1.00 s) = 45.0 m"
        cue,blocks,page=self.make_cue(spoken,[label])
        self.assertIsNotNone(cue)
        for changed in (
            "xB = (45.0 m/s)(2.00 s) = 45.0 m",
            "xB = (45.0 m/s)(1.00 s) = 46.0 m",
            "xB = (45.0 m/s)(1.00 s) = 45.0 s",
        ):
            self.assertIsNone(self.make_cue(spoken,[changed])[0])

    def test_pair_car_and_trooper_equations_includes_real_half_factor(self):
        spoken=("Therefore, the car's position is ex car equals ex bee "
                "plus vee ex car times t, and the trooper's position "
                "is ex trooper equals one-half ay sub ex times tee squared.")
        labels=["xcar = xB + vx,cart\nand\nxtrooper = 1","2axt2"]
        cue,blocks,page=self.make_cue(spoken,labels)
        self.assertIsNotNone(cue)
        self.assertTrue(verified_source_math_row(cue,9,1,blocks,page))
        for altered in (
            ["xcar = xB - vx,cart\nand\nxtrooper = 1","2axt2"],
            ["xcar = xB + vx,cart\nand\nxtrooper = 1","3axt2"],
            ["xcar = xB + vx,cart\nand\nxtrooper = 0","2axt2"],
        ):
            self.assertIsNone(self.make_cue(spoken,altered)[0])

    def test_literal_radical_is_required_between_printed_expressions(self):
        spoken=("When we substitute numerical values, the expression "
                "becomes 15.0 plus the square root of 255, "
                "which equals 31.0 seconds.")
        rows=[
            ([125.0,215.0,205.0,230.0],"3.00\n= 15.0 +",set()),
            ([208.0,204.0,217.0,215.0],"\u221a",set()),
            ([220.0,215.0,305.0,230.0],"255 = 31.0 s",set()),
        ]
        page=Page(rows)
        cue=build_exact_source_math_cue(8,2,spoken,rows,page)
        self.assertIsNotNone(cue)
        self.assertTrue(verified_source_math_row(cue,8,2,rows,page))
        for changed in (
            "255 = 30.0 s", "256 = 31.0 s",
            "255 = -31.0 s",
        ):
            alt=copy.deepcopy(rows);alt[2]=(alt[2][0],changed,set())
            self.assertIsNone(build_exact_source_math_cue(
                8,2,spoken,alt,Page(alt)))
        alt=copy.deepcopy(rows);alt[1]=(alt[1][0],"+",set())
        self.assertIsNone(build_exact_source_math_cue(
            8,2,spoken,alt,Page(alt)))

    def test_ambiguous_repeated_same_equation_abstains(self):
        spoken="yielding minus 32 meters per second squared."
        label="2.0 s = \u221232 m/s2"
        cue,_,_=self.make_cue(spoken,[label,label])
        self.assertIsNone(cue)

    def test_tampered_stored_geometry_and_spoken_are_rejected(self):
        spoken="yielding minus 32 meters per second squared."
        cue,blocks,page=self.make_cue(spoken,["2.0 s = \u221232 m/s2"])
        self.assertIsNotNone(cue)
        for field,new in (
            ("pdf_bbox",[1,1,4,4]),
            ("pdf_text","unrelated"),
            ("semantic_source_quote","unrelated"),
            ("source_math_evidence","unverified"),
            ("spoken_text","yielding minus 33 meters per second squared."),
        ):
            changed=copy.deepcopy(cue);changed[field]=new
            self.assertFalse(verified_source_math_row(changed,9,1,blocks,page))

    def test_short_quote_policy_does_not_accept_arbitrary_number(self):
        self.assertTrue(source_math_quote_valid("2axt2"))
        self.assertTrue(source_math_quote_valid("\u221a"))
        self.assertTrue(source_math_quote_valid("3.00\n= 15.0 +"))
        self.assertTrue(source_math_quote_valid("255 = 31.0 s"))
        for label in ("5", "2", "55 = 5", "x = 1", "3axt2", "ROOT"):
            self.assertFalse(source_math_quote_valid(label))


if __name__ == "__main__":
    unittest.main()

def test_explicit_x_component_voice_reuses_original_printed_source_with_zero_model():
    # Same source/variables, expressed as ordinary English rather than short
    # letter names. Only the unchanged printed-math proof can accept it.
    speech=(
        "In Example 2.7, a jet lands on an aircraft carrier with an "
        "initial velocity along the ex axis of approximately 63 meters "
        "per second and stops in 2.0 seconds."
    )
    labels=[
        "Example 2.7: Carrier Landing (Part A)",
        "Problem: A jet lands on an aircraft carrier at vxi "
        "\u224863 m/s (140 mi/h) and stops (vxf = 0) "
        "in t = 2.0 s. What is its constant acceleration?",
    ]
    blocks,page=fixture(labels)
    cue=build_exact_source_math_cue(15,1,speech,blocks,page)
    assert cue and verified_source_math_row(cue,15,1,blocks,page)
    for damaged in (
        speech.replace("ex axis","why axis"),
        speech.replace("initial velocity","final velocity"),
        speech.replace("63 meters","63.2 meters"),
    ):
        assert build_exact_source_math_cue(15,1,damaged,blocks,page) is None
    for damaged in (
        labels[1].replace("vxi","vyi"),
        labels[1].replace("63 m/s","64 m/s"),
        labels[1].replace("2.0 s","2.1 s"),
    ):
        assert build_exact_source_math_cue(
            15,1,speech,*fixture([labels[0],damaged])) is None


def test_explicit_x_component_fraction_still_requires_printed_signs_and_units():
    speech=(
        "Calculating the ex component of acceleration equals the fraction "
        "v ex final minus the initial ex component of velocity over t "
        "gives 0 minus 63 divided by 2.0,"
    )
    labels=[
        "ax = vxf \u2212vxi",
        "t\n= 0 \u221263 m/s",
        "2.0 s\n= \u221232 m/s2",
    ]
    blocks,page=fixture(labels)
    cue=build_exact_source_math_cue(15,3,speech,blocks,page)
    assert cue and verified_source_math_row(cue,15,3,blocks,page)
    for changed_speech in (
        speech.replace("ex component of acceleration","why component of acceleration"),
        speech.replace("initial ex component","final ex component"),
        speech.replace("minus the initial","plus the initial"),
        speech.replace("63 divided","63.2 divided"),
        speech.replace("2.0,","3.0,"),
    ):
        assert build_exact_source_math_cue(15,3,changed_speech,blocks,page) is None
    for i,bad in (
        (0, "ax = vxi \u2212vxf"),
        (1, "t = 0 +63 m/s"),
        (2, "2.0 s = \u22123.2 m/s2"),
    ):
        changed=labels.copy()
        changed[i]=bad
        assert build_exact_source_math_cue(
            15,3,speech,*fixture(changed)) is None

def test_displayed_fraction_rounding_must_be_internally_consistent():
    from microgen_worked_equation_recovery import (
        _printed_fraction_rounding_is_consistent,
    )
    assert _printed_fraction_rounding_is_consistent(
        "63","2.0","2.0 s = -32 m/s2"
    )
    assert _printed_fraction_rounding_is_consistent(
        "63","2.0","2.0 s = -31.5 m/s2"
    )
    for false_result in (
        "2.0 s = -3.2 m/s2",
        "2.0 s = -31 m/s2",
        "2.0 s = +32 m/s2",
        "2.0 s = -32 m/s",
        "2.0 s = -32 m/s3",
        "2.0 s = -32 m/s2 = -3.2 m/s2",
    ):
        assert not _printed_fraction_rounding_is_consistent(
            "63","2.0",false_result
        )
    assert not _printed_fraction_rounding_is_consistent(
        "63","0","2.0 s = -32 m/s2"
    )
