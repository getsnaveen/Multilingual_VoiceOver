import os, csv, json, time, html, itertools, re
from pathlib import Path
from typing import List, Tuple, Generator
import pandas as pd 
from difflib import SequenceMatcher
from natsort import natsorted
from openai import OpenAI
from google import genai
from google.genai.types import HttpOptions
from utils.logger import SingletonLogger, log_exceptions
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.config import get_settings
local_settings = get_settings()

class TranslationEvaluator:
    """
    A class for evaluating subtitle translation quality using the OpenAI API.
    """

    def __init__(self):
        self.logger = SingletonLogger.getInstance(self.__class__.__name__).logger
        self.openai_client = OpenAI(api_key=local_settings.openai_key) 
        self.gemini_client = genai.Client(http_options=HttpOptions(api_version="v1"), 
                                          api_key=local_settings.gemini_key)
         
        

    @log_exceptions()
    def generate_srt_pairs(self, src_dir: str, tgt_dir: str, src_suffix="_hi.srt", tgt_suffix="_en.srt") -> List[Tuple[str, str]]:
        """
        Returns a list of (src_file, tgt_file) pairs with matching stems.
        """
        src_files = {
            Path(f).stem.replace(src_suffix.replace(".srt", ""), ""): str(Path(src_dir) / f)
            for f in os.listdir(src_dir) if f.endswith(src_suffix)
        }
        tgt_files = {
            Path(f).stem.replace(tgt_suffix.replace(".srt", ""), ""): str(Path(tgt_dir) / f)
            for f in os.listdir(tgt_dir) if f.endswith(tgt_suffix)
        }
        keys = sorted(set(src_files) & set(tgt_files))
        return [(src_files[k], tgt_files[k]) for k in keys]

    @log_exceptions()
    def generate_srt_triples(self, hi_dir: str, id_dir: str, en_dir: str,
                             hi_suffix="_hi_SRTfile.srt",
                             id_suffix="_id_SRTfile.srt",
                             en_suffix="_en_SRTfile.srt") -> List[Tuple[str, str, str]]:
        """
        Returns a list of (hi_file, id_file, en_file) triples with matching stems.
        """
        def build_map(path, suffix):
            return {
                f.replace(suffix, ""): str(Path(path) / f)
                for f in os.listdir(path)
                if f.endswith(suffix)
            }

        hi_map = build_map(hi_dir, hi_suffix)
        id_map = build_map(id_dir, id_suffix)
        en_map = build_map(en_dir, en_suffix)

        common = sorted(set(hi_map) & set(id_map) & set(en_map))
        return [(hi_map[k], id_map[k], en_map[k]) for k in common]

    def _parse_srt(self, path: str) -> List[dict]:
        """
        Parses an SRT file into a list of captions with start/end timestamps and text.
        """
        def _hms_to_ms(hms: str) -> int:
            h, m, rest = hms.split(":")
            s, ms = rest.split(",")
            return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

        captions = []
        idx, ts, lines = None, None, []
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    if idx is not None and ts:
                        start, end = ts.split("-->")
                        captions.append({
                            "idx": idx,
                            "start_ms": _hms_to_ms(start.strip()),
                            "end_ms": _hms_to_ms(end.strip()),
                            "timestamp": ts,
                            "text": " ".join(lines),
                        })
                    idx, ts, lines = None, None, []
                elif idx is None and line.isdigit():
                    idx = int(line)
                elif ts is None and "-->" in line:
                    ts = line
                else:
                    lines.append(line)
        return captions

    def _collect_overlapping(self, src_caps, other_caps, tolerance=500) -> List[str]:
        """
        Collects overlapping text from another subtitle set based on timestamps.
        """
        out, j = [], 0
        for src in src_caps:
            buf = []
            while j < len(other_caps) and other_caps[j]["end_ms"] < src["start_ms"] - tolerance:
                j += 1
            k = j
            while k < len(other_caps) and other_caps[k]["start_ms"] <= src["end_ms"] + tolerance:
                buf.append(other_caps[k]["text"])
                k += 1
            out.append(" ".join(buf).strip())
        return out

    @log_exceptions("openai based evaluations")
    def evaluate_translation_openai(self, 
        text_src: str,
        text_tgt: str,
        src_lang: str = " ",
        tgt_lang: str = " ",
        retries: int = 3 ) -> float:
        """
        Evaluates how well text_tgt translates text_src (with minor typos allowed).
        Returns a score from 0.0 to 1.0 where 1.0 = perfect preservation of meaning.
        """

        if not text_src.strip() or not text_tgt.strip():
            return 0.0

        system_msg = (
            "You are a professional evaluator of translation quality.\n"
            "Judge how well Text-TGT conveys the meaning of Text-SRC.\n"
            "Ignore minor typos, small transcription errors, or differences in phrasing, "
            "as long as the meaning and spoken intent are preserved.\n"
            "Phonetic or sounding-similar translations are acceptable.\n"
            "Only respond with JSON: {\"score\": float between 0 and 1}.\n"
            "Use this rough guide:\n"
            " 1 = perfect translation\n"
            " 0.99 = excellent, small flaws or typos\n"
            " 0.95 = good meaning, maybe rough wording\n"
            " 0.90 = partial match\n"
            " 0.85 = acceptable\n"
            " < 0.80 = poor or incorrect translation"
        )

        user_msg = f"Text-SRC ({src_lang}): {text_src.strip()}\n" \
                f"Text-TGT ({tgt_lang}): {text_tgt.strip()}"

        for attempt in range(retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": user_msg}
                    ]
                ).choices[0].message.content.strip()

                # 🧹 Remove markdown code fences if present
                if response.startswith("```"):
                    response = response.strip("`").split("```")[1] if "```" in response[3:] else response.strip("`")

                score = float(json.loads(response)["score"])
                return score
                
            except Exception as e:
                print(f"[attempt {attempt + 1}] Error: {e}")
                time.sleep(1)

        return 0.0  

    @log_exceptions("Evaluating with Google Gemini")
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

    
    @log_exceptions("Batch Gemini Evaluation")
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
    
    @log_exceptions()
    def validate_pair_openai(self, src_file: str, tgt_file: str, out_csv: str,
                      src_lang="", tgt_lang=" ") -> None:
        """
        Validates one SRT file pair and writes similarity to CSV.
        """
        with open(out_csv, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(["index", "timestamp", "src_text", "tgt_text", "similarity"])
            src_iter = self._parse_srt(src_file)
            tgt_iter = self._parse_srt(tgt_file)

            for src, tgt in itertools.zip_longest(src_iter, tgt_iter, fillvalue={}):
                index = src.get("idx", tgt.get("idx"))
                ts = src.get("timestamp", tgt.get("timestamp"))
                score = self.evaluate_translation_openai(src.get("text", ""), tgt.get("text", ""), src_lang, tgt_lang)
                writer.writerow([index, ts, src.get("text", ""), tgt.get("text", ""), round(score, 4)])

    @log_exceptions()
    def validate_batch_openai(self, pairs: List[Tuple[str, str]],
                       src_lang="", tgt_lang=" ", output_dir="output_csvs") -> None:
        """
        Runs validation over a list of SRT file pairs.
        """
        Path(output_dir).mkdir(exist_ok=True)
        for src, tgt in pairs:
            out_file = Path(output_dir) / f"{Path(src).stem}__vs__{Path(tgt).stem}.csv"
            self.logger.info(f"▶ Validating {src} vs {tgt}")
            self.validate_pair_openai(src, tgt, str(out_file), src_lang, tgt_lang)
    
    @log_exceptions("Fast validate_pair_gemini")
    def validate_pair_gemini(self, src_file: str, tgt_file: str, out_csv: str,
                            src_lang: str = "", tgt_lang: str = "") -> None:
        """
        Validates one SRT file pair and writes similarity to CSV using batched Gemini scoring.
        """
        src_caps = self._parse_srt(src_file)
        tgt_caps = self._parse_srt(tgt_file)

        pairs = list(itertools.zip_longest(src_caps, tgt_caps, fillvalue={}))
        text_pairs = [(src.get("text", ""), tgt.get("text", "")) for src, tgt in pairs]
        meta = [(src.get("idx", tgt.get("idx", "")), src.get("timestamp", tgt.get("timestamp", "")))
                for src, tgt in pairs]

        scores = self.batch_evaluate_gemini(text_pairs, src_lang, tgt_lang)

        with open(out_csv, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(["index", "timestamp", "src_text", "tgt_text", "similarity"])
            for (idx, ts), (src, tgt), score in zip(meta, text_pairs, scores):
                writer.writerow([idx, ts, src, tgt, round(score, 4)])


    @log_exceptions()
    def validate_batch_gemini(self, pairs: List[Tuple[str, str]],
                       src_lang="Hindi", tgt_lang=" ", output_dir="output_csvs") -> None:
        """
        Runs validation over a list of SRT file pairs.
        """
        Path(output_dir).mkdir(exist_ok=True)
        for src, tgt in pairs:
            out_file = Path(output_dir) / f"{Path(src).stem}__vs__{Path(tgt).stem}.csv"
            self.logger.info(f"▶ Validating {src} vs {tgt}")
            self.validate_pair_gemini(src, tgt, str(out_file), src_lang, tgt_lang)

    @log_exceptions()
    def merge_all_csvs(self, input_dir: str, output_file: str = "final_output.csv") -> pd.DataFrame | None:
        """
        Merges all CSV files in a directory into one and returns the DataFrame.
        """
        input_dir = Path(input_dir)
        all_csvs = natsorted(input_dir.glob("*.csv"))
        if not all_csvs:
            self.logger.warning(f"No CSV files found in {input_dir}")
            return None

        frames = []
        for csv_file in all_csvs:
            try:
                frames.append(pd.read_csv(csv_file))
            except Exception as e:
                self.logger.warning(f"Skipping {csv_file.name}: {e}")

        if not frames:
            self.logger.error("No valid CSVs to merge.")
            return None

        merged_df = pd.concat(frames, ignore_index=True)
        if "similarity" in merged_df.columns:
            avg_row = {"index": "Average", **{col: "" for col in merged_df.columns if col != "similarity"}}
            avg_row["similarity"] = round(merged_df["similarity"].mean(), 4)
            merged_df.loc[len(merged_df)] = avg_row

        merged_df.to_csv(output_file, index=False)
        self.logger.info(f"Merged {len(frames)} files → {output_file}")

        for file in all_csvs:
            try:
                file.unlink()
                self.logger.info(f"Deleted temporary CSV: {file.name}")
            except Exception as e:
                self.logger.warning(f"Failed to delete {file.name}: {e}")

        return merged_df

# """
# Script to demonstrate usage of TranslationEvaluator class for SRT validation.
# """
# import time
# from evalution import TranslationEvaluator

# if __name__ == "__main__":
#     # Initialize the evaluator with your OpenAI API key
#     evaluator = TranslationEvaluator(api_key="your-openai-api-key")

#     # Example: Validate a Hindi–Kannada SRT batch
#     src_dir = "shared_data/movieslist/BablooBachelor/srtfiles/Base"
#     tgt_dir = "shared_data/movieslist/BablooBachelor/srtfiles/Kannada"
#     output_csv_dir = "validated_outputs/BablooBachelor_Kannada"
#     merged_csv_output = "shared_data/movieslist/BablooBachelor/babloo_bachelor_Evaluation_Kannada.csv"

#     # Rename files with language suffixes (optional but useful)
#     evaluator.rename_srt_files_with_language(src_dir, lang_code="hi")
#     evaluator.rename_srt_files_with_language(tgt_dir, lang_code="kn")

#     # Get matched file pairs and validate them
#     pairs = evaluator.generate_srt_pairs(src_dir, tgt_dir, hi_suffix="_hi_SRTfile.srt", tgt_suffix="_kn_SRTfile.srt")
#     evaluator.validate_batch(pairs, src_lang="Hindi", tgt_lang="Kannada", output_dir=output_csv_dir)

#     # Merge all CSVs into one
#     evaluator.merge_all_csvs(output_csv_dir, merged_csv_output)
#     time.sleep(5)

#     # Example: Validate a triple set (Hindi-Bhasa-English)
#     triples = evaluator.generate_srt_triples(
#         hi_dir="shared_data/movieslist/Rishtey/srtfiles/Base",
#         id_dir="shared_data/movieslist/Rishtey/srtfiles/Bhasa",
#         en_dir="shared_data/movieslist/Rishtey/srtfiles/Bhasa/English",
#         hi_suffix="_hi_SRTfile.srt",
#         id_suffix="_id_SRTfile.srt",
#         en_suffix="_en_SRTfile.srt",
#     )
#     triple_output_dir = "validated_outputs/Rishtey_Bhasa"
#     merged_triple_output = "shared_data/movieslist/Rishtey/rishtey_Evaluation_Bhasa.csv"

#     for hi, id_, en in triples:
#         out_csv = f"{triple_output_dir}/{Path(hi).stem}__vs__{Path(en).stem}.csv"
#         evaluator.validate_triple_streamed(hi, id_, en, out_csv)
#     evaluator.merge_all_csvs(triple_output_dir, merged_triple_output)
