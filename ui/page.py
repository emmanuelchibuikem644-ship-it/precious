from tkinter import ttk


class Page(ttk.Frame):
    """Base class for every screen in the content area."""

    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame")
        self.app = app
        self.build()

    def build(self):
        raise NotImplementedError

    def on_show(self):
        pass

    def on_hide(self):
        pass

    @property
    def is_admin(self) -> bool:
        return self.app.user["role"] == "admin"
