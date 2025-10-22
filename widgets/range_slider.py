# EthoGrid_App/widgets/range_slider.py

from PyQt5 import QtWidgets, QtCore, QtGui
from widgets.base_dialog import BaseDialog 

class RangeSlider(BaseDialog):
    """ A custom double-ended slider widget for selecting a range with value labels. """
    valuesChanged = QtCore.pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_val, self.max_val = 0, 100
        self.low_val, self.high_val = 33, 67
        self.first_handle_pressed = False
        self.second_handle_pressed = False
        self.handle_width = 20
        self.setMinimumHeight(40)
        
        self.first_handle_rect = QtCore.QRect()
        self.second_handle_rect = QtCore.QRect()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        slider_y_offset = 20
        track_rect = self.rect().adjusted(self.handle_width // 2, slider_y_offset, -self.handle_width // 2, -self.height() + slider_y_offset + 6)
        painter.setPen(QtCore.Qt.NoPen); painter.setBrush(QtGui.QColor("#3a3a3a")); painter.drawRoundedRect(track_rect, 3, 3)
        
        low_pos = int(self._value_to_pos(self.low_val)); high_pos = int(self._value_to_pos(self.high_val))
        
        painter.setBrush(QtGui.QColor(31, 119, 180, 180))
        zone1_rect = QtCore.QRectF(track_rect.left(), track_rect.top(), low_pos - track_rect.left(), track_rect.height())
        painter.drawRoundedRect(zone1_rect, 3, 3)
        
        painter.setBrush(QtGui.QColor(214, 39, 40, 180))
        zone2_rect = QtCore.QRectF(high_pos, track_rect.top(), track_rect.right() - high_pos, track_rect.height())
        painter.drawRoundedRect(zone2_rect, 3, 3)
        
        painter.setBrush(QtGui.QColor("#e0e0e0")); painter.setPen(QtGui.QColor("#c0c0c0"))
        self.first_handle_rect = QtCore.QRect(low_pos - self.handle_width // 2, slider_y_offset - self.handle_width // 2 + 3, self.handle_width, self.handle_width)
        self.second_handle_rect = QtCore.QRect(high_pos - self.handle_width // 2, slider_y_offset - self.handle_width // 2 + 3, self.handle_width, self.handle_width)
        painter.drawEllipse(self.first_handle_rect); painter.drawEllipse(self.second_handle_rect)
        
        painter.setPen(QtGui.QColor("#e0e0e0")); font = painter.font(); font.setPixelSize(12); font.setBold(True); painter.setFont(font)
        low_text = f"{self.getValues()[0]}%"; high_text = f"{self.getValues()[1]}%"; middle_val = 100 - (self.getValues()[0] + self.getValues()[1]); middle_text = f"{middle_val}%"
        painter.drawText(QtCore.QRect(0, 0, low_pos, slider_y_offset), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, low_text)
        painter.drawText(QtCore.QRect(high_pos, 0, self.width() - high_pos, slider_y_offset), QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, high_text)
        if middle_val >= 0: painter.drawText(QtCore.QRect(low_pos, 0, high_pos - low_pos, slider_y_offset), QtCore.Qt.AlignCenter, middle_text)

    def _value_to_pos(self, value):
        track_width = self.width() - self.handle_width
        return (value - self.min_val) / (self.max_val - self.min_val) * track_width + self.handle_width // 2

    def _pos_to_value(self, pos):
        track_width = self.width() - self.handle_width
        value = self.min_val + (pos - self.handle_width // 2) / track_width * (self.max_val - self.min_val)
        return int(max(self.min_val, min(self.max_val, value)))

    def mousePressEvent(self, event):
        if self.first_handle_rect.contains(event.pos()): self.first_handle_pressed = True
        elif self.second_handle_rect.contains(event.pos()): self.second_handle_pressed = True
        self.update()

    def mouseMoveEvent(self, event):
        if self.first_handle_pressed:
            new_val = self._pos_to_value(event.pos().x())
            if new_val <= self.high_val: # Use <= to allow handles to meet
                self.low_val = new_val
                self.valuesChanged.emit(self.getValues()[0], self.getValues()[1])
        elif self.second_handle_pressed:
            new_val = self._pos_to_value(event.pos().x())
            if new_val >= self.low_val: # Use >= to allow handles to meet
                self.high_val = new_val
                self.valuesChanged.emit(self.getValues()[0], self.getValues()[1])
        self.update()

    def mouseReleaseEvent(self, event):
        self.first_handle_pressed = False; self.second_handle_pressed = False
        self.update()

    def setValues(self, low_percent, high_percent):
        self.low_val = low_percent; self.high_val = 100 - high_percent
        self.update(); self.valuesChanged.emit(self.getValues()[0], self.getValues()[1])

    def getValues(self):
        return self.low_val, 100 - self.high_val