# EthoGrid_App/widgets/base_dialog.py

from PyQt5 import QtWidgets, QtCore

class BaseDialog(QtWidgets.QDialog):
    """
    A custom base QDialog class for all dialogs in EthoGrid.
    
    Its primary purpose is to disable the default behavior of the Escape key,
    preventing accidental closure of long-running task dialogs.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event):
        """
        Overrides the default key press event handler.
        """
        # If the Escape key is pressed, we "accept" the event to consume it,
        # but we do nothing. This stops it from propagating and triggering
        # the dialog's reject() slot.
        if event.key() == QtCore.Qt.Key_Escape:
            event.accept()
        else:
            # For all other keys, we let the default behavior happen.
            super().keyPressEvent(event)