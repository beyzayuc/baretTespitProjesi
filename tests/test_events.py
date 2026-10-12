from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from app.event_store import EventStore
from app.violations import ViolationMonitor, play_alarm
from app.tracking import associate_people


class IncidentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.time=datetime(2026,1,1,12)
        self.actor=('S-1-5-test-owner','PC/operator')
        self.store=EventStore(self.temp.name,backend='sqlite',identity=lambda:self.actor,clock=lambda:self.time)
        self.frame=np.zeros((60,80,3),np.uint8)
        self.monitor=ViolationMonitor(self.store,'Kamera 0',session_id='session-one')

    def tearDown(self):
        self.temp.cleanup()

    def observe(self,state='head',track=1):
        return self.monitor.update([{'track_id':track,'state':state,'box':[0,0,20,40]}],self.frame)

    def event(self):
        for _ in range(15): result=self.observe()
        return result[0]

    def test_exactly_15_then_one_event_per_track(self):
        for _ in range(14): self.assertEqual(self.observe(),[])
        self.assertEqual(len(self.observe()),1)
        for _ in range(90):self.assertEqual(self.observe(),[])
        rows=self.store.list_events()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'New')
        self.assertTrue(self.store.snapshot_file(rows[0]['snapshotPath']).is_file())

    def test_breaks_reset_consecutive_count(self):
        for state in ['helmet','uncertain','unknown',None]:
            self.monitor=ViolationMonitor(self.store,'test')
            for _ in range(14):self.observe()
            if state is None:self.monitor.update([],self.frame)
            else:self.observe(state)
            for _ in range(14):self.assertEqual(self.observe(),[])
            self.assertEqual(len(self.observe()),1)

    def test_tracks_do_not_share_streaks(self):
        for _ in range(14):self.observe(track=1)
        self.assertEqual(self.observe(track=2),[])
        self.assertEqual(self.observe(track=1),[])

    def test_false_alarm_deletes_only_image_keeps_review(self):
        event=self.event()
        path=self.store.snapshot_file(self.store.list_events()[0]['snapshotPath'])
        self.store.review(event['logId'],'False Alarm')
        row=self.store.list_events()[0]
        self.assertFalse(path.exists())
        self.assertIsNone(row['snapshotPath'])
        self.assertEqual(row['status'],'False Alarm')
        with self.store.transaction() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM ReviewHistory').fetchone()[0],1)
        for _ in range(30):self.assertEqual(self.observe(),[])

    def test_confirmed_expiry_uses_review_time(self):
        event=self.event();self.time+=timedelta(days=7)
        self.store.review(event['logId'],'Confirmed')
        self.time+=timedelta(days=29,hours=23,minutes=59)
        self.store.cleanup()
        self.assertIsNotNone(self.store.list_events()[0]['snapshotPath'])
        self.time+=timedelta(minutes=1)
        self.store.cleanup()
        self.assertIsNone(self.store.list_events()[0]['snapshotPath'])
        self.assertEqual(self.store.list_events()[0]['status'],'Confirmed')

    def test_new_images_do_not_expire(self):
        self.event();self.time+=timedelta(days=60);self.store.cleanup()
        self.assertIsNotNone(self.store.list_events()[0]['snapshotPath'])

    def test_unauthorized_review_and_list_denied(self):
        event=self.event();self.actor=('S-1-5-other','PC/other')
        with self.assertRaises(PermissionError):self.store.review(event['logId'],'False Alarm')
        with self.assertRaises(PermissionError):self.store.list_events()

    def test_finalized_event_cannot_be_rewritten(self):
        event=self.event();self.store.review(event['logId'],'Confirmed')
        with self.assertRaises(ValueError):self.store.review(event['logId'],'False Alarm')

    def test_new_session_same_track_id_is_independent(self):
        first=self.event();self.monitor=ViolationMonitor(self.store,'Kamera 0',session_id='session-two')
        second=self.event()
        self.assertNotEqual(first['logId'],second['logId'])
        self.assertEqual(len(self.store.list_events()),2)

    def test_duplicate_store_insert_is_idempotent(self):
        self.event()
        self.assertIsNone(self.store.create_event('session-one',1,'Kamera 0',self.frame))
        self.assertEqual(len(list(self.store.snapshots.glob('*.jpg'))),1)

    def test_failed_delete_retries_without_losing_review(self):
        event=self.event()
        with patch('pathlib.Path.unlink',side_effect=PermissionError('locked')):
            with self.assertRaises(RuntimeError):self.store.review(event['logId'],'False Alarm')
        self.assertEqual(self.store.list_events()[0]['status'],'False Alarm')
        self.store.cleanup()
        self.assertIsNone(self.store.list_events()[0]['snapshotPath'])

    def test_never_delete_outside_snapshot_directory(self):
        event=self.event()
        target=Path(self.temp.name)/'important.jpg';target.write_bytes(b'keep')
        with self.store.transaction() as c:
            c.execute('UPDATE OlayLoglari SET snapshotPath=? WHERE logId=?',('../important.jpg',event['logId']))
        with self.assertRaises(RuntimeError):self.store.review(event['logId'],'False Alarm')
        self.assertTrue(target.exists())

    def test_one_head_not_assigned_to_two_people(self):
        people=[{'track_id':1,'box':[0,0,100,200]},{'track_id':2,'box':[20,0,120,200]}]
        rows=associate_people(people,[{'class':'head','box':[30,10,70,60]}])
        self.assertEqual(sum(r['state']=='head' for r in rows),1)

    def test_alarm_duration_one_second(self):
        with patch('winsound.Beep') as beep:
            thread=play_alarm();thread.join(timeout=2)
            beep.assert_called_once_with(1300,1000)

    def test_duplicate_id_in_one_frame_counts_once(self):
        track={'track_id':1,'state':'head'}
        for _ in range(14):
            self.assertEqual(self.monitor.update([track,track],self.frame),[])
        self.assertEqual(len(self.monitor.update([track,track],self.frame)),1)

if __name__=='__main__':unittest.main()
