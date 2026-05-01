class DynamicLayoutManager:
    def __init__(self):
        self.mode = "tiling" # Default to tiling for prototype
        self.windows = []

    def add_window(self, window_id):
        self.windows.append(window_id)
        self.recalculate_layout()

    def recalculate_layout(self):
        """
        Calculates window geometries. In the future, the Context Engine will
        provide hints (e.g. 'coding mode' -> prioritize terminal/editor).
        """
        pass
