"""Read only June's SAPI session peak; never capture or retain audio samples."""
import threading
import time


class OutputMeter:
    def __init__(self, pid):
        self.pid = pid
        self.level = None
        self.source = 'unavailable; speaking follows SAPI engine state'
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, name='June output level', daemon=True)
        self.thread.start()

    def _run(self):
        initialized = False
        meter = None
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
            comtypes.CoInitialize()
            initialized = True
            next_search = 0
            while not self.stopped.is_set():
                if meter is None and time.monotonic() >= next_search:
                    next_search = time.monotonic() + 1
                    session = AudioUtilities.GetProcessSession(self.pid)
                    if session is not None:
                        meter = session._ctl.QueryInterface(IAudioMeterInformation)
                        self.source = 'Windows Core Audio peak for June speech process'
                if meter is not None:
                    self.level = max(0., min(1., float(meter.GetPeakValue())))
                self.stopped.wait(.05 if meter is not None else .25)
        except Exception:
            self.source = 'unavailable; speaking follows SAPI engine state'
        finally:
            self.level = None
            meter = None
            if initialized:
                comtypes.CoUninitialize()

    def stop(self):
        self.stopped.set()
        self.level = None
