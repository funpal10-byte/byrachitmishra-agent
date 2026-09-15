"""A reproducible editorial sample, rendered by the production templates.

No content API, publishing or scheduling calls. Use --video if ffmpeg is installed.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import config, render, video
from agent.schema import validate


def visual(kind, pairs, note="Suggested check"):
    return {"kind": kind, "items": [{"label": a, "detail": b} for a, b in pairs], "note": note}


QUEUE = visual("bottleneck", [("DRAFTS READY", "AI speeds up production"),
                              ("APPROVAL", "Still waiting for an owner")], "Illustrative workflow")
CHECK = visual("checklist", [("Owner", "Name the person who can approve."),
                             ("Evidence", "Attach the source for each claim."),
                             ("Escalation", "Agree who resolves a disputed claim.")])
COMPARE = visual("comparison", [("Drafting", "Time spent producing the copy"),
                                 ("Waiting", "Time until someone can approve")], "Illustrative workflow")


def sample():
    hook = "AI drafts faster. Approval still waits."
    lines = [hook, "Measure drafting and waiting separately.",
             "A reviewer needs more than clean copy.", "Give every claim a source and an owner.",
             "Agree the approval checks before drafting.", "Own the queue before scaling the output."]
    beats = [{"timecode": f"0:{i*5:02d}-0:{(i+1)*5:02d}", "onscreen": line,
              "voiceover": line, "direction": "Rendered text and workflow illustration."}
             for i, line in enumerate(lines)]
    beats[1]["visual"] = COMPARE
    beats[3]["visual"] = visual("comparison", [("Copy only", "Reviewer must find the evidence"),
                                               ("Copy + source", "Reviewer can check the claim")])
    beats[4]["visual"] = CHECK
    return {
        "title": "ai_approval_queue", "format": "reel", "pillar": "ai_marketing",
        "primary_keyword": "AI governance", "claim": "Drafting faster cannot remove an approval queue without clear ownership.",
        "hook": hook, "evidence": {"type": "framework", "detail": "Track drafting and waiting separately; assign an approver, source and escalation route before drafting."},
        "reel_cover": {"headline": "Ready. Still stuck.", "signal": "The approval bottleneck", "layout": "split", "visual": QUEUE},
        "reel_script": beats,
        "caption": hook + "\n\nAI governance starts before the copy arrives.\n\nA reviewer who must find the source and locate the decision owner is doing work the brief left unfinished.\n\nSeparate drafting time from waiting time. Then agree an approver and escalation route before the next brief.\n\nExtra review can be necessary. An ownerless queue is a different problem.\n\nSend this to whoever owns your content approvals.\n\n[ai governance, enterprise marketing, content approval]",
        "hashtags": ["#aigovernance", "#aimarketing", "#marketingoperations"],
        "alt_text": "Draft cards waiting at an approval gate; a Reel about AI governance.",
        "cta": "Send this to whoever owns your content approvals.",
        "failure_mode": "A simplified workflow cannot diagnose a real team's delay; measure it before changing review.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", action="store_true")
    args = parser.parse_args()
    brand = config.load_brand()
    root = config.ROOT / "preview" / "reset"
    root.mkdir(parents=True, exist_ok=True)
    post = sample()
    problems = validate(post)
    if problems:
        raise ValueError("\n".join(problems))
    (root / "sample-post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    covers = []
    options = [("Ready. Still stuck.", "The approval bottleneck", QUEUE),
               ("Cheap has a condition.", "The buyer must defend it", visual("comparison", [("LOWER PRICE", "Harder to defend without proof"), ("LOWER RISK", "Evidence the buyer can take upstairs")], "Illustrative buying trade-off")),
               ("Polished. Unproven.", "Before the claim goes live", visual("checklist", [("Source", "Does the evidence support the wording?"), ("Scope", "Does the claim exceed the evidence?"), ("Owner", "Who signs off the claim?")]))]
    for i, (headline, signal, obj) in enumerate(options):
        candidate = dict(post, reel_cover={"headline": headline, "signal": signal, "layout": "signal", "visual": obj})
        candidate["pillar"] = ["ai_marketing", "b2b_brand", "reputation"][i]
        covers.append(render.render_reel_cover(candidate, brand, root / f"concept-{i+1}"))
    frames = video.render_cards(post, brand, root / "reel-frames", None)
    carousel = dict(post, format="carousel", pillar="ai_in_practice", slides=[
        {"headline": post["hook"]},
        {"kicker": "01 / Diagnose", "headline": "Separate writing time from waiting time", "visual": COMPARE},
        {"kicker": "02 / Locate", "headline": "Find the decision that has no owner", "visual": QUEUE},
        {"kicker": "03 / Equip", "headline": "Send the evidence with the draft", "visual": beats_visual(post)},
        {"kicker": "04 / Use this", "headline": "Agree these checks before the next brief", "visual": CHECK},
        {"headline": "Own the queue before scaling output", "body": "Send this to whoever owns your content approvals."},
    ])
    errors = validate(carousel)
    if errors:
        raise ValueError("\n".join(errors))
    slides = render.render_carousel(carousel, brand, root / "carousel")
    from PIL import Image, ImageDraw
    def board(paths, filename, crop=False, portrait_height=640):
        width = 360
        height = 450 if crop else portrait_height
        result = Image.new("RGB", (len(paths)*(width+20)+20, height+70), "#e3e0d9")
        draw = ImageDraw.Draw(result)
        for i, path in enumerate(paths):
            with Image.open(path) as src:
                if crop:
                    src = src.crop((0, 285, 1080, 1635))
                src = src.resize((width, height))
                result.paste(src, (20+i*(width+20), 45))
            draw.text((20+i*(width+20), 15), f"{i+1:02d}", fill="#16181a")
        result.save(root / filename)
    board(covers, "covers-grid.jpg", True)
    board([covers[0], frames[1], frames[4]], "cover-to-payoff.jpg")
    board(slides, "carousel.jpg", portrait_height=450)
    if args.video:
        if not shutil.which("ffmpeg") and not os.getenv("FFMPEG_BINARY"):
            import imageio_ffmpeg
            os.environ["FFMPEG_BINARY"] = imageio_ffmpeg.get_ffmpeg_exe()
        video.assemble(frames, video.beat_durations(post["reel_script"]), root / "sample-reel.mp4", video.pick_music(post, brand))
    print(root)


def beats_visual(post):
    return post["reel_script"][3]["visual"]


if __name__ == "__main__":
    main()
