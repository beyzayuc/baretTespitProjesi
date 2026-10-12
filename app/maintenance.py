import hashlib
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from .event_store import windows_identity


def register_cleanup(project):
    """Hourly task, current Windows operator only, no elevated privileges."""
    project=Path(project).resolve()
    name='BaretTespitCleanup_' + hashlib.sha256(str(project).encode()).hexdigest()[:10]
    sid,_=windows_identity()
    executable=Path(sys.executable).with_name('pythonw.exe')
    if not executable.exists():executable=Path(sys.executable)
    start=(datetime.now()+timedelta(minutes=1)).isoformat(timespec='seconds')
    xml=f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
 <Triggers><TimeTrigger><Repetition><Interval>PT1H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition><StartBoundary>{start}</StartBoundary><Enabled>true</Enabled></TimeTrigger></Triggers>
 <Principals><Principal id="Operator"><UserId>{escape(sid)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
 <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled><ExecutionTimeLimit>PT10M</ExecutionTimeLimit></Settings>
 <Actions Context="Operator"><Exec><Command>{escape(str(executable))}</Command><Arguments>{escape(subprocess.list2cmdline([str(project/'maintenance.py')]))}</Arguments><WorkingDirectory>{escape(str(project))}</WorkingDirectory></Exec></Actions>
</Task>'''
    xml_path=project/'data'/'cleanup_task.xml'
    xml_path.write_text(xml,encoding='utf-16')
    result=subprocess.run(['schtasks','/Create','/TN',name,'/XML',str(xml_path),'/F'],capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        return 'Zamanlanmış temizlik kurulamadı; görüntü temizliği uygulama açıkken ve sonraki açılışta yapılacak.'
    return None
