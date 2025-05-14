import threading
import time

class PortManager:
    def __init__(self, start_port, end_port):
        self.free_ports = set(range(start_port, end_port + 1))
        self.lock = threading.Lock()  # To ensure thread safety

    def get_port(self, duration=None):
        """
        Get a free port. If a duration is specified, the port will be automatically returned after the duration.
        """
        with self.lock:
            if not self.free_ports:
                return False
            port = self.free_ports.pop()

        # Schedule the port to be returned after the specified duration
        if duration is not None:
            threading.Timer(duration, self.return_port, args=(port,)).start()

        return port

    def return_port(self, port):
        """
        Return a port back to the pool.
        """
        with self.lock:
            self.free_ports.add(port)
            print(f"Port {port} returned to the pool.")
