
class UndoEvent:
    def __init__(self, unroll_time, action, args):
        self.unroll_time = unroll_time  # Timestamp when the event should be unrolled
        self.action = action  # Function to execute
        self.args = args  # Arguments for the function

    def __lt__(self, other):
        # Compare events based on unroll time
        return self.unroll_time < other.unroll_time
