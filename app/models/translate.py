import re, os
import requests
from openai import OpenAI
from utils.logger import SingletonLogger, log_exceptions
from utils.config import get_settings
from google.cloud import translate_v3 as translate
local_settings = get_settings()


class TranslationUtils:
    """
    Utility class providing functions for translation, text formatting,
    subtitle file generation, and text wrapping for subtitles.
    """

    def __init__(self):
        """
        Initializes the TranslationUtils with OpenAI and Google API keys.
        
        Args:
            openai_key (str): API key for OpenAI GPT model.
            google_key (str): API key for Google Translate API.
        """
        self.logger = SingletonLogger.getInstance("TranslationUtils").logger
        self.openai_client = OpenAI(api_key=local_settings.openai_key)
        # self.google_key = local_settings.google_translate_key
        creds_path = local_settings.google_credentials_path
        if creds_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        self.google_client = translate.TranslationServiceClient()

    @log_exceptions("OpenAI translation failed")
    def translate_text_openai(self, text: str, target_language: str) -> str:
        """
        Translate Hindi text to target language using OpenAI GPT model.

        Args:
            text (str): Hindi input text to translate.
            target_language (str): Target language for translation.

        Returns:
            str: Translated output.
        """
        prompt = """Translate only the Hindi text into {target_language}. 
        Only return plain translated text. 
        Do NOT include any extra formatting, explanations, or foreign scripts. 
        Return in a single language only: {target_language}. 
        No code, no markdown. If unsure, translate literally.

        Hindi text:
        {text.strip()}"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are a precise and professional translator. "
                    "Translate the user's Hindi input into the requested language. "
                    "Output only the translated text, with no extra comments, formatting, or scripts outside the target language."
                )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        output = response.choices[0].message.content.strip()

        if output.startswith("```") and "```" in output[3:]:
            output = output.strip("`").split("\\n", 1)[-1].rsplit("```", 1)[0].strip()

        return re.sub(r'\\b(\\w+)( \\1){2,}', r'\\1 \\1', output)
    
    @log_exceptions("OpenAI batch translation failed")
    def translate_batch_openai(self, texts: list[str], target_language: str) -> list[str]:
        """
        Translate a batch of Hindi texts using OpenAI GPT.

        Args:
            texts (List[str]): List of Hindi subtitle lines.
            target_language (str): Target language.

        Returns:
            List[str]: Translated lines in order.
        """
        numbered_text = "\n".join([f"{i + 1}. {line.strip()}" for i, line in enumerate(texts)])

        prompt = f"""Translate the following numbered Hindi subtitle lines into {target_language}. 
        Return only the translated lines, in the same numbered order. Do not add any extra text or formatting.

        Hindi lines:
        {numbered_text}
        """

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are a precise subtitle translator. Translate only the Hindi lines provided into the target language, "
                    "preserving order and tone. Do not add explanations, comments, or code formatting."
                )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        output = response.choices[0].message.content.strip()

        # Extract numbered translations
        translated_lines = []
        for line in output.splitlines():
            match = re.match(r"^\d+\.\s*(.+)$", line.strip())
            if match:
                translated_lines.append(match.group(1).strip())
            else:
                # fallback if unnumbered or broken format
                translated_lines.append(line.strip())

        # Ensure it matches expected size
        if len(translated_lines) != len(texts):
            print("⚠️ Line mismatch. Falling back to individual translation.")
            return [self.translate_text_openai(t, target_language) for t in texts]

        return translated_lines
        
    @log_exceptions("Google Cloud batch translation failed")
    def translate_batch_google(self,
                            texts: list[str],
                            target_language: str,
                            source_language: str = "hi",
                            glossary_id: str = None) -> list[str]:
        """
        Translate a batch of texts using Google Cloud Translate API v3 with optional glossary support.

        Args:
            texts (List[str]): List of input subtitle lines.
            target_language (str): Language code to translate to (e.g., 'en', 'hi').
            source_language (str): Language code of source (default = 'auto').
            glossary_id (str): Optional glossary ID.

        Returns:
            List[str]: Translated texts.
        """
        try:
            client = translate.TranslationServiceClient()
            project_id = "nimixitsubtitling"  # ← replace with your actual GCP project ID
            parent = f"projects/{project_id}/locations/global"

            request = {
                "parent": parent,
                "contents": texts,
                "mime_type": "text/plain",
                "source_language_code": source_language,
                "target_language_code": target_language
            }

            if glossary_id:
                glossary_path = f"{parent}/glossaries/{glossary_id}"
                request["glossary_config"] = translate.TranslateTextGlossaryConfig(
                    glossary=glossary_path
                )

            response = client.translate_text(request=request)

            if glossary_id:
                return [t.translated_text for t in response.glossary_translations]
            else:
                return [t.translated_text for t in response.translations]

        except Exception as e:
            print(f"⚠️ Google Cloud batch translation error: {e}")
            # fallback to single-line translation
            return [self.translate_text_google(t, target_language, source_language, glossary_id) for t in texts]

    @log_exceptions("Google Cloud single-line translation failed")
    def translate_text_google(self, text: str, target_language: str, source_language: str = "hi", glossary_id: str = None) -> str:
        """
        Translate a single line of text using Google Cloud Translate API v3 with optional glossary support.

        Args:
            text (str): Text to translate.
            target_language (str): Target language code (e.g., 'kn', 'en').
            source_language (str): Source language code (default: 'auto').
            glossary_id (str): Optional glossary ID for domain-specific terms.

        Returns:
            str: Translated text.
        """
        try:
            client = translate.TranslationServiceClient()
            project_id = "nimixitsubtitling"  # 🔁 Replace with your actual GCP project ID
            parent = f"projects/{project_id}/locations/global"

            # Base translation config
            request = {
                "contents": [text],
                "target_language_code": target_language,
                "source_language_code": source_language,
                "parent": parent,
                "mime_type": "text/plain",
            }

            # Attach glossary config if glossary_id is provided
            if glossary_id:
                glossary_path = f"{parent}/glossaries/{glossary_id}"
                request["glossary_config"] = translate.TranslateTextGlossaryConfig(
                    glossary=glossary_path
                )

            response = client.translate_text(request=request)

            if glossary_id:
                return response.glossary_translations[0].translated_text
            else:
                return response.translations[0].translated_text

        except Exception as e:
            print(f"❌ Failed to translate: {text[:30]}... - Error: {e}")
            return text
