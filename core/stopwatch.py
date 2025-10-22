# EthoGrid_App/core/stopwatch.py

import time

class Stopwatch:
    def __init__(self):
        self.start_time = None
        self.elapsed_time = 0

    def start(self):
        """Starts or resets the stopwatch."""
        self.start_time = time.time()
        self.elapsed_time = 0

    def get_elapsed_time(self, as_float=False):
        """
        Returns the total elapsed time.
        
        Args:
            as_float (bool): If True, returns raw seconds. Otherwise, returns formatted string.
        """
        if self.start_time is None:
            return 0.0 if as_float else "00:00:00"
        
        self.elapsed_time = time.time() - self.start_time
        
        if as_float:
            return self.elapsed_time
        else:
            return self.format_time(self.elapsed_time)

    def get_etr(self, current_progress, total_progress):
        """
        Calculates the Estimated Time Remaining (ETR).
        """
        if self.start_time is None or current_progress <= 1 or total_progress == 0:
            return "--:--:--"

        # Use the internally stored elapsed time, which is updated by get_elapsed_time
        if self.elapsed_time < 0.1: # Avoid division by zero on the first few frames
            return "--:--:--"
            
        rate = current_progress / self.elapsed_time
        if rate == 0:
            return "--:--:--"

        remaining_items = total_progress - current_progress
        remaining_seconds = remaining_items / rate
        
        return self.format_time(remaining_seconds)

    @staticmethod
    def format_time(seconds):
        """Formats a duration in seconds into a HH:MM:SS string."""
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"