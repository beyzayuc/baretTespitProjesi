"""Durable incident storage with Windows-identity authorization and retention."""
from contextlib import contextmanager, closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import io
import json
import os
import sqlite3
import subprocess
import threading
import uuid


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def windows_identity():
    result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, text=True, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    account, sid = next(csv.reader(io.StringIO(result.stdout.strip())))[:2]
    if not sid.startswith('S-1-'):
        raise PermissionError('Windows kullanıcı kimliği doğrulanamadı.')
    return sid, account


SQL_SCHEMA = """
IF OBJECT_ID('dbo.Operators','U') IS NULL
CREATE TABLE dbo.Operators (sid NVARCHAR(184) PRIMARY KEY, accountName NVARCHAR(255) NOT NULL, enabled BIT NOT NULL DEFAULT 1);
IF OBJECT_ID('dbo.OlayLoglari','U') IS NULL
CREATE TABLE dbo.OlayLoglari (
 logId INT IDENTITY(1,1) PRIMARY KEY, trackId INT NOT NULL,
 sessionId VARCHAR(36) NOT NULL, timeStamp DATETIME2 NOT NULL,
 sourceName NVARCHAR(255) NOT NULL, violationType VARCHAR(50) NOT NULL,
 snapshotPath NVARCHAR(255) NULL, status VARCHAR(20) NOT NULL,
 reviewedAt DATETIME2 NULL, reviewedBy NVARCHAR(255) NULL,
 reviewedBySid NVARCHAR(184) NULL,
 CONSTRAINT UQ_OlaySessionTrack UNIQUE(sessionId, trackId),
 CONSTRAINT CK_OlayStatus CHECK(status IN ('New','Confirmed','False Alarm')));
IF OBJECT_ID('dbo.ReviewHistory','U') IS NULL
CREATE TABLE dbo.ReviewHistory (
 reviewId INT IDENTITY(1,1) PRIMARY KEY, logId INT NOT NULL REFERENCES dbo.OlayLoglari(logId),
 oldStatus VARCHAR(20) NOT NULL, newStatus VARCHAR(20) NOT NULL,
 reviewedAt DATETIME2 NOT NULL, reviewedBy NVARCHAR(255) NOT NULL, reviewedBySid NVARCHAR(184) NOT NULL);
"""
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS Operators(sid TEXT PRIMARY KEY, accountName TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS OlayLoglari (
 logId INTEGER PRIMARY KEY AUTOINCREMENT, trackId INTEGER NOT NULL,
 sessionId TEXT NOT NULL, timeStamp TEXT NOT NULL, sourceName TEXT NOT NULL,
 violationType TEXT NOT NULL, snapshotPath TEXT NULL,
 status TEXT NOT NULL CHECK(status IN ('New','Confirmed','False Alarm')),
 reviewedAt TEXT NULL, reviewedBy TEXT NULL, reviewedBySid TEXT NULL,
 UNIQUE(sessionId,trackId));
CREATE TABLE IF NOT EXISTS ReviewHistory(
 reviewId INTEGER PRIMARY KEY AUTOINCREMENT, logId INTEGER NOT NULL REFERENCES OlayLoglari(logId),
 oldStatus TEXT NOT NULL,newStatus TEXT NOT NULL,reviewedAt TEXT NOT NULL,
 reviewedBy TEXT NOT NULL,reviewedBySid TEXT NOT NULL);
"""


class EventStore:
    def __init__(self, root, backend='auto', identity=windows_identity, clock=utcnow):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots = self.root / 'snapshots'
        self.snapshots.mkdir(exist_ok=True)
        self.identity, self.clock = identity, clock
        self.lock = threading.RLock()
        self.warning = ''
        self.connection_string = None
        settings_path = self.root / 'storage.json'
        existing = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else None
        if existing and backend == 'auto':
            backend = existing['backend']
        if backend in ('auto', 'sqlserver'):
            import pyodbc
            drivers = pyodbc.drivers()
            driver = next((d for d in ['ODBC Driver 18 for SQL Server','ODBC Driver 17 for SQL Server','SQL Server'] if d in drivers), None)
            servers = [existing['server']] if existing and existing.get('server') else ['.', '.\\MSSQLSERVER01']
            for server in servers:
                try:
                    prefix = f'DRIVER={{{driver}}};SERVER={server};Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;'
                    with closing(pyodbc.connect(prefix + 'DATABASE=master;', timeout=2, autocommit=True)) as c:
                        c.execute("IF DB_ID(N'BaretTespitApp') IS NULL CREATE DATABASE [BaretTespitApp]")
                    self.connection_string = prefix + 'DATABASE=BaretTespitApp;'
                    with closing(pyodbc.connect(self.connection_string, timeout=2, autocommit=True)) as c:
                        c.execute(SQL_SCHEMA)
                    backend = 'sqlserver'
                    break
                except Exception:
                    self.connection_string = None
            if not self.connection_string:
                if backend == 'sqlserver':
                    raise RuntimeError('Kayıtlı SQL Server bağlantısı açılamadı. Olay kaybını önlemek için işlem başlatılmadı. SQL Server hizmetini ve Windows erişimini kontrol edin.')
                backend = 'sqlite'
                self.warning = 'SQL Server bağlantısı kurulamadı; olaylar bu bilgisayardaki SQLite veritabanına kaydediliyor.'
        self.backend = backend
        if self.backend == 'sqlite':
            with closing(sqlite3.connect(self.root / 'events.db')) as c:
                c.executescript(SQLITE_SCHEMA)
        if not existing:
            settings_path.write_text(json.dumps({'backend': backend, 'server': server if self.connection_string else None}, indent=2), encoding='utf-8')
        with self.transaction() as c:
            if c.execute('SELECT COUNT(*) FROM Operators').fetchone()[0] == 0:
                sid, name = self.identity()
                c.execute('INSERT INTO Operators(sid,accountName,enabled) VALUES (?,?,1)', (sid, name))

    @contextmanager
    def transaction(self):
        with self.lock:
            if self.backend == 'sqlite':
                connection = sqlite3.connect(self.root / 'events.db', timeout=30)
                connection.execute('PRAGMA foreign_keys=ON')
            else:
                import pyodbc
                connection = pyodbc.connect(self.connection_string, timeout=5)
            try:
                yield connection.cursor()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def authorized(self):
        sid, _ = self.identity()
        with self.transaction() as c:
            row = c.execute('SELECT enabled FROM Operators WHERE sid=?', (sid,)).fetchone()
        return bool(row and row[0])

    def require_operator(self):
        if not self.authorized():
            raise PermissionError('Bu Windows hesabı olay incelemesi için yetkili değil.')
        return self.identity()

    @staticmethod
    def rows(cursor):
        keys = [d[0] for d in cursor.description]
        return [dict(zip(keys, row)) for row in cursor.fetchall()]

    def create_event(self, session_id, track_id, source, frame):
        from .engine import save_image
        with self.lock:
            with self.transaction() as c:
                row = c.execute('SELECT logId FROM OlayLoglari WHERE sessionId=? AND trackId=?', (session_id, track_id)).fetchone()
            if row:
                return None
            relative = 'snapshots/' + uuid.uuid4().hex + '.jpg'
            path = self.snapshot_file(relative)
            try:
                save_image(path, frame)
                with self.transaction() as c:
                    c.execute('INSERT INTO OlayLoglari(trackId,sessionId,timeStamp,sourceName,violationType,snapshotPath,status) VALUES (?,?,?,?,?,?,?)', (track_id,session_id,self.clock().isoformat(),str(source)[:255],'Helmet Violation',relative,'New'))
                    log_id = c.execute('SELECT logId FROM OlayLoglari WHERE sessionId=? AND trackId=?', (session_id,track_id)).fetchone()[0]
                return {'logId':log_id,'trackId':track_id,'status':'New'}
            except Exception:
                path.unlink(missing_ok=True)
                with self.transaction() as c:
                    row = c.execute('SELECT logId FROM OlayLoglari WHERE sessionId=? AND trackId=?',(session_id,track_id)).fetchone()
                if row:
                    return None
                raise

    def list_events(self):
        self.require_operator()
        with self.transaction() as c:
            return self.rows(c.execute("SELECT * FROM OlayLoglari ORDER BY CASE WHEN status='New' THEN 0 ELSE 1 END, timeStamp DESC"))

    def snapshot_file(self, relative):
        if not relative:
            return None
        path = (self.root / relative).resolve()
        if path.parent != self.root / 'snapshots' or path.suffix.lower() != '.jpg':
            raise ValueError('Olay görüntüsü izin verilen klasörün dışında.')
        return path

    def review(self, log_id, new_status):
        if new_status not in ('Confirmed', 'False Alarm'):
            raise ValueError('İnceleme sonucu Confirmed veya False Alarm olmalı.')
        sid, account = self.require_operator()
        now = self.clock().isoformat()
        with self.transaction() as c:
            c.execute('UPDATE OlayLoglari SET status=?,reviewedAt=?,reviewedBy=?,reviewedBySid=? WHERE logId=? AND status=?', (new_status,now,account,sid,log_id,'New'))
            if c.rowcount != 1:
                raise ValueError('Bu kayıt zaten sonlandırılmış veya bulunamadı.')
            c.execute('INSERT INTO ReviewHistory(logId,oldStatus,newStatus,reviewedAt,reviewedBy,reviewedBySid) VALUES (?,?,?,?,?,?)', (log_id,'New',new_status,now,account,sid))
        # Commit the review first; deletion failures remain retryable by cleanup.
        self.cleanup()

    def cleanup(self):
        cutoff = (self.clock() - timedelta(days=30)).isoformat()
        with self.transaction() as c:
            rows = self.rows(c.execute("SELECT logId,snapshotPath FROM OlayLoglari WHERE snapshotPath IS NOT NULL AND (status='False Alarm' OR (status='Confirmed' AND reviewedAt<=?))", (cutoff,)))
        failures = []
        for row in rows:
            try:
                path = self.snapshot_file(row['snapshotPath'])
                path.unlink(missing_ok=True)
                with self.transaction() as c:
                    c.execute('UPDATE OlayLoglari SET snapshotPath=NULL WHERE logId=? AND snapshotPath=?', (row['logId'], row['snapshotPath']))
            except (OSError, ValueError) as exc:
                failures.append(f"Olay {row['logId']}: görüntü silinemedi veya güvenli konumda değil.")
        if failures:
            raise RuntimeError('Görüntü temizliği yeniden denenecek. ' + '; '.join(failures))
