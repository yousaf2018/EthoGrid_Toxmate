# EthoGrid_App/widgets/timeline_widget.py

from PyQt5 import QtWidgets, QtGui, QtCore

class TimelineWidget(QtWidgets.QWidget):
    """
    A custom widget to display behavior timelines for multiple tanks.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.timeline_segments = {}
        self.behavior_colors = {}
        self.total_frames = 0
        self.current_frame = 0
        self.num_tanks = 0

    def setData(self, timeline_segments, behavior_colors, total_frames, num_tanks):
        self.timeline_segments = timeline_segments
        self.behavior_colors = behavior_colors
        self.total_frames = total_frames
        self.num_tanks = num_tanks
        if self.num_tanks > 0:
            self.setMinimumHeight(max(40, self.num_tanks * 12 + 20))
            self.setMaximumHeight(self.num_tanks * 12 + 20)
        else:
            self.setMinimumHeight(0)
        self.update()

    def setCurrentFrame(self, frame_idx):
        if self.current_frame != frame_idx:
            self.current_frame = frame_idx
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.total_frames <= 1 or self.num_tanks == 0: return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(30, 10, -10, -10)
        if not rect.isValid(): return

        bar_height_total = rect.height() / self.num_tanks
        bar_height_visible = bar_height_total * 0.8

        for i in range(self.num_tanks):
            tank_id = i + 1
            y_pos = rect.top() + i * bar_height_total
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#4a4a4a")))
            painter.drawRect(QtCore.QRectF(rect.left(), y_pos, rect.width(), bar_height_visible))
            if tank_id in self.timeline_segments:
                for start_frame, end_frame, behavior in self.timeline_segments[tank_id]:
                    color_tuple = self.behavior_colors.get(behavior, (100, 100, 100))
                    color = QtGui.QColor(*color_tuple)
                    x_start = rect.left() + (start_frame / self.total_frames) * rect.width()
                    x_end = rect.left() + ((end_frame + 1) / self.total_frames) * rect.width()
                    segment_width = max(1.0, x_end - x_start)
                    painter.setBrush(QtGui.QBrush(color))
                    painter.drawRect(QtCore.QRectF(x_start, y_pos, segment_width, bar_height_visible))
            painter.setPen(QtGui.QColor("#e0e0e0"))
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            label_rect = QtCore.QRectF(rect.left() - 25, y_pos, 20, bar_height_visible)
            painter.drawText(label_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, f"T{tank_id}")
        
        if self.total_frames > 0:
            indicator_x = rect.left() + (self.current_frame / self.total_frames) * rect.width()
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 80, 80, 220), 2))
            painter.drawLine(QtCore.QPointF(indicator_x, rect.top()), QtCore.QPointF(indicator_x, rect.bottom()))