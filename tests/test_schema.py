import unittest

from agent.schema import validate


def reel_post() -> dict:
    hook = "Stop paying agencies for asset volume"
    beats = [
        {
            "timecode": "0:00-0:03",
            "onscreen": hook,
            "voiceover": hook + ". Pay for the decisions they prevent.",
        }
    ]
    beats.extend(
        {
            "timecode": f"0:{start:02d}-0:{start + 4:02d}",
            "onscreen": f"Proof point {number}",
            "voiceover": f"This is proof point {number} with a specific mechanism.",
        }
        for number, start in enumerate(range(3, 23, 4), 2)
    )
    return {
        "title": "agency_scope_review",
        "pillar": "ai_marketing",
        "format": "reel",
        "primary_keyword": "AI agency retainers",
        "claim": "AI changes what agencies should be paid to do.",
        "hook": hook,
        "evidence": {
            "type": "framework",
            "detail": "Separate production work from strategic decision work in the scope review.",
        },
        "reel_script": beats,
        "caption": hook + ".\n\nAI agency retainers should reward judgment, not asset count.",
        "alt_text": "Text Reel about reviewing AI agency retainers.",
        "hashtags": ["#aimarketing", "#agencystrategy", "#brandstrategy"],
        "cta": "Send this to the person approving your next agency scope.",
        "failure_mode": "It fails if the scope review has no strategic decision to examine.",
    }


class HookContractTests(unittest.TestCase):
    def test_a_unified_opening_passes(self):
        self.assertEqual(validate(reel_post()), [])

    def test_topic_label_is_rejected(self):
        post = reel_post()
        post["hook"] = "How AI is changing marketing"
        post["reel_script"][0]["onscreen"] = post["hook"]
        post["reel_script"][0]["voiceover"] = post["hook"] + "."
        post["caption"] = post["hook"] + ".\n\nAI agency retainers should reward judgment."
        self.assertIn("hook starts as a topic label — lead with the cost, tension or objection", validate(post))

    def test_reel_opening_cannot_drift_from_the_hook(self):
        post = reel_post()
        post["reel_script"][0]["onscreen"] = "Generic work costs zero"
        self.assertIn("Reel beat 1 onscreen text must exactly match hook", validate(post))

    def test_factual_source_requires_a_url(self):
        post = reel_post()
        post["evidence"] = {"type": "source", "detail": "A reported benchmark."}
        self.assertIn("source evidence requires source_url", validate(post))

    def test_unknown_evidence_type_is_rejected(self):
        post = reel_post()
        post["evidence"] = {"type": "statistic", "detail": "A number without proof."}
        self.assertIn(
            "evidence type must be source, case_study, practitioner_observation or framework",
            validate(post),
        )

    def test_source_evidence_rejects_a_malformed_url(self):
        post = reel_post()
        post["evidence"] = {
            "type": "source",
            "detail": "A reported benchmark.",
            "source_url": "not-a-url",
        }
        self.assertIn("source evidence source_url must be an http or https URL", validate(post))
