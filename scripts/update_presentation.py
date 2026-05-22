"""Update the PowerPoint deck with corrected text and regenerated visuals."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
DECK_PATH = ROOT / "deliverables" / "montgomery_crash_safety_presentation.pptx"


TEXT_REPLACEMENTS = {
    "As Resources Are Limited So As People’s Attention": "Limited resources require focused safety investment",
    "Now We Need to Consider (Equity & Vulnerable Users)": "Priority scoring adds equity and vulnerable users",
    "Top 10 Segments by composite score": "Top 10 Segments by CEI-aware priority score",
}


SLIDE_IMAGES = {
    6: "assets/chart_01_annual_crashes.png",
    9: "assets/chart_03_vru_dui_ksi_share.png",
    11: "assets/chart_04_average_cost.png",
    12: "assets/chart_03_vru_dui_ksi_share.png",
    15: "assets/chart_05_hin_map.png",
    16: "assets/chart_06_hin_concentration.png",
    17: "assets/chart_07_top_ksi_segments.png",
    19: "assets/chart_08_exposure_rate.png",
    23: "assets/chart_09_priority_score.png",
    24: "assets/chart_10_cei_priority_map.png",
}


def replace_text(prs: Presentation) -> None:
    for slide in prs.slides:
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    text = run.text
                    for old, new in TEXT_REPLACEMENTS.items():
                        text = text.replace(old, new)
                    run.text = text


def delete_pictures(slide) -> None:
    for shape in list(slide.shapes):
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            shape._element.getparent().remove(shape._element)


def add_chart(slide, image_path: Path, prs: Presentation, full: bool = False) -> None:
    if full:
        slide.shapes.add_picture(str(image_path), Inches(0.3), Inches(0.7), width=prs.slide_width - Inches(0.6))
        return
    slide.shapes.add_picture(str(image_path), Inches(0.75), Inches(1.35), width=Inches(11.85))


def add_or_update_title(slide, text: str) -> None:
    title = slide.shapes.title
    if title is not None:
        title.text = text
        return
    box = slide.shapes.add_textbox(Inches(0.55), Inches(0.25), Inches(12.1), Inches(0.55))
    box.text_frame.text = text
    for paragraph in box.text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(24)
            run.font.bold = True


def update_images(prs: Presentation) -> None:
    for slide_number, rel_path in SLIDE_IMAGES.items():
        slide = prs.slides[slide_number - 1]
        delete_pictures(slide)
        image_path = ROOT / rel_path
        add_chart(slide, image_path, prs, full=slide_number in {15, 24})

    add_or_update_title(prs.slides[23], "CEI disadvantaged tracts and priority corridors")


def update_key_slide_text(prs: Presentation) -> None:
    slide4 = prs.slides[3]
    for shape in slide4.shapes:
        if getattr(shape, "has_text_frame", False) and "From" in shape.text:
            shape.text = (
                "From 2020-2024, Montgomery County recorded 59,476 crashes. "
                "Of these, 1,400 were fatal or suspected serious injury crashes (KSI), "
                "with an estimated $7.1 billion in societal cost. To reach Vision Zero, "
                "the County should focus engineering, enforcement, and policy on the "
                "corridors and conditions most strongly linked to severe crashes."
            )

    slide22 = prs.slides[21]
    replacements_by_text = {
        "KSI crash burden": "KSI crash burden",
        "(0.5 x Fatal collisions)": "(1.00 x KSI burden)",
        "(0.25 x Vulnerable Users collisions)": "(0.50 x VRU KSI)",
        "(0.25 x KSI crash burden\nIn disadvantaged areas)": "(0.25 x KSI in disadvantaged tracts)",
        "(0.25 x exposure-adjusted risk)": "(0.25 x exposure-adjusted risk)",
    }
    for shape in slide22.shapes:
        if getattr(shape, "has_text_frame", False):
            text = shape.text.strip()
            if text in replacements_by_text:
                shape.text = replacements_by_text[text]

    slide26 = prs.slides[25]
    for shape in slide26.shapes:
        if getattr(shape, "has_text_frame", False) and "Re-score" in shape.text:
            shape.text = (
                "Prioritizes high-harm corridors, including corridors in disadvantaged tracts\n\n"
                "Re-score every 2-3 years\n\n"
                "Phased delivery:\n"
                "Year 1: quick wins such as LPIs, daylighting, and pilot road diets\n"
                "Years 1-3: corridor redesigns\n"
                "Years 3-5: major reconstructions\n\n"
                "Track progress: KSI, HIN share, VRU KSI, CEI contribution, and exposure-adjusted risk"
            )


def main() -> None:
    prs = Presentation(DECK_PATH)
    replace_text(prs)
    update_key_slide_text(prs)
    update_images(prs)
    prs.save(DECK_PATH)
    print(f"Updated {DECK_PATH}")


if __name__ == "__main__":
    main()
