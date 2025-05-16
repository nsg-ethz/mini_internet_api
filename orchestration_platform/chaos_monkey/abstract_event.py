import random
from abc import ABC, abstractmethod


class AbstractEvent(ABC):
    def __init__(self, min_duration: int, max_duration: int):
        self.min_duration = min_duration
        self.max_duration = max_duration

    @abstractmethod
    def execute(self, rng: random.Random):
        """
        Abstract method to execute the event. Must be implemented by subclasses.
        """
        pass

    def get_average_duration(self) -> float:
        """
        Calculate the average duration of the event.
        """
        return (self.min_duration + self.max_duration) / 2
