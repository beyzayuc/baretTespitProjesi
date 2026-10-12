from pathlib import Path
from app.event_store import EventStore

if __name__ == '__main__':
    root=Path(__file__).resolve().parent/'data'
    if (root/'storage.json').exists():
        try:
            EventStore(root).cleanup()
        except Exception as exc:
            (root/'maintenance_error.txt').write_text(str(exc),encoding='utf-8')
            raise
