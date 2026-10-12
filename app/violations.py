import threading
import uuid


class ViolationMonitor:
    def __init__(self, store, source, required_frames=15, session_id=None):
        self.store, self.source = store, source
        self.required_frames = required_frames
        self.session_id = session_id or str(uuid.uuid4())
        self.streaks = {}
        self.active = set()

    def update(self, tracks, frame):
        unique = {}
        for track in tracks:
            tid = int(track['track_id'])
            if tid in unique and unique[tid]['state'] != track['state']:
                unique[tid] = {**track, 'state': 'uncertain'}
            else:
                unique.setdefault(tid, track)
        tracks = list(unique.values())
        observed = {int(t['track_id']) for t in tracks}
        for tid in set(self.streaks) - observed:
            self.streaks[tid] = 0
        created = []
        for track in tracks:
            tid = int(track['track_id'])
            if track['state'] != 'head':
                self.streaks[tid] = 0
                continue
            self.streaks[tid] = self.streaks.get(tid, 0) + 1
            if self.streaks[tid] >= self.required_frames and tid not in self.active:
                event = self.store.create_event(self.session_id, tid, self.source, frame)
                self.active.add(tid)
                if event:
                    created.append(event)
        return created


def play_alarm(on_error=None):
    def sound():
        try:
            import winsound
            winsound.Beep(1300, 1000)
        except Exception:
            if on_error:
                on_error('Sesli uyarı çalınamadı. Yeni ihlal ekrandaki bildirimle gösteriliyor.')
    thread = threading.Thread(target=sound, daemon=True)
    thread.start()
    return thread
