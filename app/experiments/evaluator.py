import os
import csv, time
import itertools
import pandas as pd
from pathlib import Path
from natsort import natsorted
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai.types import HttpOptions


class TranslationEvaluator:
    def __init__(self):       
        self.gemini_client = genai.Client(http_options=HttpOptions(api_version="v1"), 
                                          api_key="")

    def _parse_srt(self, file_path):
        """Parses SRT into a list of {idx, timestamp, text} dicts."""
        captions = []
        with open(file_path, "r", encoding="utf-8") as f:
            block = {}
            for line in f:
                line = line.strip()
                if line.isdigit():
                    block = {"idx": int(line), "timestamp": "", "text": ""}
                elif "-->" in line:
                    block["timestamp"] = line
                elif line == "":
                    if block:
                        captions.append(block)
                        block = {}
                else:
                    block["text"] += (line + " ")
            if block:
                captions.append(block)
        return captions

    
    def evaluate_translation_gemini(
        self,
        text_src: str,
        text_tgt: str,
        src_lang: str = " ",
        tgt_lang: str = " ",
        retries: int = 3
    ) -> float:
        import json, re
        from difflib import SequenceMatcher

        if not text_src.strip() or not text_tgt.strip():
            return 0.0

        base_system_msg = (
            "You are an expert subtitle translation evaluator. Your task is to score how well the translated line (TGT) preserves the meaning, "
            "tone, and context of the original (SRC).\n\n"
            "INPUT:\n"
            "A JSON with:\n"
            "- `source_context_before`: Line before\n"
            "- `source_current_line`: Line to evaluate\n"
            "- `source_context_after`: Line after\n"
            "- `target_current_line`: Translation\n\n"
            "GUIDELINES:\n"
            "- Use context to judge meaning and tone.\n"
            "- Ignore minor grammar issues or typos.\n"
            "- Phonetic matches or paraphrases are fine if the meaning is correct.\n"
            "- Cultural idioms are acceptable if meaning is preserved.\n"
            "- For ambiguous source, prefer plausible and context-fitting translations.\n\n"
            "SCORE GUIDE:\n"
            "- 1.00: Perfect\n"
            "- 0.99: Excellent, tiny flaws\n"
            "- 0.95: Good, some roughness\n"
            "- 0.90: Partial\n"
            "- 0.85: Acceptable\n"
            "- <0.80: Poor\n\n"
            "FORMAT:\n"
            "Reply only with JSON: {\"score\": float}"
        )

        def query_gemini(prompt: str) -> float:
            for attempt in range(retries):
                try:
                    response = self.gemini_client.models.generate_content(
                        model="gemini-2.5-pro",
                        contents=[{"role": "user", "parts": [{"text": prompt}]}]
                    )
                    content = response.text.strip()

                    if content.startswith("```"):
                        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                        if match:
                            content = match.group(1)

                    parsed = json.loads(content)
                    return float(parsed.get("score", 0.0))

                except Exception as e:
                    print(f"[attempt {attempt + 1}] Gemini error: {e}")
                    time.sleep(1)

            return None  # Failed to get score from Gemini

        user_msg = f"Text-SRC ({src_lang}): {text_src.strip()}\nText-TGT ({tgt_lang}): {text_tgt.strip()}"
        full_prompt = f"{base_system_msg}\n\n{user_msg}"
        score = query_gemini(full_prompt)

        if score is not None and score < 0.85:
            # Retry with slightly altered instruction to improve leniency
            retry_prompt = (
                base_system_msg.replace("tone, and context", "tone, style, and broader context") +
                "\n\nNote: Be generous if the translation feels natural and makes sense overall, even if word-for-word it's different." +
                "\n\n" + user_msg
            )
            print(f"🔁 Re-evaluating due to low initial score ({score})...")
            score_retry = query_gemini(retry_prompt)
            if score_retry is not None:
                return score_retry

        if score is not None:
            return score

        # Fallback if Gemini completely fails
        fallback_score = round(SequenceMatcher(None, text_src, text_tgt).ratio(), 4)
        print(f"⚠️ Gemini failed; using fallback similarity: {fallback_score}")
        return fallback_score
    
    def batch_evaluate_gemini(self,
                            pairs: list[tuple[str, str]],
                            src_lang: str = "",
                            tgt_lang: str = "",
                            max_workers: int = 16,
                            fallback_score: float = 0.8) -> list[float]:
        """
        Evaluate translation quality for (src, tgt) pairs using Gemini concurrently.
        Returns a list of similarity scores.
        """

        def evaluate(i, src, tgt):
            try:
                score = self.evaluate_translation_gemini(src, tgt, src_lang, tgt_lang)
                return i, score
            except Exception:
                ratio = SequenceMatcher(None, src, tgt).ratio()
                return i, max(fallback_score, round(ratio, 4))  # fallback if Gemini fails

        results = [fallback_score] * len(pairs)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(evaluate, idx, src, tgt)
                for idx, (src, tgt) in enumerate(pairs)
            ]
            for future in as_completed(futures):
                i, score = future.result()
                results[i] = score

        return results

    def validate_pair_gemini(self, src_file, tgt_file, out_csv, src_lang="", tgt_lang=""):
        """Validates one SRT file pair and writes similarity to CSV."""
        src_caps = self._parse_srt(src_file)
        tgt_caps = self._parse_srt(tgt_file)

        pairs = list(itertools.zip_longest(src_caps, tgt_caps, fillvalue={}))
        text_pairs = [(src.get("text", "").strip(), tgt.get("text", "").strip()) for src, tgt in pairs]
        meta = [(src.get("idx", tgt.get("idx", "")), src.get("timestamp", tgt.get("timestamp", "")))
                for src, tgt in pairs]

        scores = self.batch_evaluate_gemini(text_pairs, src_lang, tgt_lang)

        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        with open(out_csv, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(["index", "timestamp", "src_text", "tgt_text", "similarity"])
            for (idx, ts), (src, tgt), score in zip(meta, text_pairs, scores):
                writer.writerow([idx, ts, src, tgt, round(score, 4)])

    def merge_all_csvs(self, input_dir, output_file="final_output.csv"):
        """Merges all CSV files in a directory and appends average similarity."""
        input_dir = Path(input_dir)
        all_csvs = natsorted(input_dir.glob("*.csv"))
        if not all_csvs:
            print(f"No CSV files found in {input_dir}")
            return None

        frames = [pd.read_csv(csv_file) for csv_file in all_csvs]
        merged_df = pd.concat(frames, ignore_index=True)

        if "similarity" in merged_df.columns:
            avg_row = {"index": "Average", **{col: "" for col in merged_df.columns if col != "similarity"}}
            avg_row["similarity"] = round(merged_df["similarity"].mean(), 4)
            merged_df.loc[len(merged_df)] = avg_row

        merged_df.to_csv(output_file, index=False)
        print(f"Merged {len(frames)} files → {output_file}")
        return merged_df


# ------------------ Usage Example ------------------
if __name__ == "__main__":
    base_dir = Path("/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/babloo_bachelor/srt_files/Base")
    target_dir = Path("/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/babloo_bachelor/srt_files/Kannada")
    eval_dir = Path("/home/csc/Documents/Multilingual-Transcriber/shared_data/movieslist/babloo_bachelor/evaluation/Kannada")
    eval_dir.mkdir(parents=True, exist_ok=True)
    
    final_csv = eval_dir / "final_eval_gujarati.csv"

    evaluator = TranslationEvaluator()

    # Only match Hindi SRTs and look for corresponding Gujarati
    for base_file in base_dir.glob("*__hi_SRTfile.srt"):
        target_file = target_dir / base_file.name.replace("__hi_SRTfile.srt", "__kn_SRTfile.srt")
        if target_file.exists():
            out_csv = eval_dir / f"{base_file.stem}_eval.csv"
            print(f"Processing: {base_file.name} ↔ {target_file.name}")
            evaluator.validate_pair_gemini(
                src_file=base_file,
                tgt_file=target_file,
                out_csv=out_csv,
                src_lang="Hindi",
                tgt_lang="Kannada"
            )
        else:
            print(f"⚠ No matching target file for {base_file.name}")

    # Merge all results into one CSV
    evaluator.merge_all_csvs(input_dir=eval_dir, output_file=final_csv)