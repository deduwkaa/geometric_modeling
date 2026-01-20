import sys
import math
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform, QBrush, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QPushButton, QSizePolicy, QSlider
)


# ==========================================
# 1. МАТЕМАТИЧНЕ ЯДРО (Кардіоїда)
# ==========================================
class CardioidMath:
    @staticmethod
    def get_point(a, t):
        """
        x = a * (1 - cos(t)) * cos(t)
        y = a * (1 - cos(t)) * sin(t)
        """
        r = a * (1 - math.cos(t))
        x = r * math.cos(t)
        y = r * math.sin(t)
        return QPointF(x, y)

    @staticmethod
    def get_derivatives(a, t):
        dx = a * (math.sin(2 * t) - math.sin(t))
        dy = a * (math.cos(t) - math.cos(2 * t))
        return dx, dy

    @staticmethod
    def calculate_properties(a, t):
        area = 6 * math.pi * (a ** 2)
        length = 16 * a
        r_curv = (8 * a / 3) * math.sin(t / 2)
        return area, length, r_curv


# ==========================================
# 2. КЛАС ПОЛОТНА (CANVAS)
# ==========================================
class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: white;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.param_a = 50.0
        self.param_t = 1.0
        self.transform_matrix = QTransform()

        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.last_mouse_pos = QPointF()

    def set_params(self, a, t):
        self.param_a = a
        self.param_t = t
        self.update()

    def set_transform_params(self, dx, dy, angle, cx, cy):
        t = QTransform()
        t.translate(dx, dy)
        t.translate(cx, cy)
        t.rotate(angle)
        t.translate(-cx, -cy)
        self.transform_matrix = t
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position() - self.last_mouse_pos
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_mouse_pos = event.position()
            self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.1
        else:
            self.scale_factor /= 1.1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        painter.translate(cx + self.offset_x, cy + self.offset_y)
        painter.scale(self.scale_factor, -self.scale_factor)

        self.draw_grid(painter)

        # Трансформація
        painter.setTransform(self.transform_matrix, True)

        self.draw_cardioid(painter)
        self.draw_tangent_normal(painter)

    def draw_grid(self, painter):
        pen = QPen(QColor("#e0e0e0"))
        pen.setWidthF(1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        limit = 2000
        step = 50
        for i in range(-limit, limit, step):
            painter.drawLine(i, -limit, i, limit)
            painter.drawLine(-limit, i, limit, i)

        pen.setColor(Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(-limit, 0, limit, 0)
        painter.drawLine(0, -limit, 0, limit)

    def draw_cardioid(self, painter):
        path = QPainterPath()
        steps = 360
        first_pt = CardioidMath.get_point(self.param_a, 0)
        path.moveTo(first_pt)
        for i in range(1, steps + 1):
            t = math.radians(i)
            pt = CardioidMath.get_point(self.param_a, t)
            path.lineTo(pt)

        pen = QPen(QColor("#007AFF"), 3)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def draw_tangent_normal(self, painter):
        t_val = self.param_t
        pt = CardioidMath.get_point(self.param_a, t_val)

        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.red)
        painter.drawEllipse(pt, 4, 4)

        dx, dy = CardioidMath.get_derivatives(self.param_a, t_val)
        line_len = 100
        mag = math.sqrt(dx ** 2 + dy ** 2)

        if mag > 0.001:
            tx, ty = (dx / mag) * line_len, (dy / mag) * line_len
            nx, ny = (-dy / mag) * line_len, (dx / mag) * line_len

            pen_tan = QPen(QColor("magenta"), 2)
            pen_tan.setCosmetic(True)
            painter.setPen(pen_tan)
            painter.drawLine(QPointF(pt.x() - tx, pt.y() - ty), QPointF(pt.x() + tx, pt.y() + ty))

            pen_norm = QPen(QColor("green"), 2)
            pen_norm.setCosmetic(True)
            painter.setPen(pen_norm)
            painter.drawLine(QPointF(pt.x() - nx, pt.y() - ny), QPointF(pt.x() + nx, pt.y() + ny))


# ==========================================
# 3. ГОЛОВНЕ ВІКНО
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №2: Кардіоїда (Варіант 13)")
        self.resize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        controls = QWidget()
        controls.setFixedWidth(320)
        ctrl_layout = QVBoxLayout(controls)

        # 1. Curve Params
        grp_curve = QGroupBox("Параметри Кардіоїди")
        grid_curve = QGridLayout()
        self.spin_a = QDoubleSpinBox()
        self.spin_a.setRange(10, 300)
        self.spin_a.setValue(50)
        self.spin_a.setSuffix(" px")
        self.slider_t = QSlider(Qt.Orientation.Horizontal)
        self.slider_t.setRange(0, 628)
        self.slider_t.setValue(100)
        grid_curve.addWidget(QLabel("Параметр a:"), 0, 0)
        grid_curve.addWidget(self.spin_a, 0, 1)
        grid_curve.addWidget(QLabel("Точка t:"), 1, 0)
        grid_curve.addWidget(self.slider_t, 1, 1)
        grp_curve.setLayout(grid_curve)
        ctrl_layout.addWidget(grp_curve)

        # 2. Animation
        grp_anim = QGroupBox("Анімація")
        anim_layout = QVBoxLayout()
        self.btn_anim = QPushButton("Старт/Стоп Анімація")
        self.btn_anim.setCheckable(True)
        anim_layout.addWidget(self.btn_anim)
        grp_anim.setLayout(anim_layout)
        ctrl_layout.addWidget(grp_anim)

        # 3. Transformations
        grp_trans = QGroupBox("Евклідові перетворення")
        grid_trans = QGridLayout()
        self.spin_dx = self.create_spin(0, -500, 500)
        self.spin_dy = self.create_spin(0, -500, 500)
        self.spin_angle = self.create_spin(0, -360, 360)
        self.spin_cx = self.create_spin(0, -500, 500)
        self.spin_cy = self.create_spin(0, -500, 500)
        grid_trans.addWidget(QLabel("Зсув X:"), 0, 0);
        grid_trans.addWidget(self.spin_dx, 0, 1)
        grid_trans.addWidget(QLabel("Зсув Y:"), 1, 0);
        grid_trans.addWidget(self.spin_dy, 1, 1)
        grid_trans.addWidget(QLabel("Оберт (°):"), 2, 0);
        grid_trans.addWidget(self.spin_angle, 2, 1)
        grid_trans.addWidget(QLabel("Центр X:"), 3, 0);
        grid_trans.addWidget(self.spin_cx, 3, 1)
        grid_trans.addWidget(QLabel("Центр Y:"), 4, 0);
        grid_trans.addWidget(self.spin_cy, 4, 1)
        grp_trans.setLayout(grid_trans)
        ctrl_layout.addWidget(grp_trans)

        # 4. Results
        grp_res = QGroupBox("Властивості")
        res_layout = QVBoxLayout()
        self.lbl_area = QLabel("Площа: 0")
        self.lbl_len = QLabel("Довжина: 0")
        self.lbl_rad = QLabel("Радіус кривини: 0")
        res_layout.addWidget(self.lbl_area)
        res_layout.addWidget(self.lbl_len)
        res_layout.addWidget(self.lbl_rad)
        grp_res.setLayout(res_layout)
        ctrl_layout.addWidget(grp_res)

        ctrl_layout.addStretch()
        self.canvas = CanvasWidget()
        layout.addWidget(controls)
        layout.addWidget(self.canvas)

        # Signals
        self.spin_a.valueChanged.connect(self.update_all)
        self.slider_t.valueChanged.connect(self.update_all)
        for sb in [self.spin_dx, self.spin_dy, self.spin_angle, self.spin_cx, self.spin_cy]:
            sb.valueChanged.connect(self.update_transform)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_step)
        self.btn_anim.clicked.connect(self.toggle_animation)
        self.anim_direction = 1

        self.update_all()

    def create_spin(self, val, mn, mx):
        sb = QDoubleSpinBox()
        sb.setRange(mn, mx)
        sb.setValue(val)
        return sb

    def update_all(self):
        a = self.spin_a.value()
        t_deg = self.slider_t.value() / 100.0
        self.canvas.set_params(a, t_deg)
        area, length, r_curv = CardioidMath.calculate_properties(a, t_deg)
        self.lbl_area.setText(f"Площа: {area:.2f}")
        self.lbl_len.setText(f"Довжина: {length:.2f}")
        self.lbl_rad.setText(f"Радіус кривини (у т. t): {abs(r_curv):.2f}")

    def update_transform(self):
        self.canvas.set_transform_params(
            self.spin_dx.value(), self.spin_dy.value(),
            self.spin_angle.value(), self.spin_cx.value(), self.spin_cy.value()
        )

    def toggle_animation(self, checked):
        if checked:
            self.timer.start(30)
        else:
            self.timer.stop()

    def animate_step(self):
        # 1. Дихання (параметр a)
        curr_a = self.spin_a.value()
        if curr_a >= 100:
            self.anim_direction = -1
        elif curr_a <= 30:
            self.anim_direction = 1

        # 2. Обертання (кут)
        curr_angle = self.spin_angle.value()
        new_angle = (curr_angle + 1) % 360

        # Блокуємо сигнали, щоб не викликати подвійне перемальовування
        self.spin_a.blockSignals(True)
        self.spin_angle.blockSignals(True)

        self.spin_a.setValue(curr_a + 0.5 * self.anim_direction)
        self.spin_angle.setValue(new_angle)

        self.spin_a.blockSignals(False)
        self.spin_angle.blockSignals(False)

        # Оновлюємо все вручну
        self.update_all()
        self.update_transform()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())