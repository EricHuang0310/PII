# run_stt.py
"""
STT JSON → 脫敏 Pipeline 轉接器

使用方式：
  python run_stt.py input.json
  python run_stt.py input.json -o output.json
  python run_stt.py /path/to/folder/          # 批次處理整個資料夾

STT JSON 格式：
  DIALOGUE_INFO.DIRECTION = "I"(inbound）/ "O"（outbound）
  DIALOGUE_CONTENT[].Role = "R0" / "R1"
  
  Inbound（客戶打進來）：R1 = AGENT, R0 = CUSTOMER
  Outbound（客服打出去）：R0 = AGENT, R1 = CUSTOMER
"""
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

from pipeline import MaskingPipeline, DialogueTurn, MaskingResult
from pseudonym import PseudonymTracker


# ══════════════════════════════════════════════════════════════
# Role 映射
# ══════════════════════════════════════════════════════════════

def _get_role_mapping(direction: str) -> Dict[str, str]:
    """
    根據通話方向決定 R0/R1 對應的 speaker。
    Inbound (I)：R1=客服接聽 → AGENT,  R0=客戶來電 → CUSTOMER
    Outbound(O)：R0=客服撥出 → AGENT,  R1=客戶接聽 → CUSTOMER
    """
    if direction == "O":
        return {"R0": "AGENT", "R1": "CUSTOMER"}
    else:  # "I" 或其他，預設 Inbound
        return {"R0": "CUSTOMER", "R1": "AGENT"}


# ══════════════════════════════════════════════════════════════
# JSON → DialogueTurn 轉換
# ══════════════════════════════════════════════════════════════

def parse_stt_json(data: Dict[str, Any]) -> tuple[str, List[DialogueTurn]]:
    """
    解析 STT JSON，回傳 (session_id, turns)。
    """
    call_id   = data.get("CALL_ID", "unknown")
    info      = data.get("DIALOGUE_INFO", {})
    direction = info.get("DIRECTION", "I")
    content   = data.get("DIALOGUE_CONTENT", [])

    role_map = _get_role_mapping(direction)

    turns: List[DialogueTurn] = []
    for utt in content:
        role    = utt.get("Role", "")
        text    = utt.get("Text", "").strip()
        begin   = int(utt.get("Begin", 0))
        end     = int(utt.get("End", 0))

        if not text:
            continue

        # ASR confidence：取該句所有 word 的平均信心分
        conf_str = utt.get("Confidence", "").strip()
        asr_confidence = None
        if conf_str:
            try:
                scores = [float(s) for s in conf_str.split()]
                asr_confidence = sum(scores) / len(scores) if scores else None
            except ValueError:
                pass

        speaker = role_map.get(role, "UNKNOWN")

        # STT 輸出的 Text 有空格分隔 token，去掉空格還原連續中文
        # 但保留英數之間的空格
        cleaned = _clean_stt_spaces(text)

        turns.append(DialogueTurn(
            speaker=speaker,
            text=cleaned,
            start_time=begin / 1000.0,   # ms → sec
            end_time=end / 1000.0,
            asr_confidence=asr_confidence,
        ))

    return call_id, turns


def _clean_stt_spaces(text: str) -> str:
    """
    清理 STT 空格：中文字之間的空格移除，英數之間保留。
    '我 是 客服 為您服務 您好' → '我是客服為您服務您好'
    'OK 好的' → 'OK 好的'（保留英中之間空格）
    """
    result = []
    chars = list(text)
    for i, c in enumerate(chars):
        if c == ' ':
            # 前後都是中文字 → 跳過空格
            prev_ch = chars[i - 1] if i > 0 else ''
            next_ch = chars[i + 1] if i + 1 < len(chars) else ''
            if _is_cjk(prev_ch) and _is_cjk(next_ch):
                continue
        result.append(c)
    return ''.join(result)


def _is_cjk(c: str) -> bool:
    if not c:
        return False
    cp = ord(c)
    return (0x4E00 <= cp <= 0x9FFF or      # CJK Unified
            0x3400 <= cp <= 0x4DBF or      # CJK Extension A
            0xF900 <= cp <= 0xFAFF)        # CJK Compat


# ══════════════════════════════════════════════════════════════
# 脫敏處理
# ══════════════════════════════════════════════════════════════

def process_stt(
    data: Dict[str, Any],
    pipeline: MaskingPipeline,
) -> Dict[str, Any]:
    """
    處理單筆 STT JSON，回傳含脫敏結果的新 JSON。
    """
    call_id, turns = parse_stt_json(data)

    if not turns:
        print(f"  [SKIP] {call_id}: 無對話內容")
        return data

    tracker = PseudonymTracker(session_id=call_id)
    results: List[MaskingResult] = pipeline.mask_dialogue(
        turns=turns, session_id=call_id,
    )

    # 將脫敏結果寫回 DIALOGUE_CONTENT
    content = data.get("DIALOGUE_CONTENT", [])
    result_idx = 0
    for utt in content:
        text = utt.get("Text", "").strip()
        if not text:
            continue
        if result_idx < len(results):
            r = results[result_idx]
            utt["Text_masked"]     = r.masked_text
            utt["Text_normalized"] = r.normalized_text
            utt["entities_found"]  = [
                {
                    "type":  e.entity_type,
                    "start": e.start,
                    "end":   e.end,
                    "score": round(e.score, 3),
                    "text":  r.normalized_text[e.start:e.end],
                }
                for e in r.entities_found
            ]
            utt["usability_tag"] = r.usability_tag
            result_idx += 1

    # 加上假名對照表和整體統計
    data["MASKING_SUMMARY"] = {
        "total_turns":     len(turns),
        "total_entities":  sum(r.entity_count for r in results),
        "entity_types":    list({et for r in results for et in r.entity_types}),
        "pseudonym_map":   tracker.get_mapping(),
    }

    return data


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def main():
    # ══════════════════════════════════════════════════════
    # 設定區（直接改這裡）
    # ══════════════════════════════════════════════════════
    INPUT_PATH  = "/raid2/Kee/Harry借用/Liang借用/04_語音資料庫/stt"        # 單檔或資料夾
    OUTPUT_DIR  = "/raid2/Kee/Harry借用/Liang借用/04_語音資料庫/pii_output"       # 輸出資料夾
    THRESHOLD   = 0.50
    CKIP_MODEL  = "/raid2/model/ckip/bert-base-chinese-ner"
    CKIP_DEVICE = -1   # -1=CPU, 0=GPU
    # ══════════════════════════════════════════════════════

    input_path = Path(INPUT_PATH)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 收集檔案
    if input_path.is_dir():
        files = sorted(input_path.glob("*.json"))
        if not files:
            print(f"[錯誤] 資料夾 {input_path} 中無 .json 檔案")
            return
    elif input_path.is_file():
        files = [input_path]
    else:
        print(f"[錯誤] 路徑不存在：{input_path}")
        return

    # 初始化 Pipeline
    import spacy, tempfile, os
    tmpdir = tempfile.mkdtemp()
    blank_path = os.path.join(tmpdir, "blank_zh")
    spacy.blank("zh").to_disk(blank_path)

    try:
        pipeline = MaskingPipeline(
            log_path=str(output_dir / "stt_audit_log.csv"),
            score_threshold=THRESHOLD,
            spacy_model=blank_path,
            enable_ckip=True,
            ckip_model=CKIP_MODEL,
            ckip_device=CKIP_DEVICE,
        )
    except Exception as e:
        print(f"[錯誤] Pipeline 初始化失敗：{e}")
        return

    print(f"處理 {len(files)} 個檔案...\n")

    with pipeline:
        for f in files:
            print(f"[處理] {f.name}")
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result_data = process_stt(data, pipeline)

                out_path = output_dir / (f.stem + "_masked.json")
                out_path.write_text(
                    json.dumps(result_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                summary = result_data.get("MASKING_SUMMARY", {})
                print(f"  → {out_path.name}  "
                      f"(entities: {summary.get('total_entities', 0)}, "
                      f"types: {summary.get('entity_types', [])})")

            except Exception as e:
                print(f"  [錯誤] {f.name}: {e}")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\nAudit log → {output_dir / 'stt_audit_log.csv'}")
    print("完成！")


if __name__ == "__main__":
    main()