class DynamicLayoutManager:
    def __init__(self):
        self.mode = "tiling" # Default to tiling for prototype
        self.windows = []

    def add_window(self, window_id):
        if window_id not in self.windows:
            self.windows.append(window_id)
        return self.recalculate_layout()

    def remove_window(self, window_id):
        if window_id in self.windows:
            self.windows.remove(window_id)
        return self.recalculate_layout()

    def recalculate_layout(self):
        """
        Calculates window geometries. In the future, the Context Engine will
        provide hints (e.g. 'coding mode' -> prioritize terminal/editor).
        """
        count = len(self.windows)
        if count == 0:
            return {}
        if self.mode == "focus" or count == 1:
            return {window_id: {"x": 0, "y": 0, "width": 1, "height": 1} for window_id in self.windows}

        columns = 2 if count > 1 else 1
        rows = (count + columns - 1) // columns
        layout = {}
        for index, window_id in enumerate(self.windows):
            column = index % columns
            row = index // columns
            layout[window_id] = {
                "x": column / columns,
                "y": row / rows,
                "width": 1 / columns,
                "height": 1 / rows,
            }
        return layout
