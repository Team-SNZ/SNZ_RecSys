#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dotenv import load_dotenv
import os
import getpass
import sys
import argparse
import time
import json
from typing import List, Dict, Any, Optional
import pandas as pd

try:
    from openai import OpenAI
except Exception as e:
    raise SystemExit("Please install the OpenAI SDK first: pip install openai")

def _set_env(var: str) -> None:
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

load_dotenv(override=True)
_set_env("OPENAI_API_KEY")

QUESTION_THEMES = [
    "여행 중 최악의 경험과 그 이유",
    "이번 여행에서 이것만큼은 꼭 있으면 하는 것",
    "같이 여행을 가고 싶은 사람의 특징",
    "이번 여행에서 가장 기대하는 것",
    "이번 여행이 자신의 삶에 가졌으면 하는 의미",
]


def build_persona_context(row: pd.Series) -> str:
    """
    Build a compact persona description from CSV columns.
    Missing fields are skipped gracefully.
    """
    fields = [
        ("ID", row.get("ID", "")),
        ("예민함정도", row.get("예민함정도", "")),
        ("의견수용", row.get("의견수용", "")),
        ("말수", row.get("말수", "")),
        ("시간약속", row.get("시간약속", "")),
        ("리더십", row.get("리더십", "")),
        ("체력", row.get("체력", "")),
        ("청결민감도", row.get("청결민감도", "")),
        ("여행일정강도", row.get("여행일정강도", "")),
        ("국내or해외", row.get("국내or해외", "")),
        ("산or바다", row.get("산or바다", "")),
        ("계획or즉흥", row.get("계획or즉흥", "")),
        ("랜드마크", row.get("랜드마크", "")),
        ("코골이", row.get("코골이", "")),
        ("웨이팅", row.get("웨이팅", "")),
        ("여행희망지역", row.get("여행희망지역", "")),
        ("싫어하는기후", row.get("싫어하는기후", "")),
        ("여행목적", row.get("여행목적", "")),
        ("숙소유형", row.get("숙소유형", "")),
        ("기상시간", row.get("기상시간", "")),
        ("여행예산", row.get("여행예산", "")),
        ("Profile", row.get("Profile", "")),
        ("Rec_ids", row.get("Rec_ids", "")),
    ]

    # Convert NaN to empty string and format compactly
    def as_text(v):
        if pd.isna(v):
            return ""
        return str(v).strip()

    lines = [f"{k}: {as_text(v)}" for k, v in fields if as_text(v)]
    return "\n".join(lines)


def make_prompt(persona_text: str, question_themes: List[str]) -> List[Dict[str, str]]:
    """
    Construct chat messages for the OpenAI API to generate a concise summary in Korean.
    The model is asked to synthesize likely answers to all five themes into one paragraph.
    """
    system = (
        "당신은 여행 성향 인터뷰어이자 요약가입니다. "
        "주어진 페르소나 정보를 바탕으로 사용자가 아래 다섯 가지 질문에 대해 할 법한 답변을 "
        "간결하게 한 단락(summary)으로 한국어로 요약하세요. "
        "요약에는 다섯 주제가 모두 반영되어야 하며, 과장하거나 단정짓지 말고, "
        "페르소나에 나타난 사실과 합리적 추론만 사용하세요. "
        "문체는 1인칭(‘저는 …’)을 사용하고, 4~6문장 내외로 작성하세요. "
        "줄바꿈 없이 하나의 문단으로 출력하세요."
    )

    questions = "\n".join(f"- {q}" for q in question_themes)

    user = (
        f"[페르소나]\n{persona_text}\n\n"
        "[질문 주제]\n"
        f"{questions}\n\n"
        "요청: 위 다섯 주제를 모두 포함하는 요약 단락을 작성하세요."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def summarize_row(
    client: "OpenAI",
    row: pd.Series,
    model: str,
    temperature: float = 0.3,
    max_retries: int = 3,
) -> str:
    """
    Call the model once per row to get a compact summary paragraph.
    Retries briefly on transient errors.
    """
    persona = build_persona_context(row)
    messages = make_prompt(persona, QUESTION_THEMES)

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                n=1,
            )
            text = resp.choices[0].message.content.strip()
            return text
        except Exception as e:
            wait = min(2**attempt, 10)
            if attempt >= max_retries:
                raise
            time.sleep(wait)

    # Should never reach here
    return ""


def main():
    parser = argparse.ArgumentParser(description="Generate persona-based interview summaries and save back to CSV.")
    parser.add_argument("input_csv", help="Path to input CSV")
    parser.add_argument("--output", "-o", default=None, help="Path to output CSV (default: overwrite input)")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI chat model name (default: gpt-4o)")
    parser.add_argument("--temperature", type=float, default=1, help="Sampling temperature (default: 1)")
    parser.add_argument("--only-missing", action="store_true", help="Only fill empty 'summary' cells")
    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)

    # Ensure a 'summary' column exists
    if "summary" not in df.columns:
        df["summary"] = ""

    client = OpenAI()
    
    # Iterate rows
    updated_count = 0
    for idx, row in df.iterrows():
        # Skip if only-missing and summary already present
        if args.only_missing and isinstance(row.get("summary", ""), str) and row["summary"].strip():
            continue

        try:
            summary_text = summarize_row(client, row, model=args.model, temperature=args.temperature)
            df.at[idx, "summary"] = summary_text
            updated_count += 1
            print(f"[{idx}] updated summary.")
        except Exception as e:
            print(f"[{idx}] failed to summarize: {e}")

    output_path = args.output or args.input_csv
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Done. Updated {updated_count} rows. Saved to: {output_path}")


if __name__ == "__main__":
    main()
