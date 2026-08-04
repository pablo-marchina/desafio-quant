import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag.ingestion import NVIDIAKnowledgeIngestor


if __name__ == "__main__":
    report = NVIDIAKnowledgeIngestor().run()
    sys.stdout.buffer.write(
        (json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
