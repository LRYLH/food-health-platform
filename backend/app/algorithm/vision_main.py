"""
vision_engine 主入口 — 批量处理食品包装图片，输出 VisionResult JSON

用法:
    # 按 task_id 处理单张
    python vision_main.py --task-id 6f2b4c3d9f8142e6b2b0d6c9cf7d7f10

    # 扫描 vision_input 下所有图片，文件名 stem 作为 task_id
    python vision_main.py

会读取 model_io/vision_input/{task_id}.request.json（若存在），
结果写入 model_io/vision_output/{task_id}.json，符合 VisionResult 契约。
"""
import argparse
import json
import sys
import time
from pathlib import Path

IO_DIR = Path("/app/model_io")
INPUT_DIR = IO_DIR / "vision_input"
OUTPUT_DIR = IO_DIR / "vision_output"


def load_request(task_id: str) -> dict:
    """读取 BackendVisionRequest JSON（若存在），提取 task_id 和 user_context。"""
    req_path = INPUT_DIR / f"{task_id}.request.json"
    if req_path.exists():
        return json.loads(req_path.read_text(encoding="utf-8"))
    return {"task_id": task_id}


def process_image(image_path: Path, task_id: str) -> dict:
    """处理单张图片，返回 VisionResult。"""
    from vision_engine.pipeline import analyze

    t0 = time.perf_counter()

    if not image_path.exists():
        return {
            "schema_version": "1.0",
            "task_id": task_id,
            "ingredients": {"raw_text": None, "items": []},
            "nutrition_facts": {"raw_text": None, "serving_size": None, "items": []},
            "expiration_date": {"raw_text": None, "value": None},
            "detected_claims": [],
            "ocr_text_blocks": [],
            "meta": {"model": "error", "elapsed_ms": 0},
            "error": {"code": "IMAGE_NOT_FOUND", "message": f"文件不存在: {image_path}"},
        }

    result = analyze(str(image_path), task_id=task_id)
    result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


def run_batch():
    """扫描 vision_input 下所有图片，文件名 stem 作为 task_id。"""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = sorted(
        [p for p in INPUT_DIR.glob("*") if p.suffix.lower() in exts and not p.name.startswith(".")]
    )

    if not images:
        print(f"未在 {INPUT_DIR} 中找到图片文件")
        return

    print(f"\n{'='*60}")
    print(f"  vision_engine 批量分析 — {len(images)} 张图片")
    print(f"{'='*60}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for img in images:
        task_id = img.stem
        req = load_request(task_id)
        if "task_id" in req and req["task_id"] != task_id:
            task_id = req["task_id"]

        print(f"[{task_id}] {img.name} → ", end="", flush=True)

        try:
            result = process_image(img, task_id)
            out_path = OUTPUT_DIR / f"{task_id}.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

            ing = result.get("ingredients", {})
            nut = result.get("nutrition_facts", {})
            exp = result.get("expiration_date", {})
            meta = result.get("meta", {})

            print(f"配料:{len(ing.get('items') or [])} 营养:{len(nut.get('items') or [])} "
                  f"保质期:{exp.get('value') or '-'} [{meta.get('model', '?')}] → {out_path.name}")

        except Exception as e:
            print(f"失败: {e}")
            err = {
                "schema_version": "1.0",
                "task_id": task_id,
                "ingredients": {"raw_text": None, "items": []},
                "nutrition_facts": {"raw_text": None, "serving_size": None, "items": []},
                "expiration_date": {"raw_text": None, "value": None},
                "detected_claims": [],
                "ocr_text_blocks": [],
                "meta": {"model": "error"},
                "error": {"code": "VISION_ERROR", "message": str(e)},
            }
            (OUTPUT_DIR / f"{task_id}.json").write_text(
                json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    print(f"\n结果保存在: {OUTPUT_DIR}\n")


def run_single(task_id: str):
    """按 task_id 处理单张图片。"""
    req = load_request(task_id)
    if "image" in req and "path" in req.get("image", {}):
        img_path = Path(req["image"]["path"])
        if not img_path.is_absolute():
            img_path = Path("/app") / img_path
    else:
        # 根据扩展名查找图片
        exts = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
        candidates = [p for ext in exts if (p := INPUT_DIR / f"{task_id}{ext}").exists()]
        img_path = candidates[0] if candidates else INPUT_DIR / f"{task_id}.jpg"

    result = process_image(img_path, task_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="vision_engine 食品包装图像分析")
    parser.add_argument("--task-id", type=str, help="按指定 task_id 处理单张图片")
    args = parser.parse_args()

    if args.task_id:
        run_single(args.task_id)
    else:
        run_batch()
