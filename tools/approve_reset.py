"""Install the two user-approved, complete reset samples; never publish here."""
from pathlib import Path
import datetime as dt
import json
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.preview_reset import sample, COMPARE, QUEUE, CHECK, beats_visual
from agent import config, render
from agent.schema import validate, check_voice
from agent.run_batch import write_readable


def main():
    brand = config.load_brand()
    now = dt.datetime.now(brand.timezone)
    base = config.APPROVED_DIR / "reset-approved"
    post = sample()
    carousel = dict(post, title="approval_owner_checklist", format="carousel", pillar="ai_in_practice")
    carousel.pop("reel_script", None)
    carousel.pop("reel_cover", None)
    carousel["hook"] = "Every approval needs a named owner."
    carousel["caption"] = carousel["caption"].replace(post["hook"], carousel["hook"], 1)
    carousel["alt_text"] = "Six slides with an AI governance workflow and an approval checklist."
    carousel["slides"] = [
        {"headline": carousel["hook"]},
        {"kicker": "01 / Diagnose", "headline": "Separate writing time from waiting time", "visual": COMPARE},
        {"kicker": "02 / Locate", "headline": "Find the decision that has no owner", "visual": QUEUE},
        {"kicker": "03 / Equip", "headline": "Send the evidence with the draft", "visual": beats_visual(post)},
        {"kicker": "04 / Use this", "headline": "Agree these checks before the next brief", "visual": CHECK},
        {"headline": "Own the queue before scaling output", "body": "Send this to whoever owns your content approvals."}]
    for item, days, hour in [(post, 1, 19), (carousel, 3, 10)]:
        folder = base / item["title"]
        if (folder / "post.json").exists():
            print("Already approved:", folder)
            continue
        problems = validate(item) + check_voice(item, brand.voice.get("banned_phrases", []))
        if problems:
            raise ValueError(problems)
        folder.mkdir(parents=True, exist_ok=True)
        item["status"] = "approved"
        item["content_version"] = 2
        item["approved_at"] = now.isoformat()
        item["scheduled_for"] = (now + dt.timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()
        if item["format"] == "reel":
            shutil.copy2(config.ROOT / "preview/reset/sample-reel.mp4", folder / "reel.mp4")
            shutil.copy2(config.ROOT / "preview/reset/concept-1/reel-cover.jpg", folder / "reel-cover.jpg")
            item["video"] = "reel.mp4"
            images = [folder / "reel-cover.jpg"]
        else:
            images = render.render_carousel(item, brand, folder)
        item["images"] = [p.name for p in images]
        item["warnings"] = []
        (folder / "post.json").write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
        write_readable(item, folder, images, [])
        print(item["title"], item["scheduled_for"])


if __name__ == "__main__":
    main()
