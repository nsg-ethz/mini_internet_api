import threading


class Link_Lock:
    def __init__(self):
        # We need two locks to ensure that a elementary loss event doesn't get interrupted by undoing a chaos monkey event

        # The active lock is used to ensure that we don't have multiple chaos monkey events running at the same time
        self.in_use_lock = threading.Lock()
        # The modify_lock is used when actually modifying the link state
        self.modify_lock = threading.Lock()

    def acquire_in_use(self):
        return self.in_use_lock.acquire(blocking=False)

    def release_in_use(self):
        self.in_use_lock.release()

    def acquire_modify(self):
        # Modifying should be quick so no need to not block
        self.modify_lock.acquire()

    def release_modify(self):
        self.modify_lock.release()