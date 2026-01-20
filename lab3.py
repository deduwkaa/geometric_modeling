import sys
import math
import numpy as np  # Додано numpy для роботи з матрицями
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QPushButton, QSizePolicy, QCheckBox
)


# 1. МАТЕМАТИЧНЕ ЯДРО (Engineering Form / Matrix)

class SplineMath:
    @staticmethod
    def get_segment_points(p0, p1, p2, p3, tension, segments=30):
        """
        Розрахунок точок сегмента кривої 3-го порядку в інженерному (алгебраїчному) вигляді.
        P(t) = A*t^3 + B*t^2 + C*t + D
        Коефіцієнти A, B, C, D знаходяться через матрицю Кардинального сплайна.
        """
        # Параметр натягу s
        s = (1 - tension) / 2.0

        # Матриця Кардинального сплайна (Basis Matrix)
        # | -s   2-s   s-2   s |
        # | 2s   s-3  3-2s  -s |
        # | -s    0     s    0 |
        # |  0    1     0    0 |
        M = np.array([
            [-s, 2 - s, s - 2, s],
            [2 * s, s - 3, 3 - 2 * s, -s],
            [-s, 0, s, 0],
            [0, 1, 0, 0]
        ])

        # Вектори геометрії (Geometry Vectors)
        Gx = np.array([p0.x(), p1.x(), p2.x(), p3.x()])
        Gy = np.array([p0.y(), p1.y(), p2.y(), p3.y()])

        # Алгебраїчні коефіцієнти (Algebraic Coefficients)
        # C = M * G
        Cx = M @ Gx
        Cy = M @ Gy

        points = []
        for i in range(1, segments + 1):
            t = i / segments
            # Обчислення полінома: At^3 + Bt^2 + Ct + D
            # Cx[0]*t^3 + Cx[1]*t^2 + Cx[2]*t + Cx[3]
            t2 = t * t
            t3 = t2 * t

            x = Cx[0] * t3 + Cx[1] * t2 + Cx[2] * t + Cx[3]
            y = Cy[0] * t3 + Cy[1] * t2 + Cy[2] * t + Cy[3]
            points.append(QPointF(x, y))

        return points



# 2. КЛАС ПОЛОТНА (CANVAS)

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #2b2b2b;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # КОНТУР ЯХТИ (опорні точки)
        self.points = [
            QPointF(0, 200),  # ТОП ЩОГЛИ
            QPointF(25, 160),  # ПРАВЕ ВІТРИЛО
            QPointF(50, 100),
            QPointF(65, 50),
            QPointF(10, 50),
            QPointF(150, 20),  # ПРАВИЙ БОРТ
            QPointF(100, -30),
            QPointF(40, -45),
            QPointF(-40, -45),  # ЛІВИЙ БОРТ
            QPointF(-100, -30),
            QPointF(-150, 20),
            QPointF(-10, 50),  # ЛІВЕ ВІТРИЛО
            QPointF(-70, 50),
            QPointF(-35, 140)
        ]

        # Ціль для анімації (Коло)
        self.target_shape = []
        radius = 150
        for i in range(len(self.points)):
            angle = 2 * math.pi * i / len(self.points) + math.pi / 2
            self.target_shape.append(QPointF(radius * math.cos(angle), radius * math.sin(angle)))

        self.current_points = [QPointF(p) for p in self.points]

        # Параметри
        self.show_polygon = True
        self.tension = 0.0

        # Інтерактив
        self.selected_point_index = -1
        self.drag_radius = 10
        self.last_mouse_pos = QPointF()

        # Трансформації
        self.transform_matrix = QTransform()
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # Анімація
        self.anim_progress = 0.0
        self.is_animating = False

    def set_tension(self, val):
        self.tension = val
        self.update()

    def set_show_polygon(self, val):
        self.show_polygon = val
        self.update()

    def set_transform_params(self, dx, dy, angle, scale_x, scale_y):
        t = QTransform()
        t.scale(scale_x, scale_y)
        t.rotate(angle)
        t.translate(dx, dy)
        self.transform_matrix = t
        self.update()

    def update_animation_state(self, progress):
        self.anim_progress = progress
        for i in range(len(self.points)):
            p_start = self.points[i]
            p_end = self.target_shape[i]
            new_x = p_start.x() + (p_end.x() - p_start.x()) * progress
            new_y = p_start.y() + (p_end.y() - p_start.y()) * progress
            self.current_points[i] = QPointF(new_x, new_y)
        self.update()

    # --- Mouse Events ---
    def mousePressEvent(self, event):
        pos = self.get_logical_pos(event.position())
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_animating:
                for i, p in enumerate(self.current_points):
                    if (p - pos).manhattanLength() < self.drag_radius * 2:
                        self.selected_point_index = i
                        return
            self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event):
        pos = self.get_logical_pos(event.position())
        if self.selected_point_index >= 0:
            self.current_points[self.selected_point_index] = pos
            self.points[self.selected_point_index] = pos
            self.update()
        elif event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position() - self.last_mouse_pos
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_mouse_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        self.selected_point_index = -1

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.1
        else:
            self.scale_factor /= 1.1
        self.update()

    def get_logical_pos(self, screen_pos):
        cx = self.width() / 2
        cy = self.height() / 2
        x = (screen_pos.x() - cx - self.offset_x) / self.scale_factor
        y = -(screen_pos.y() - cy - self.offset_y) / self.scale_factor
        return QPointF(x, y)

    # --- Painting ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        painter.translate(cx + self.offset_x, cy + self.offset_y)
        painter.scale(self.scale_factor, -self.scale_factor)

        self.draw_grid(painter)

        painter.setTransform(self.transform_matrix, True)

        # 1. Каркас
        if self.show_polygon:
            pen_poly = QPen(QColor("#808080"), 1, Qt.DashLine)
            pen_poly.setCosmetic(True)
            painter.setPen(pen_poly)
            poly_path = QPainterPath()
            if self.current_points:
                poly_path.moveTo(self.current_points[0])
                for p in self.current_points[1:]:
                    poly_path.lineTo(p)
                poly_path.closeSubpath()
            painter.drawPath(poly_path)

        # 2. Крива (Інженерний вигляд: розрахунок коефіцієнтів)
        curve_path = QPainterPath()
        pts = self.current_points
        n = len(pts)
        if n > 0:
            curve_path.moveTo(pts[0])
            for i in range(n):
                # 4 точки для сегмента (ковзне вікно)
                p0 = pts[(i - 1) % n]
                p1 = pts[i]
                p2 = pts[(i + 1) % n]
                p3 = pts[(i + 2) % n]

                # Отримуємо точки сегмента через матричний розрахунок коефіцієнтів
                segment_points = SplineMath.get_segment_points(p0, p1, p2, p3, self.tension)
                for pt in segment_points:
                    curve_path.lineTo(pt)

        pen_curve = QPen(QColor("#0099FF"), 2)
        pen_curve.setCosmetic(True)
        painter.setPen(pen_curve)
        brush_color = QColor("#1A3A5A")
        brush_color.setAlpha(150)
        painter.setBrush(brush_color)
        painter.drawPath(curve_path)

        # 3. Вузли
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("red"))
        point_r = 7 / self.scale_factor
        for p in self.current_points:
            painter.drawEllipse(p, point_r, point_r)

    def draw_grid(self, painter):
        pen = QPen(QColor("#505050"), 0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        limit = 2000
        step = 50
        for i in range(-limit, limit, step):
            painter.drawLine(i, -limit, i, limit)
            painter.drawLine(-limit, i, limit, i)
        pen.setColor(QColor("#000000"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(-limit, 0, limit, 0)
        painter.drawLine(0, -limit, 0, limit)


# 3. ГОЛОВНЕ ВІКНО

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №3: Яхта (Алгебраїчні криві)")
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Controls
        controls = QWidget()
        controls.setFixedWidth(340)
        ctrl_layout = QVBoxLayout(controls)

        grp_params = QGroupBox("Налаштування")
        grid_params = QGridLayout()
        self.chk_poly = QCheckBox("Показати каркас")
        self.chk_poly.setChecked(True)
        self.chk_poly.stateChanged.connect(self.toggle_poly)
        self.spin_tension = QDoubleSpinBox()
        self.spin_tension.setRange(-2.0, 2.0)
        self.spin_tension.setSingleStep(0.1)
        self.spin_tension.setValue(0.0)
        self.spin_tension.valueChanged.connect(self.update_tension)
        grid_params.addWidget(self.chk_poly, 0, 0, 1, 2)
        grid_params.addWidget(QLabel("Натяг (Tension):"), 1, 0)
        grid_params.addWidget(self.spin_tension, 1, 1)
        grp_params.setLayout(grid_params)
        ctrl_layout.addWidget(grp_params)

        grp_anim = QGroupBox("Анімація")
        anim_layout = QVBoxLayout()
        self.btn_anim = QPushButton("Трансформація в Коло")
        self.btn_anim.setCheckable(True)
        self.btn_anim.clicked.connect(self.toggle_anim)
        anim_layout.addWidget(self.btn_anim)
        grp_anim.setLayout(anim_layout)
        ctrl_layout.addWidget(grp_anim)

        grp_trans = QGroupBox("Евклідові перетворення")
        grid_trans = QGridLayout()
        self.spin_dx = self.create_spin(0, -500, 500)
        self.spin_dy = self.create_spin(0, -500, 500)
        self.spin_angle = self.create_spin(0, -360, 360)
        self.spin_sx = self.create_spin(1, 0.1, 5, step=0.1)
        self.spin_sy = self.create_spin(1, 0.1, 5, step=0.1)
        grid_trans.addWidget(QLabel("Зсув X:"), 0, 0);
        grid_trans.addWidget(self.spin_dx, 0, 1)
        grid_trans.addWidget(QLabel("Зсув Y:"), 1, 0);
        grid_trans.addWidget(self.spin_dy, 1, 1)
        grid_trans.addWidget(QLabel("Оберт (°):"), 2, 0);
        grid_trans.addWidget(self.spin_angle, 2, 1)
        grid_trans.addWidget(QLabel("Масштаб X:"), 3, 0);
        grid_trans.addWidget(self.spin_sx, 3, 1)
        grid_trans.addWidget(QLabel("Масштаб Y:"), 4, 0);
        grid_trans.addWidget(self.spin_sy, 4, 1)
        grp_trans.setLayout(grid_trans)
        ctrl_layout.addWidget(grp_trans)

        ctrl_layout.addStretch()
        self.canvas = CanvasWidget()
        layout.addWidget(controls)
        layout.addWidget(self.canvas)

        self.timer = QTimer()
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.anim_tick)
        self.anim_direction = 1
        self.anim_curr_val = 0.0

        for sb in [self.spin_dx, self.spin_dy, self.spin_angle, self.spin_sx, self.spin_sy]:
            sb.valueChanged.connect(self.update_transform)

    def create_spin(self, val, mn, mx, step=1.0):
        sb = QDoubleSpinBox()
        sb.setRange(mn, mx)
        sb.setValue(val)
        sb.setSingleStep(step)
        return sb

    def toggle_poly(self):
        self.canvas.set_show_polygon(self.chk_poly.isChecked())

    def update_tension(self):
        self.canvas.set_tension(self.spin_tension.value())

    def update_transform(self):
        self.canvas.set_transform_params(
            self.spin_dx.value(), self.spin_dy.value(),
            self.spin_angle.value(), self.spin_sx.value(), self.spin_sy.value()
        )

    def toggle_anim(self):
        self.canvas.is_animating = True
        self.timer.start()
        if self.anim_curr_val >= 1.0:
            self.anim_direction = -1
        elif self.anim_curr_val <= 0.0:
            self.anim_direction = 1

    def anim_tick(self):
        self.anim_curr_val += 0.02 * self.anim_direction
        if self.anim_curr_val >= 1.0:
            self.anim_curr_val = 1.0;
            self.timer.stop()
            self.canvas.is_animating = False;
            self.btn_anim.setChecked(True)
        elif self.anim_curr_val <= 0.0:
            self.anim_curr_val = 0.0;
            self.timer.stop()
            self.canvas.is_animating = False;
            self.btn_anim.setChecked(False)
        self.canvas.update_animation_state(self.anim_curr_val)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())