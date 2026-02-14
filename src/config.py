from dataclasses import dataclass
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

@dataclass(frozen=True)
class Settings:
    client_id: int
    client_secret: str
    verify_token: str
    callback_url: str
    redirect_uri: str
    db_path: str
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    pdf_output_dir: str = "./pdfs"
    # New: markdown report output dir (defaults to PDF_OUTPUT_DIR for backwards compatibility)
    report_output_dir: str = "./pdfs"

def get_settings() -> Settings:
    pdf_output_dir = os.environ.get("PDF_OUTPUT_DIR", "./pdfs")
    report_output_dir = os.environ.get("REPORT_OUTPUT_DIR") or pdf_output_dir
    return Settings(
        client_id=int(os.environ["STRAVA_CLIENT_ID"]),
        client_secret=os.environ["STRAVA_CLIENT_SECRET"],
        verify_token=os.environ["STRAVA_VERIFY_TOKEN"],
        callback_url=os.environ.get("STRAVA_CALLBACK_URL", ""),
        redirect_uri=os.environ.get("STRAVA_REDIRECT_URI", "http://localhost:8787/callback"),
        db_path=os.environ.get("DB_PATH", "./db/strava.sqlite"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        pdf_output_dir=pdf_output_dir,
        report_output_dir=report_output_dir,
    )
