# EthoGrid_App/widgets/custom_widgets.py

from PyQt5 import QtWidgets

class CustomSpinBox(QtWidgets.QSpinBox):
    """
    A QSpinBox subclass that disables changing the value with the mouse scroll wheel.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def wheelEvent(self, event):
        # Ignore the scroll wheel event to prevent value changes
        event.ignore()

class CustomDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """
    A QDoubleSpinBox subclass that disables changing the value with the mouse scroll wheel.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def wheelEvent(self, event):
        # Ignore the scroll wheel event to prevent value changes
        event.ignore()