# EthoGrid_App/core/grid_manager.py

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QPointF
from PyQt5.QtGui import QTransform

class GridManager(QObject):
    """
    Manages the state and transformation of the annotation grid.
    Encapsulates logic for rotation, scaling, and positioning.
    """
    transform_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.transform = QTransform()
        self.center = QPointF(0.5, 0.5)
        self.angle = 0.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.video_size = (0, 0)

    def set_video_size(self, width, height):
        self.video_size = (width, height)
        self._update_transform_matrix()

    def reset(self):
        self.center = QPointF(0.5, 0.5)
        self.angle = 0.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self._update_transform_matrix()
        self.transform_updated.emit()

    def update_rotation(self, angle):
        self.angle = angle
        self._update_transform_matrix()
        self.transform_updated.emit()

    def update_scale(self, scale_x, scale_y):
        self.scale_x = scale_x
        self.scale_y = scale_y
        self._update_transform_matrix()
        self.transform_updated.emit()
    
    def update_center(self, center_point):
        self.center = center_point
        self._update_transform_matrix()
        self.transform_updated.emit()

    def handle_mouse_drag_rotate(self, last_pos, current_pos):
        """Calculates rotation based on mouse movement around the center."""
        if self.video_size[0] == 0: return

        center_px = QPointF(self.center.x() * self.video_size[0], self.center.y() * self.video_size[1])
        
        vec_prev = QPointF(last_pos.x() * self.video_size[0] - center_px.x(), last_pos.y() * self.video_size[1] - center_px.y())
        vec_curr = QPointF(current_pos.x() * self.video_size[0] - center_px.x(), current_pos.y() * self.video_size[1] - center_px.y())
        
        angle_change = np.degrees(np.arctan2(vec_curr.y(), vec_curr.x()) - np.arctan2(vec_prev.y(), vec_prev.x()))
        self.angle = (self.angle + angle_change + 180) % 360 - 180
        
        self._update_transform_matrix()
        self.transform_updated.emit()

    def _update_transform_matrix(self):
        self.transform.reset()
        if self.video_size[0] > 0:
            w, h = self.video_size
            center_x, center_y = self.center.x() * w, self.center.y() * h
            self.transform.translate(center_x, center_y)
            self.transform.rotate(self.angle)
            self.transform.scale(self.scale_x, self.scale_y)
            self.transform.translate(-w / 2, -h / 2)