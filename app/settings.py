"""Operator-independent application settings."""
import json
from pathlib import Path


def load_confidence(path=None):
    path = Path(path) if path is not None else Path(__file__).resolve().parent.parent / 'settings.json'
    if not path.exists():
        return 0.5
    try:
        settings = json.loads(path.read_text(encoding='utf-8-sig'))
        value = settings.get('confidence', 0.5)
    except (ValueError, AttributeError) as exc:
        raise ValueError('settings.json geçerli bir JSON ayar dosyası olmalı.') from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
        raise ValueError('settings.json içindeki confidence değeri 0’dan büyük, en fazla 1 olan bir sayı olmalı.')
    return float(value)
