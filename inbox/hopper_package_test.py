"""The contract for the Hopper slice "the package": the dict a promotion hands to Warp.

Written by Jeremy and Claude before any build. The builder never sees this file and may not
write it. It is hash-pinned in the task. Three modules are under test. They are pure: they
never read a file, open a socket, start a process or look at the clock. They build a dict,
a list of names and a sentence. Writing the folder and posting it to Warp are not part of
this slice.

  package.py     build_package(promotion, idea, concepts, reference_images, names) -> dict
  filenames.py   numbered(prefix, paths) -> list of names like prefix-1.png, prefix-2.jpg
  confirm.py     confirm_text(concept_count) -> str

promotion         a dict with id, promoted_by, created (a timezone-aware datetime) and
                  concept_ids (the concepts the promoter ticked, in the order they ticked them)
idea              a dict with id, text, lane, source, source_ref, submitter, reviewer_notes
                  and scout_motive
concepts          the idea's concept rows, each a dict with id, model, prompt, seed and file_path
reference_images  the stored paths of the idea's reference images, in order
names             a dict from sign-in email to display name. A submitter or promoter with an @
                  in it is an email and must be in this dict. Anything else is a system name.
"""
import unittest
from datetime import datetime, timedelta, timezone

from confirm import confirm_text
from filenames import numbered
from package import build_package

NAMES = {"josh@threadpower.com": "Josh", "steph@threadpower.com": "Steph"}
CONCEPTS = [
    {"id": 4, "model": "flux2-klein-4b", "prompt": "a wolf, flat ink", "seed": 1234, "file_path": "2026-12-07/318/a.png"},
    {"id": 9, "model": "qwen-image-turbo", "prompt": "a wolf, halftone", "seed": 77, "file_path": "2026-12-07/318/b.webp"},
    {"id": 12, "model": "flux2-klein-4b", "prompt": "a wolf, woodcut", "seed": 5, "file_path": "2026-12-07/318/c.png"},
]


def idea(**changes):
    base = {"id": 318, "text": "Wolf at the laundromat", "lane": "apparel", "source": "team", "source_ref": None,
            "submitter": "josh@threadpower.com", "reviewer_notes": "more moonlight", "scout_motive": None}
    base.update(changes)
    return base


def promotion(**changes):
    base = {"id": 41, "promoted_by": "steph@threadpower.com", "concept_ids": [9, 4],
            "created": datetime(2026, 12, 8, 15, 2, 0, tzinfo=timezone.utc)}
    base.update(changes)
    return base


class Shape(unittest.TestCase):
    def test_the_whole_package_for_a_team_idea(self):
        got = build_package(promotion(), idea(), CONCEPTS, ["uploads/318/sketch.jpg"], NAMES)
        self.assertEqual(got, {
            "schema": 1,
            "promotion_id": 41,
            "idea": {"id": 318, "text": "Wolf at the laundromat", "lane": "apparel", "source": "team",
                     "source_ref": None, "submitter": "Josh"},
            "promoted_by": "Steph",
            "promoted_at": "2026-12-08T15:02:00Z",
            "reviewer_notes": "more moonlight",
            "scout": {"finding_id": None, "motive": None, "evidence_url": None},
            "concepts": [
                {"file": "concept-1.webp", "model": "qwen-image-turbo", "prompt": "a wolf, halftone", "seed": 77},
                {"file": "concept-2.png", "model": "flux2-klein-4b", "prompt": "a wolf, flat ink", "seed": 1234},
            ],
            "reference_images": ["ref-1.jpg"],
        })

    def test_the_keys_are_exactly_the_ones_in_the_spec(self):
        got = build_package(promotion(), idea(), CONCEPTS, [], NAMES)
        self.assertEqual(list(got), ["schema", "promotion_id", "idea", "promoted_by", "promoted_at",
                                     "reviewer_notes", "scout", "concepts", "reference_images"])
        self.assertEqual(list(got["idea"]), ["id", "text", "lane", "source", "source_ref", "submitter"])
        self.assertEqual(got["schema"], 1)


class Concepts(unittest.TestCase):
    def test_zero_concepts_is_a_valid_package(self):
        got = build_package(promotion(concept_ids=[]), idea(), CONCEPTS, [], NAMES)
        self.assertEqual(got["concepts"], [])
        self.assertEqual(got["reference_images"], [])
        self.assertEqual(build_package(promotion(concept_ids=[]), idea(), [], [], NAMES)["concepts"], [])

    def test_zero_concepts_does_not_drop_the_reference_images(self):
        got = build_package(promotion(concept_ids=[]), idea(), CONCEPTS, ["uploads/318/sketch.jpg", "uploads/318/b.png"], NAMES)
        self.assertEqual(got["concepts"], [])
        self.assertEqual(got["reference_images"], ["ref-1.jpg", "ref-2.png"])

    def test_only_the_ticked_concepts_in_the_order_they_were_ticked(self):
        got = build_package(promotion(concept_ids=[12, 4, 9]), idea(), CONCEPTS, [], NAMES)
        self.assertEqual([c["seed"] for c in got["concepts"]], [5, 1234, 77])
        self.assertEqual([c["file"] for c in got["concepts"]], ["concept-1.png", "concept-2.png", "concept-3.webp"])

    def test_a_ticked_concept_that_is_not_one_of_the_ideas_concepts_is_an_error(self):
        with self.assertRaises(ValueError):
            build_package(promotion(concept_ids=[4, 99]), idea(), CONCEPTS, [], NAMES)

    def test_reference_images_are_numbered_in_order_and_keep_their_endings(self):
        got = build_package(promotion(), idea(), CONCEPTS, ["uploads/318/x.png", "uploads/318/photo.JPG"], NAMES)
        self.assertEqual(got["reference_images"], ["ref-1.png", "ref-2.JPG"])


class Filenames(unittest.TestCase):
    def test_names_count_from_one_and_keep_each_files_own_ending(self):
        self.assertEqual(numbered("concept", ["a/b/x.png", "y.webp", "z.PNG"]), ["concept-1.png", "concept-2.webp", "concept-3.PNG"])
        self.assertEqual(numbered("ref", ["uploads/318/sketch.jpg"]), ["ref-1.jpg"])

    def test_no_paths_is_no_names_and_a_file_with_no_ending_gets_none(self):
        self.assertEqual(numbered("ref", []), [])
        self.assertEqual(numbered("ref", ["uploads/318/scan"]), ["ref-1"])


class People(unittest.TestCase):
    def test_emails_become_display_names(self):
        got = build_package(promotion(promoted_by="josh@threadpower.com"), idea(submitter="steph@threadpower.com"),
                            CONCEPTS, [], NAMES)
        self.assertEqual((got["promoted_by"], got["idea"]["submitter"]), ("Josh", "Steph"))

    def test_a_system_name_is_shown_as_it_is(self):
        got = build_package(promotion(), idea(source="warp", submitter="warp", source_ref="tool feedback"),
                            CONCEPTS, [], NAMES)
        self.assertEqual(got["idea"]["submitter"], "warp")
        self.assertEqual(got["idea"]["source_ref"], "tool feedback")


    def test_a_system_name_that_is_not_in_the_names_is_still_shown_as_itself(self):
        got = build_package(promotion(promoted_by="luma"), idea(source="scout", submitter="scout"), CONCEPTS, [], {})
        self.assertEqual((got["promoted_by"], got["idea"]["submitter"]), ("luma", "scout"))

    def test_an_email_that_is_not_in_the_names_is_an_error(self):
        with self.assertRaises(ValueError):
            build_package(promotion(), idea(submitter="ghost@threadpower.com"), CONCEPTS, [], NAMES)
        with self.assertRaises(ValueError):
            build_package(promotion(promoted_by="ghost@threadpower.com"), idea(), CONCEPTS, [], NAMES)
        with self.assertRaises(ValueError):
            build_package(promotion(), idea(), CONCEPTS, [], {})

    def test_no_email_address_is_anywhere_in_the_package(self):
        got = build_package(promotion(), idea(), CONCEPTS, ["uploads/318/sketch.jpg"], NAMES)
        self.assertNotIn("@", repr(got))


class Rest(unittest.TestCase):
    def test_the_time_is_written_in_utc_to_the_second_with_a_z(self):
        central = timezone(timedelta(hours=-6))
        made = datetime(2026, 12, 8, 9, 2, 30, 999999, tzinfo=central)
        got = build_package(promotion(created=made), idea(), CONCEPTS, [], NAMES)
        self.assertEqual(got["promoted_at"], "2026-12-08T15:02:30Z")

    def test_a_scout_idea_carries_its_finding_and_motive(self):
        scouted = idea(source="scout", source_ref="FND-2026-50-003", scout_motive="belonging", submitter="scout")
        got = build_package(promotion(), scouted, CONCEPTS, [], NAMES)
        self.assertEqual(got["scout"], {"finding_id": "FND-2026-50-003", "motive": "belonging", "evidence_url": None})

    def test_an_idea_that_is_not_from_scout_has_an_empty_scout_block(self):
        odd = idea(source="warp", source_ref="meeting", scout_motive="belonging", submitter="warp")
        got = build_package(promotion(), odd, CONCEPTS, [], NAMES)
        self.assertEqual(got["scout"], {"finding_id": None, "motive": None, "evidence_url": None})

    def test_no_lane_and_no_notes_stay_empty(self):
        got = build_package(promotion(), idea(lane=None, reviewer_notes=None), CONCEPTS, [], NAMES)
        self.assertIsNone(got["idea"]["lane"])
        self.assertIsNone(got["reviewer_notes"])

    def test_nothing_passed_in_is_changed(self):
        p, i, c = promotion(), idea(), [dict(x) for x in CONCEPTS]
        build_package(p, i, c, ["uploads/318/x.png"], NAMES)
        self.assertEqual((p, i, c), (promotion(), idea(), CONCEPTS))


class Confirm(unittest.TestCase):
    BASE = "This hands a package to Warp. It will show up in Warp's review queue."

    def test_with_concepts_it_is_the_sentence_in_the_spec(self):
        self.assertEqual(confirm_text(2), self.BASE)
        self.assertEqual(confirm_text(1), self.BASE)

    def test_with_no_concepts_it_says_so(self):
        self.assertEqual(confirm_text(0), self.BASE + " No concepts attached.")


if __name__ == "__main__":
    unittest.main()
