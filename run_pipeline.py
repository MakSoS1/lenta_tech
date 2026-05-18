import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.pipeline.price_tag_pipeline import PriceTagPipeline


def _parse_excludes(values: list[str] | None) -> list[str]:
    excludes: list[str] = []
    for value in values or []:
        excludes.extend([part.strip() for part in value.split(",") if part.strip()])
    return excludes


def main():
    parser = argparse.ArgumentParser(description="Process Lenta shelf video into price-tag CSV")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", "-o", default=None, help="Output CSV path")
    parser.add_argument("--output-dir", default=None, help="Output directory, defaults to ./outputs")
    parser.add_argument("--conf", type=float, default=0.05, help="YOLO confidence threshold for general mode")
    parser.add_argument("--frames", type=int, default=60, help="Frames sampled in general mode")
    parser.add_argument(
        "--mode",
        choices=["general", "catalog", "register"],
        default="general",
        help=(
            "general runs detector/OCR; register transfers a closest labeled template only for unlabeled repeat "
            "passes; catalog is kept as a compatibility alias and does not exact-fit labeled videos"
        ),
    )
    parser.add_argument("--no-vlm", action="store_true", help="Disable local Ollama VLM fallback")
    parser.add_argument("--vlm-max-tags", type=int, default=None, help="Maximum local VLM calls per video")
    parser.add_argument(
        "--catalog-exclude",
        action="append",
        default=[],
        help="Comma-separated video stems excluded from catalog matching, useful for leave-one-video-out checks",
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: video not found: {video_path}")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = Path(args.output_dir) if args.output_dir else Path(__file__).resolve().parent / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{video_path.stem}_final.csv"

    pipeline = PriceTagPipeline(
        use_vlm=not args.no_vlm,
        conf_threshold=args.conf,
        mode=args.mode,
        vlm_max_tags=args.vlm_max_tags,
    )
    results = pipeline.process_video(
        str(video_path),
        num_frames=args.frames,
        mode=args.mode,
        catalog_exclude=_parse_excludes(args.catalog_exclude),
    )
    pipeline.save_csv(results, str(output_path))
    print(f"mode={args.mode} saved {len(results)} tags to {output_path}")


if __name__ == "__main__":
    main()
