"""Prevent two runtimes from executing the same durable schedules."""
import os


class InstanceLock:
    def __init__(self, path):
        self.path, self.handle = path, None

    def acquire(self):
        handle = open(self.path, "a+b")
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise RuntimeError("June is already running for this data directory")
        self.handle = handle

    def release(self):
        if self.handle:
            self.handle.close()
            self.handle = None
