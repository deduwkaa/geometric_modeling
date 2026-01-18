import sys
import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QTabWidget, QPushButton, QSizePolicy
)


# ==========================================
# 1. КЛАС ПОЛОТНА (CANVAS) - МАЛЮВАННЯ
# ==========================================
class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: white;")
        # Дозволяємо віджету розтягуватися
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # --- Параметри деталі (Варіант 13 - Фланець) ---
        self.param_center_d = 90.0  # D великого отвору
        self.param_bcd_d = 200.0  # D розміщення отворів (BCD)
        self.param_hole_d = 28.0  # d малих отворів
        self.param_corner_r = 40.0  # R заокруглення вершин

        # Матриця перетворень (трансформацій)
        self.transform_matrix = QTransform()

        # Налаштування вигляду (Камера)
        self.scale_factor = 1.5  # Зумування
        self.offset_x = 0  # Зсув сцени по X
        self.offset_y = 0  # Зсув сцени по Y
        self.grid_step = 50  # Крок сітки

        # Для мишки
        self.last_mouse_pos = QPointF()

    def set_shape_params(self, center_d, bcd_d, hole_d, corner_r):
        self.param_center_d = center_d
        self.param_bcd_d = bcd_d
        self.param_hole_d = hole_d
        self.param_corner_r = corner_r
        self.update()  # Перемалювати

    def set_transform(self, transform):
        self.transform_matrix = transform
        self.update()

    # --- Події Миші (Переміщення та Зум) ---
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
        zoom_in = 1.1
        zoom_out = 1 / zoom_in
        if event.angleDelta().y() > 0:
            self.scale_factor *= zoom_in
        else:
            self.scale_factor *= zoom_out
        self.update()

    # --- ЛОГІКА ПОБУДОВИ ФЛАНЦЯ ---
    def get_shape_path(self):
        """
        Генерує контур деталі.
        """
        r_bcd = self.param_bcd_d / 2.0
        r_corner = self.param_corner_r

        # 1. Знаходимо центри трьох вершин (90°, 210°, 330°)
        angles_deg = [90, 210, 330]
        centers = []
        for ang in angles_deg:
            rad = math.radians(ang)
            cx = r_bcd * math.cos(rad)
            cy = r_bcd * math.sin(rad)
            centers.append(QPointF(cx, cy))

        # 2. Формуємо ТІЛО (Body)
        body_path = QPainterPath()

        # А) Додаємо кола на вершинах ("вуха")
        for c in centers:
            p = QPainterPath()
            p.addEllipse(c, r_corner, r_corner)
            body_path = body_path.united(p)

        # Б) З'єднуємо кола прямокутниками (дотичні)
        for i in range(3):
            c1 = centers[i]
            c2 = centers[(i + 1) % 3]

            vec = c2 - c1
            length = math.sqrt(vec.x() ** 2 + vec.y() ** 2)
            if length == 0: continue

            # Нормаль до вектора
            norm = QPointF(-vec.y(), vec.x()) / length * r_corner

            # Будуємо полігон
            rect_poly = QPainterPath()
            rect_poly.moveTo(c1 + norm)
            rect_poly.lineTo(c2 + norm)
            rect_poly.lineTo(c2 - norm)
            rect_poly.lineTo(c1 - norm)
            rect_poly.closeSubpath()

            body_path = body_path.united(rect_poly)

        # В) Заповнюємо центр
        tri_path = QPainterPath()
        tri_path.moveTo(centers[0])
        tri_path.lineTo(centers[1])
        tri_path.lineTo(centers[2])
        tri_path.closeSubpath()
        body_path = body_path.united(tri_path)

        # 3. Формуємо ОТВОРИ (Holes)
        holes_path = QPainterPath()

        # Центральний отвір
        holes_path.addEllipse(QPointF(0, 0), self.param_center_d / 2, self.param_center_d / 2)

        # Малі отвори по кутах
        r_hole = self.param_hole_d / 2
        for c in centers:
            holes_path.addEllipse(c, r_hole, r_hole)

        # 4. Віднімаємо отвори від тіла
        final_path = body_path.subtracted(holes_path)

        # === ! ВАЖЛИВО: ВИПРАВЛЕННЯ ДЛЯ ПРОЗОРИХ ОТВОРІВ ! ===
        final_path.setFillRule(Qt.FillRule.OddEvenFill)
        # =====================================================

        return final_path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Центрування системи координат у вікні
        cx = self.width() / 2
        cy = self.height() / 2
        painter.translate(cx + self.offset_x, cy + self.offset_y)

        # Масштабування (Y вгору)
        painter.scale(self.scale_factor, -self.scale_factor)

        # 1. Малюємо координатну сітку
        self.draw_grid(painter)

        # 2. Малюємо Деталь
        painter.save()

        # Застосовуємо матрицю трансформацій
        painter.setTransform(self.transform_matrix, True)

        # Стиль заливки та ліній
        pen = QPen(QColor("#2c3e50"), 2)
        pen.setCosmetic(True)
        brush = QBrush(QColor("#4a90e2"))  # Синій колір

        painter.setPen(pen)
        painter.setBrush(brush)

        painter.drawPath(self.get_shape_path())

        # Малюємо локальний центр (червона крапка)
        painter.setPen(QPen(Qt.red, 5))
        painter.drawPoint(0, 0)

        painter.restore()

    def draw_grid(self, painter):
        # Сітка
        grid_pen = QPen(QColor("#e0e0e0"))
        grid_pen.setWidthF(1)
        grid_pen.setCosmetic(True)
        painter.setPen(grid_pen)

        limit = 1000
        step = self.grid_step

        for i in range(-limit, limit, step):
            painter.drawLine(i, -limit, i, limit)
            painter.drawLine(-limit, i, limit, i)

        # Головні осі (X, Y)
        axis_pen = QPen(Qt.black)
        axis_pen.setWidth(2)
        axis_pen.setCosmetic(True)
        painter.setPen(axis_pen)
        painter.drawLine(-limit, 0, limit, 0)
        painter.drawLine(0, -limit, 0, limit)


# ==========================================
# 2. ГОЛОВНЕ ВІКНО (UI)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №1 - Варіант 13 (Фланець)")
        self.resize(1100, 750)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # ЛІВА ПАНЕЛЬ (Керування)
        control_panel = QWidget()
        control_panel.setFixedWidth(340)
        control_layout = QVBoxLayout(control_panel)

        # Група 1: Геометрія
        shape_group = QGroupBox("Параметри Фланця")
        shape_layout = QGridLayout()

        self.spin_center_d = self.create_spin(90, 10, 300)
        self.spin_bcd_d = self.create_spin(200, 50, 500)
        self.spin_hole_d = self.create_spin(28, 5, 100)
        self.spin_corner_r = self.create_spin(40, 5, 100)

        shape_layout.addWidget(QLabel("D центр:"), 0, 0);
        shape_layout.addWidget(self.spin_center_d, 0, 1)
        shape_layout.addWidget(QLabel("D розміщ (BCD):"), 1, 0);
        shape_layout.addWidget(self.spin_bcd_d, 1, 1)
        shape_layout.addWidget(QLabel("d отворів:"), 2, 0);
        shape_layout.addWidget(self.spin_hole_d, 2, 1)
        shape_layout.addWidget(QLabel("R кутів:"), 3, 0);
        shape_layout.addWidget(self.spin_corner_r, 3, 1)
        shape_group.setLayout(shape_layout)

        # Група 2: Вкладки трансформацій
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_euclidean_tab(), "Евклідові")
        self.tabs.addTab(self.create_affine_tab(), "Афінні")
        self.tabs.addTab(self.create_projective_tab(), "Проективні")

        # Кнопка Скидання
        btn_reset = QPushButton("Скинути налаштування")
        btn_reset.clicked.connect(self.reset_all)

        control_layout.addWidget(shape_group)
        control_layout.addWidget(self.tabs)
        control_layout.addStretch()
        control_layout.addWidget(btn_reset)

        # ПРАВА ПАНЕЛЬ (Малювання)
        self.canvas = CanvasWidget()

        main_layout.addWidget(control_panel)
        main_layout.addWidget(self.canvas)

        # Підключення подій (Signals)
        self.spin_center_d.valueChanged.connect(self.update_shape)
        self.spin_bcd_d.valueChanged.connect(self.update_shape)
        self.spin_hole_d.valueChanged.connect(self.update_shape)
        self.spin_corner_r.valueChanged.connect(self.update_shape)
        self.tabs.currentChanged.connect(self.update_transform)

    def create_spin(self, val, mn, mx):
        sb = QDoubleSpinBox()
        sb.setRange(mn, mx)
        sb.setValue(val)
        sb.setSingleStep(1.0)
        return sb

    # --- Створення вкладок ---
    def create_euclidean_tab(self):
        w = QWidget()
        l = QGridLayout()
        self.e_dx = self.create_spin(0, -500, 500)
        self.e_dy = self.create_spin(0, -500, 500)
        self.e_angle = self.create_spin(0, -360, 360)
        self.e_cx = self.create_spin(0, -500, 500)
        self.e_cy = self.create_spin(0, -500, 500)

        l.addWidget(QLabel("Зсув X:"), 0, 0);
        l.addWidget(self.e_dx, 0, 1)
        l.addWidget(QLabel("Зсув Y:"), 1, 0);
        l.addWidget(self.e_dy, 1, 1)
        l.addWidget(QLabel("Кут (°):"), 2, 0);
        l.addWidget(self.e_angle, 2, 1)
        l.addWidget(QLabel("Центр оберт. X:"), 3, 0);
        l.addWidget(self.e_cx, 3, 1)
        l.addWidget(QLabel("Центр оберт. Y:"), 4, 0);
        l.addWidget(self.e_cy, 4, 1)
        w.setLayout(l)

        for sb in [self.e_dx, self.e_dy, self.e_angle, self.e_cx, self.e_cy]:
            sb.valueChanged.connect(self.update_transform)
        return w

    def create_affine_tab(self):
        w = QWidget()
        l = QGridLayout()
        self.a_11 = self.create_spin(1, -5, 5)  # Scale X
        self.a_12 = self.create_spin(0, -5, 5)  # Shear Y
        self.a_21 = self.create_spin(0, -5, 5)  # Shear X
        self.a_22 = self.create_spin(1, -5, 5)  # Scale Y
        self.a_dx = self.create_spin(0, -500, 500)
        self.a_dy = self.create_spin(0, -500, 500)

        l.addWidget(QLabel("m11 (Sx):"), 0, 0);
        l.addWidget(self.a_11, 0, 1)
        l.addWidget(QLabel("m12 (Hy):"), 0, 2);
        l.addWidget(self.a_12, 0, 3)
        l.addWidget(QLabel("m21 (Hx):"), 1, 0);
        l.addWidget(self.a_21, 1, 1)
        l.addWidget(QLabel("m22 (Sy):"), 1, 2);
        l.addWidget(self.a_22, 1, 3)
        l.addWidget(QLabel("Dx:"), 2, 0);
        l.addWidget(self.a_dx, 2, 1)
        l.addWidget(QLabel("Dy:"), 2, 2);
        l.addWidget(self.a_dy, 2, 3)
        w.setLayout(l)

        for sb in [self.a_11, self.a_12, self.a_21, self.a_22, self.a_dx, self.a_dy]:
            sb.valueChanged.connect(self.update_transform)
        return w

    def create_projective_tab(self):
        w = QWidget()
        l = QGridLayout()
        self.p_spins = []
        defaults = [1, 0, 0, 0, 1, 0, 0, 0, 1]

        for i in range(3):
            for j in range(3):
                idx = i * 3 + j
                val = defaults[idx]
                sb = QDoubleSpinBox()
                sb.setRange(-500, 500)
                sb.setValue(val)
                # Збільшуємо точність для проективних параметрів
                if j == 2 and i < 2:
                    sb.setSingleStep(0.001)
                    sb.setDecimals(4)
                    sb.setRange(-0.01, 0.01)
                else:
                    sb.setSingleStep(0.1)

                sb.valueChanged.connect(self.update_transform)
                self.p_spins.append(sb)
                l.addWidget(sb, i, j)

        l.addWidget(QLabel("m13, m23 - перспектива"), 3, 0, 1, 3)
        w.setLayout(l)
        return w

    # --- Оновлення ---
    def update_shape(self):
        self.canvas.set_shape_params(
            self.spin_center_d.value(),
            self.spin_bcd_d.value(),
            self.spin_hole_d.value(),
            self.spin_corner_r.value()
        )

    def update_transform(self):
        idx = self.tabs.currentIndex()
        t = QTransform()

        if idx == 0:  # Евклідові
            t.translate(self.e_dx.value(), self.e_dy.value())
            cx, cy = self.e_cx.value(), self.e_cy.value()
            t.translate(cx, cy)
            t.rotate(self.e_angle.value())
            t.translate(-cx, -cy)

        elif idx == 1:  # Афінні
            t = QTransform(
                self.a_11.value(), self.a_12.value(),
                self.a_21.value(), self.a_22.value(),
                self.a_dx.value(), self.a_dy.value()
            )

        elif idx == 2:  # Проективні
            p = [s.value() for s in self.p_spins]
            t.setMatrix(
                p[0], p[1], p[2],
                p[3], p[4], p[5],
                p[6], p[7], p[8]
            )

        self.canvas.set_transform(t)

    def reset_all(self):
        self.blockSignals(True)
        # Скидаємо евклідові
        self.e_dx.setValue(0);
        self.e_dy.setValue(0);
        self.e_angle.setValue(0)
        self.e_cx.setValue(0);
        self.e_cy.setValue(0)
        # Скидаємо афінні
        self.a_11.setValue(1);
        self.a_22.setValue(1)
        self.a_12.setValue(0);
        self.a_21.setValue(0)
        self.a_dx.setValue(0);
        self.a_dy.setValue(0)
        # Скидаємо проективні
        defaults = [1, 0, 0, 0, 1, 0, 0, 0, 1]
        for sb, val in zip(self.p_spins, defaults):
            sb.setValue(val)

        self.blockSignals(False)
        self.update_transform()


# ==========================================
# 3. ЗАПУСК
# ==========================================
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    # Піднімаємо вікно наверх
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()