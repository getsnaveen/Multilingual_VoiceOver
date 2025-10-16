import re
from typing import List, Tuple
from utils.logger import SingletonLogger, log_exceptions

class SRTTranslator:
    """
    A utility class for parsing, translating, and writing SRT subtitle files
    using a provided translator that supports OpenAI-based translation methods.
    """

    def __init__(self, translator, logger=None):
        """
        Initialize the SRTTranslator class.

        Args:
            translator: An instance with `translate_text_openai()` and `translate_batch_openai()` methods.
            logger: Optional custom logger. If not provided, a singleton logger will be used.
        """
        self.translator = translator
        self.logger = SingletonLogger.getInstance("SRTTranslator").logger        

    @log_exceptions("Failed to parse SRT file")
    def parse_srt_file(self, path: str) -> List[Tuple[int, str, str, str]]:
        """
        Parse a .srt file into structured subtitle segments.

        Args:
            path (str): Path to the .srt file.

        Returns:
            List[Tuple[int, str, str, str]]: List of subtitle entries with index, start time, end time, and text.
        """
        blocks = []
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        for block in re.split(r"\n\n+", content):
            lines = block.strip().splitlines()
            if len(lines) >= 3:
                idx = int(lines[0].strip())
                times = lines[1].strip()
                text = "\n".join(lines[2:]).strip()
                start_time, end_time = times.split(" --> ")
                blocks.append((idx, start_time.strip(), end_time.strip(), text))
        return blocks

    @log_exceptions("Failed to write SRT file")
    def write_srt_file(self, path: str, blocks: List[Tuple[int, str, str, str]]):
        """
        Write subtitle segments into an .srt file.

        Args:
            path (str): Path to the output .srt file.
            blocks (List[Tuple[int, str, str, str]]): List of tuples with index, start, end, and translated text.
        """
        with open(path, "w", encoding="utf-8") as f:
            for idx, start, end, text in blocks:
                f.write(f"{idx}\n{start} --> {end}\n{text.strip()}\n\n")

    @log_exceptions("Failed to translate SRT file (single line mode)")
    def translate_srt_file_with_openai(self, input_path: str, output_path: str, target_language: str):
        """
        Translate each subtitle line individually using the translator and save to a new .srt file.

        Args:
            input_path (str): Path to the input .srt file.
            output_path (str): Path to save the translated .srt file.
            target_language (str): Language to translate the text into.
        """
        srt_blocks = self.parse_srt_file(input_path)
        translated_blocks = []

        for idx, start, end, original_text in srt_blocks:
            self.logger.info(f"🔁 Translating segment and original_text {idx}...{original_text}")
            try:
                translated_text = self.translator.translate_text_openai(original_text, target_language, "hi")
                self.logger.info(f"🔁 Translated text ...{translated_text}")
            except Exception as e:
                self.logger.warning(f"❌ Failed to translate segment {idx}: {e}")
                translated_text = original_text
            translated_blocks.append((idx, start, end, translated_text))

        self.write_srt_file(output_path, translated_blocks)
        self.logger.info(f"✅ Translated SRT saved to: {output_path}")

    @log_exceptions("Failed to translate SRT file (batch mode)")
    def translate_srt_file_batch_with_openai(self, input_path: str, output_path: str, target_language: str, batch_size: int = 10):
        """
        Translate subtitle lines in batches using the translator and save to a new .srt file.

        Args:
            input_path (str): Path to the input .srt file.
            output_path (str): Path to the output .srt file.
            target_language (str): Language to translate the text into.
            batch_size (int): Number of lines to include per batch translation.
        """
        srt_blocks = self.parse_srt_file(input_path)
        translated_blocks = []

        for i in range(0, len(srt_blocks), batch_size):
            batch = srt_blocks[i:i + batch_size]
            texts = [block[3] for block in batch]
            self.logger.info(f"🔁 Translating batch {i // batch_size + 1}...")

            try:
                translated_texts = self.translator.translate_batch_openai(texts, target_language)
                self.logger.info(f"🔁 Translated text ...{translated_texts}")
            except Exception as e:
                self.logger.warning(f"❌ Batch translation failed: {e}")
                translated_texts = texts  # fallback

            for (idx, start, end, _), translated_text in zip(batch, translated_texts):
                translated_blocks.append((idx, start, end, translated_text))

        self.write_srt_file(output_path, translated_blocks)
        self.logger.info(f"✅ Translated SRT saved to: {output_path}")

    @log_exceptions("Failed to translate SRT file (single line mode)")
    def translate_srt_file_with_google_translate(self, input_path: str, output_path: str, target_language: str):
        """
        Translate each subtitle line individually using the translator and save to a new .srt file.

        Args:
            input_path (str): Path to the input .srt file.
            output_path (str): Path to save the translated .srt file.
            target_language (str): Language to translate the text into.
        """
        srt_blocks = self.parse_srt_file(input_path)
        translated_blocks = []

        for idx, start, end, original_text in srt_blocks:
            self.logger.info(f"🔁 Translating segment and original_text {idx}...{original_text}")
            try:
                translated_text = self.translator.translate_text_google(original_text, target_language)
                self.logger.info(f"🔁 Translated text ...{translated_text}")
            except Exception as e:
                self.logger.warning(f"❌ Failed to translate segment {idx}: {e}")
                translated_text = original_text
            translated_blocks.append((idx, start, end, translated_text))

        self.write_srt_file(output_path, translated_blocks)
        self.logger.info(f"✅ Translated SRT saved to: {output_path}")

    @log_exceptions("Failed to translate SRT file (batch mode)")
    def translate_srt_file_batch_with_google_translate(self, input_path: str, output_path: str, target_language: str, batch_size: int = 10):
        """
        Translate subtitle lines in batches using the translator and save to a new .srt file.

        Args:
            input_path (str): Path to the input .srt file.
            output_path (str): Path to the output .srt file.
            target_language (str): Language to translate the text into.
            batch_size (int): Number of lines to include per batch translation.
        """
        srt_blocks = self.parse_srt_file(input_path)
        translated_blocks = []

        for i in range(0, len(srt_blocks), batch_size):
            batch = srt_blocks[i:i + batch_size]
            texts = [block[3] for block in batch]
            self.logger.info(f"🔁 Translating batch {i // batch_size + 1}...")

            try:
                translated_texts = self.translator.translate_batch_google(texts, target_language)
                self.logger.info(f"🔁 Translated text ...{translated_texts}")
            except Exception as e:
                self.logger.warning(f"❌ Batch translation failed: {e}")
                translated_texts = texts  # fallback

            for (idx, start, end, _), translated_text in zip(batch, translated_texts):
                translated_blocks.append((idx, start, end, translated_text))

        self.write_srt_file(output_path, translated_blocks)
        self.logger.info(f"✅ Translated SRT saved to: {output_path}")
