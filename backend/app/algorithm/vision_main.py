"""
vision_engine 主入口 — 批量处理食品包装图片

用法:
    python vision_main.py                              # 处理 vision_input 下所有图片
    python vision_main.py --input path/to/image.jpg   # 处理单张图片
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
IO_DIR = Path("/app/model_io")
INPUT_DIR = IO_DIR / "vision_input"
OUTPUT_DIR = IO_DIR / "vision_output"


def process_image(image_path: Path) -> dict:
    """处理单张图片，返回结构化结果。"""
    from vision_engine.pipeline import analyze

    t0 = time.perf_counter()

    # 确保输入文件存在
    if not image_path.exists():
        return {"error": f"文件不存在: {image_path}", "image": image_path.name}

    result = analyze(str(image_path))
    result["image"] = image_path.name
    result["elapsed_s"] = round(time.perf_counter() - t0, 1)
    return result


def run_batch():
    """扫描 INPUT_DIR 下所有图片，逐一处理并输出 JSON。"""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = sorted(
        [p for p in INPUT_DIR.glob("*") if p.suffix.lower() in exts]
    )

    if not images:
        print(f"未在 {INPUT_DIR} 中找到图片文件")
        return

    print(f"\n{'='*60}")
    print(f"  vision_engine 批量分析 — {len(images)} 张图片")
    print(f"{'='*60}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for img in images:
        stem = img.stem
        size_kb = img.stat().st_size / 1024
        print(f"[{stem}] {img.name} ({size_kb:.0f}KB) → ", end="", flush=True)

        try:
            result = process_image(img)

            # 写入 JSON
            out_path = OUTPUT_DIR / f"{stem}.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 打印摘要
            ing = result.get("ingredients", {})
            nut = result.get("nutrition_facts", {})
            exp = result.get("expiration_date", {})
            meta = result.get("meta", {})

            ing_n = len(ing.get("items") or [])
            nut_n = len(nut.get("items") or [])
            exp_v = exp.get("value") or "-"
            elapsed = result.get("elapsed_s", "?")

            print(f"配料:{ing_n} 营养:{nut_n} 保质期:{exp_v}  [{elapsed}s] → {out_path.name}")

        except Exception as e:
            print(f"失败: {e}")
            err_result = {"image": img.name, "error": str(e)}
            out_path = OUTPUT_DIR / f"{stem}_error.json"
            out_path.write_text(
                json.dumps(err_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    print(f"\n结果保存在: {OUTPUT_DIR}\n")


def run_single(path: str):
    """处理单张图片。"""
    img = Path(path)
    result = process_image(img)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="vision_engine 食品包装图像分析")
    parser.add_argument("--input", "-i", type=str, help="单张图片路径")
    args = parser.parse_args()

    if args.input:
        run_single(args.input)
    else:
        run_batch()
