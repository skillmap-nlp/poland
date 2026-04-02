#!/usr/bin/env python3
"""Build slim Lightcast AI skills payload for the report."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
INPUT_XLSX = ROOT_DIR / "ai_skills_2026_lightcast_scraped.xlsx"
OUTPUT_JS = BASE_DIR / "assets" / "lightcast_ai_skills_data.js"
EMBEDDINGS_NPZ = ROOT_DIR / "lightcast_aiml" / "lightcast_ai_skills_voyage4.npz"
AUDIT_CSV = ROOT_DIR / "lightcast_aiml" / "lightcast_new_skill_cluster_predictions.csv"
MATCH_SCORES_NPZ = ROOT_DIR / "lightcast_aiml" / "ai_skill_match_scores.npz"
MATCH_THRESHOLD = 0.55
JOBS_DB = ROOT_DIR / "jobs_database.db"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "using",
    "use",
    "in",
    "of",
    "to",
    "a",
    "an",
    "or",
    "on",
    "ai",
    "artificial",
    "intelligence",
    "skill",
    "skills",
}


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9+#.-]{3,}", text.lower())
        if token not in STOPWORDS
    ]


def split_segments(text: str) -> list[str]:
    raw_parts = re.split(r"[\n\r•]+|(?<=[.!?;])\s+", text)
    segments = []
    for part in raw_parts:
        cleaned = clean_text(part)
        if 20 <= len(cleaned) <= 260:
            segments.append(cleaned)
    return segments


def choose_best_excerpt(
    skill_name: str, text_blocks: list[tuple[str, str]]
) -> tuple[str, str, float, int, int]:
    skill_name_clean = clean_text(skill_name)
    skill_name_lower = skill_name_clean.lower()
    skill_tokens = set(tokenize(skill_name_clean))

    best_excerpt = ""
    best_source = ""
    best_score = -1.0
    best_contains_full = 0
    best_overlap = 0

    for source, text in text_blocks:
        for segment in split_segments(text):
            segment_lower = segment.lower()
            segment_tokens = set(tokenize(segment))
            overlap = len(skill_tokens & segment_tokens)
            contains_full = 1 if skill_name_lower in segment_lower else 0
            contains_partial = sum(1 for token in skill_tokens if token in segment_tokens)
            score = contains_full * 10 + overlap * 3 + contains_partial * 1.5
            if score > best_score:
                best_excerpt = segment
                best_source = source
                best_score = score
                best_contains_full = contains_full
                best_overlap = overlap

    return best_excerpt, best_source, best_score, best_contains_full, best_overlap


def main() -> None:
    df = pd.read_excel(INPUT_XLSX, sheet_name="all_skills")
    df = df[df["retrieve_status"] == "ok"].copy()
    df["skill_id"] = df["skill_id"].astype(str)

    embeddings_npz = np.load(EMBEDDINGS_NPZ, allow_pickle=True)
    embedding_map = {
        str(skill_id): embeddings_npz["embeddings"][idx]
        for idx, skill_id in enumerate(embeddings_npz["skill_ids"])
    }
    df = df[df["skill_id"].isin(embedding_map)].copy()

    benchmark_df = df[df["worldbank_ai_skill"] == 1].copy()
    new_df = df[df["worldbank_ai_skill"] == 0].copy()

    cluster_order = sorted(benchmark_df["excel_ai_skill_cluster"].dropna().unique())
    centroids: dict[str, np.ndarray] = {}
    for cluster in cluster_order:
        cluster_ids = benchmark_df.loc[
            benchmark_df["excel_ai_skill_cluster"] == cluster, "skill_id"
        ].tolist()
        cluster_matrix = np.vstack([embedding_map[skill_id] for skill_id in cluster_ids]).astype(
            np.float32
        )
        centroids[cluster] = l2_normalize(cluster_matrix.mean(axis=0))

    centroid_matrix = np.vstack([centroids[cluster] for cluster in cluster_order]).astype(np.float32)

    predicted_rows = []
    for _, row in new_df.iterrows():
        sims = centroid_matrix @ embedding_map[row["skill_id"]]
        order = np.argsort(-sims)
        top1 = int(order[0])
        top2 = int(order[1])
        predicted_rows.append(
            {
                "skill_id": row["skill_id"],
                "lightcast_name": clean_text(row.get("lightcast_name")),
                "predicted_cluster": cluster_order[top1],
                "predicted_score": float(sims[top1]),
                "second_cluster": cluster_order[top2],
                "second_score": float(sims[top2]),
                "score_margin": float(sims[top1] - sims[top2]),
                "classification_method": "embedding_centroid_voyage4",
                "expert_verification_needed": 1,
            }
        )

    predicted_df = pd.DataFrame(predicted_rows)
    predicted_map = {
        row["skill_id"]: row for row in predicted_df.to_dict(orient="records")
    }
    predicted_df.to_csv(AUDIT_CSV, index=False)

    rows = []
    for _, row in df.sort_values(["worldbank_ai_skill", "lightcast_name"], ascending=[False, True]).iterrows():
        martins_neto = int(row.get("worldbank_ai_skill", 0) or 0)
        prediction = predicted_map.get(row["skill_id"], {})
        cluster = clean_text(row.get("excel_ai_skill_cluster")) or clean_text(
            prediction.get("predicted_cluster")
        )
        cluster_source = "paper" if martins_neto else "embedding_provisional"
        rows.append(
            {
                "skill_id": clean_text(row.get("skill_id")),
                "skill_name": clean_text(row.get("lightcast_name")),
                "description": clean_text(row.get("lightcast_description")),
                "cluster": cluster,
                "category": clean_text(row.get("lightcast_category")),
                "subcategory": clean_text(row.get("lightcast_subcategory")),
                "skill_type": clean_text(row.get("lightcast_type")),
                "martins_neto": martins_neto,
                "lightcast_new": int(not martins_neto),
                "cluster_source": cluster_source,
                "predicted_score": round(float(prediction.get("predicted_score", 0.0)), 4)
                if not martins_neto
                else None,
                "expert_verification_needed": int(not martins_neto),
            }
        )

    row_map = {row["skill_id"]: row for row in rows}

    cluster_summary = {}
    for cluster in cluster_order:
        paper_count = int(
            benchmark_df["excel_ai_skill_cluster"].fillna("").eq(cluster).sum()
        )
        new_count = int(predicted_df["predicted_cluster"].fillna("").eq(cluster).sum())
        cluster_summary[cluster] = {
            "paper_count": paper_count,
            "new_count": new_count,
            "total_count": paper_count + new_count,
        }

    match_npz = np.load(MATCH_SCORES_NPZ, allow_pickle=True)
    matched_skill_ids = embeddings_npz["skill_ids"][match_npz["indices_all"]]
    matched_scores = match_npz["scores_all"]
    matched_job_ids = match_npz["job_ids"]
    valid_mask = matched_scores >= MATCH_THRESHOLD

    conn = sqlite3.connect(JOBS_DB)
    title_rows = conn.execute(
        "SELECT id, title_clean, requirements, responsibilities, description "
        "FROM job_ads WHERE title_clean IS NOT NULL"
    ).fetchall()
    conn.close()
    job_map = {
        int(job_id): {
            "title": clean_text(title),
            "requirements": clean_text(requirements),
            "responsibilities": clean_text(responsibilities),
            "description": clean_text(description),
        }
        for job_id, title, requirements, responsibilities, description in title_rows
    }

    ai_postings_total = int(valid_mask.sum())
    cluster_counts: dict[str, int] = {}
    cluster_skill_counts: dict[str, dict[str, int]] = {}

    for skill_id in matched_skill_ids[valid_mask]:
        skill_key = str(skill_id)
        row = row_map.get(skill_key)
        if not row:
            continue
        cluster = row["cluster"] or "Unclassified"
        cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
        cluster_skill_counts.setdefault(cluster, {})
        cluster_skill_counts[cluster][skill_key] = cluster_skill_counts[cluster].get(skill_key, 0) + 1

    example_candidates = []
    seen_pairs = set()
    for idx, is_valid in enumerate(valid_mask):
        if not is_valid:
            continue
        skill_key = str(matched_skill_ids[idx])
        row = row_map.get(skill_key)
        job = job_map.get(int(matched_job_ids[idx]))
        if not row or not job:
            continue
        excerpt, excerpt_source, excerpt_score, contains_full, overlap = choose_best_excerpt(
            row["skill_name"],
            [
                ("Requirements", job["requirements"]),
                ("Responsibilities", job["responsibilities"]),
                ("Description", job["description"]),
            ],
        )
        if not excerpt or excerpt_score < 1:
            continue
        dedup_key = (excerpt, row["skill_name"])
        if dedup_key in seen_pairs:
            continue
        seen_pairs.add(dedup_key)
        example_candidates.append(
            {
                "job_title": job["title"],
                "excerpt": excerpt,
                "excerpt_source": excerpt_source,
                "excerpt_score": round(float(excerpt_score), 1),
                "match_style": "exact" if contains_full or overlap >= 2 else "semantic",
                "skill_name": row["skill_name"],
                "cluster": row["cluster"],
                "score": round(float(matched_scores[idx]), 3),
                "martins_neto": row["martins_neto"],
                "lightcast_new": row["lightcast_new"],
            }
        )

    example_candidates = [row for row in example_candidates if row["score"] >= 0.60]

    exact_examples = sorted(
        [row for row in example_candidates if row["match_style"] == "exact"],
        key=lambda item: (-item["excerpt_score"], -item["score"], item["cluster"], item["job_title"]),
    )
    semantic_examples = sorted(
        [
            row
            for row in example_candidates
            if row["match_style"] == "semantic" and row["excerpt_score"] >= 3 and row["score"] >= 0.63
        ],
        key=lambda item: (-item["score"], -item["excerpt_score"], item["cluster"], item["job_title"]),
    )

    selected_examples = []
    used_clusters: dict[str, int] = {}
    used_skills: set[str] = set()

    def try_add_example(example: dict[str, object]) -> bool:
        cluster = example["cluster"] or "Unclassified"
        if used_clusters.get(cluster, 0) >= 2:
            return False
        skill_name = str(example["skill_name"])
        if skill_name in used_skills:
            return False
        selected_examples.append(example)
        used_clusters[cluster] = used_clusters.get(cluster, 0) + 1
        used_skills.add(skill_name)
        return True

    for example in semantic_examples[:6]:
        try_add_example(example)

    for example in exact_examples:
        try_add_example(example)
        if len(selected_examples) >= 16:
            break

    if len(selected_examples) < 16:
        for example in semantic_examples[6:]:
            try_add_example(example)
            if len(selected_examples) >= 16:
                break

    if len(selected_examples) < 16:
        fallback_candidates = sorted(
            example_candidates,
            key=lambda item: (-item["excerpt_score"], -item["score"], item["cluster"], item["job_title"]),
        )
        for example in fallback_candidates:
            try_add_example(example)
            if len(selected_examples) >= 16:
                break

    demand_summary = []
    for cluster, count in sorted(cluster_counts.items(), key=lambda item: (-item[1], item[0])):
        top_skills = []
        for skill_id, skill_count in sorted(
            cluster_skill_counts[cluster].items(),
            key=lambda item: (-item[1], row_map[item[0]]["skill_name"]),
        )[:5]:
            row = row_map[skill_id]
            top_skills.append(
                {
                    "skill_id": skill_id,
                    "skill_name": row["skill_name"],
                    "count": int(skill_count),
                    "share_within_cluster_pct": round(skill_count / count * 100, 1),
                    "martins_neto": row["martins_neto"],
                    "lightcast_new": row["lightcast_new"],
                }
            )

        summary = cluster_summary.get(cluster, {"paper_count": 0, "new_count": 0, "total_count": 0})
        demand_summary.append(
            {
                "cluster": cluster,
                "count": int(count),
                "share_of_ai_postings_pct": round(count / ai_postings_total * 100, 1) if ai_postings_total else 0.0,
                "paper_count": summary["paper_count"],
                "new_count": summary["new_count"],
                "top_skills": top_skills,
            }
        )

    payload = {
        "meta": {
            "count_total": len(rows),
            "count_martins_neto": sum(row["martins_neto"] for row in rows),
            "count_lightcast_new": sum(row["lightcast_new"] for row in rows),
            "cluster_summary": cluster_summary,
            "ai_postings_total_expanded": ai_postings_total,
            "match_threshold": MATCH_THRESHOLD,
            "classification_note": (
                "New Lightcast AI skills are assigned to Martins-Neto clusters "
                "using embedding-based classification and still require expert verification."
            ),
        },
        "rows": rows,
        "demand_summary": demand_summary,
        "match_examples": selected_examples,
    }

    OUTPUT_JS.write_text(
        "window.__LIGHTCAST_AI_SKILLS__ = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"Saved {OUTPUT_JS}")
    print(f"Saved {AUDIT_CSV}")
    print(payload["meta"])


if __name__ == "__main__":
    main()
