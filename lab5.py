import sys
import os
import math
import numpy as np

# --- 1. АВТОМАТИЧНЕ ВИПРАВЛЕННЯ ПОМИЛКИ "COCOA" (MACOS FIX) ---
try:
    import PySide6

    dirname = os.path.dirname(PySide6.__file__)
    plugin_path = os.path.join(dirname, 'plugins', 'platforms')
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
except ImportError:
    pass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QPushButton, QSizePolicy, QCheckBox
)


# 1. МАТЕМАТИКА (3D Transformations)

class Transform3D:
    @staticmethod
    def rotate_x(angle_deg):
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        return np.array([
            [1, 0, 0, 0],
            [0, c, -s, 0],
            [0, s, c, 0],
            [0, 0, 0, 1]
        ])

    @staticmethod
    def rotate_y(angle_deg):
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        return np.array([
            [c, 0, s, 0],
            [0, 1, 0, 0],
            [-s, 0, c, 0],
            [0, 0, 0, 1]
        ])

    @staticmethod
    def rotate_z(angle_deg):
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        return np.array([
            [c, -s, 0, 0],
            [s, c, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])

    @staticmethod
    def translate(dx, dy, dz):
        return np.array([
            [1, 0, 0, dx],
            [0, 1, 0, dy],
            [0, 0, 1, dz],
            [0, 0, 0, 1]
        ])

    @staticmethod
    def scale(sx, sy, sz):
        return np.array([
            [sx, 0, 0, 0],
            [0, sy, 0, 0],
            [0, 0, sz, 0],
            [0, 0, 0, 1]
        ])

    @staticmethod
    def get_perspective_projection(dist):
        return np.identity(4)


# 2. ГЕНЕРАЦІЯ ФІГУРИ (Star Prism)

def generate_star_prism(points_count=5, inner_r=50, outer_r=100, height=150):
    """Генерує вершини та ребра призми у формі зірки"""
    vertices = []
    edges = []

    # Генеруємо основу (зірку) в площині XY
    angle_step = math.pi / points_count

    # Нижня та Верхня основи
    for z in [-height / 2, height / 2]:
        start_idx = len(vertices)
        for i in range(2 * points_count):
            angle = i * angle_step
            r = outer_r if i % 2 == 0 else inner_r
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            vertices.append([x, y, z, 1.0])  # Homogeneous coords

            # Ребра основи
            if i > 0:
                edges.append((start_idx + i - 1, start_idx + i))
        # Замикаємо основу
        edges.append((start_idx + 2 * points_count - 1, start_idx))

    # Вертикальні ребра (з'єднують низ і верх)
    bottom_start = 0
    top_start = 2 * points_count
    for i in range(2 * points_count):
        edges.append((bottom_start + i, top_start + i))

    return np.array(vertices), edges


# 3. КЛАС ПОЛОТНА (Visualizer)

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #2b2b2b;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # -- ПАРАМЕТРИ ФІГУРИ (Star Prism) --
        self.fig_outer_r = 100
        self.fig_inner_r = 50
        self.fig_height = 150
        self.vertices, self.edges = generate_star_prism(5, self.fig_inner_r, self.fig_outer_r, self.fig_height)

        # -- ПАРАМЕТРИ ТРАНСФОРМАЦІЇ (Власні) --
        self.own_dx = 0
        self.own_dy = 0
        self.own_dz = 0
        self.own_rot_x = 0
        self.own_rot_y = 0
        self.own_rot_z = 0

        # -- ПАРАМЕТРИ ПРОЕКЦІЇ (Варіант 13: Триточкова перспектива) --
        self.view_dist = 600  # Відстань до камери
        self.view_rot_x = 30  # Кут нахилу (Alpha)
        self.view_rot_y = 45  # Кут повороту (Beta)
        self.view_rot_z = 0

    def update_figure(self):
        # Перегенерація при зміні розмірів
        self.vertices, self.edges = generate_star_prism(5, self.fig_inner_r, self.fig_outer_r, self.fig_height)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#2b2b2b"))

        # Центр екрану
        cx, cy = self.width() / 2, self.height() / 2

        # 1. МАТРИЦЯ МОДЕЛІ (Власні перетворення фігури)
        M_model = Transform3D.translate(self.own_dx, self.own_dy, self.own_dz) @ \
                  Transform3D.rotate_z(self.own_rot_z) @ \
                  Transform3D.rotate_y(self.own_rot_y) @ \
                  Transform3D.rotate_x(self.own_rot_x)

        # 2. МАТРИЦЯ ВИДУ (View / Camera)
        M_view = Transform3D.translate(0, 0, self.view_dist) @ \
                 Transform3D.rotate_x(self.view_rot_x) @ \
                 Transform3D.rotate_y(self.view_rot_y)

        # Комбінована матриця (Model -> View)
        M_final = M_view @ M_model

        # 3. ПРОЕКЦІЮВАННЯ ТА МАЛЮВАННЯ
        projected_points = []

        # Перетворюємо всі вершини
        for v in self.vertices:
            p = M_final @ v
            x, y, z = p[0], p[1], p[2]

            factor = 0
            if (self.view_dist - z) != 0:
                factor = self.view_dist / (self.view_dist - z + 0.001)

            px = x * factor
            py = y * factor

            projected_points.append((cx + px, cy - py))  # Y inverted for screen

        # Малюємо ребра
        pen = QPen(QColor("#00AAFF"), 2)
        painter.setPen(pen)

        for edge in self.edges:
            p1 = projected_points[edge[0]]
            p2 = projected_points[edge[1]]
            painter.drawLine(p1[0], p1[1], p2[0], p2[1])

        # 4. МАЛЮЄМО ОСІ (Для орієнтиру)
        self.draw_axes(painter, M_view, cx, cy)

        # Текст
        painter.setPen(QColor("white"))
        painter.drawText(10, 20, f"Method 17: Three-point Perspective")
        painter.drawText(10, 40, f"Distance (d): {self.view_dist}")

    def draw_axes(self, painter, M_view, cx, cy):
        length = 100
        origin = np.array([0, 0, 0, 1])
        axis_x = np.array([length, 0, 0, 1])
        axis_y = np.array([0, length, 0, 1])
        axis_z = np.array([0, 0, length, 1])

        def project(v):
            p = M_view @ v
            x, y, z = p[0], p[1], p[2]
            factor = self.view_dist / (self.view_dist - z + 0.001)
            return cx + x * factor, cy - y * factor

        o_scr = project(origin)
        x_scr = project(axis_x)
        y_scr = project(axis_y)
        z_scr = project(axis_z)

        # X - Red
        painter.setPen(QPen(Qt.red, 2))
        painter.drawLine(o_scr[0], o_scr[1], x_scr[0], x_scr[1])
        painter.drawText(x_scr[0], x_scr[1], "X")

        # Y - Green
        painter.setPen(QPen(Qt.green, 2))
        painter.drawLine(o_scr[0], o_scr[1], y_scr[0], y_scr[1])
        painter.drawText(y_scr[0], y_scr[1], "Y")

        # Z - Blue
        painter.setPen(QPen(Qt.blue, 2))
        painter.drawLine(o_scr[0], o_scr[1], z_scr[0], z_scr[1])
        painter.drawText(z_scr[0], z_scr[1], "Z")


# 4. ГОЛОВНЕ ВІКНО

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №5: Триточкова Перспектива (Варіант 13)")
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # --- ПАНЕЛЬ КЕРУВАННЯ ---
        controls = QWidget()
        controls.setFixedWidth(320)
        ctrl_layout = QVBoxLayout(controls)

        # 1. Параметри фігури
        grp_fig = QGroupBox("1. Параметри Фігури (Зірка)")
        l_fig = QGridLayout()

        self.spin_h = self.add_spin(l_fig, "Висота:", 150, 10, 500, 0)
        self.spin_r = self.add_spin(l_fig, "Радіус:", 100, 10, 300, 1)

        grp_fig.setLayout(l_fig)
        ctrl_layout.addWidget(grp_fig)

        # 2. Власні трансформації
        grp_trans = QGroupBox("2. Власні перетворення (Model)")
        l_trans = QGridLayout()

        self.spin_dx = self.add_spin(l_trans, "Зсув X:", 0, -500, 500, 0)
        self.spin_dy = self.add_spin(l_trans, "Зсув Y:", 0, -500, 500, 1)
        self.spin_dz = self.add_spin(l_trans, "Зсув Z:", 0, -500, 500, 2)

        self.spin_rot_x = self.add_spin(l_trans, "Оберт X:", 0, -360, 360, 3)
        self.spin_rot_y = self.add_spin(l_trans, "Оберт Y:", 0, -360, 360, 4)
        self.spin_rot_z = self.add_spin(l_trans, "Оберт Z:", 0, -360, 360, 5)

        grp_trans.setLayout(l_trans)
        ctrl_layout.addWidget(grp_trans)

        # 3. Параметри проекції
        grp_proj = QGroupBox("3. Проекція (Триточкова)")
        l_proj = QGridLayout()

        self.spin_dist = self.add_spin(l_proj, "Дистанція (d):", 600, 100, 2000, 0)
        self.spin_view_x = self.add_spin(l_proj, "Кут огляду X:", 30, -180, 180, 1)
        self.spin_view_y = self.add_spin(l_proj, "Кут огляду Y:", 45, -180, 180, 2)

        grp_proj.setLayout(l_proj)
        ctrl_layout.addWidget(grp_proj)

        # 4. Анімація
        grp_anim = QGroupBox("4. Анімація")
        l_anim = QVBoxLayout()
        self.btn_anim = QPushButton("Старт / Стоп")
        self.btn_anim.setCheckable(True)
        self.btn_anim.clicked.connect(self.toggle_anim)
        l_anim.addWidget(self.btn_anim)
        grp_anim.setLayout(l_anim)
        ctrl_layout.addWidget(grp_anim)

        ctrl_layout.addStretch()

        # --- ПОЛОТНО ---
        self.canvas = CanvasWidget()
        layout.addWidget(controls)
        layout.addWidget(self.canvas)

        # Таймер анімації
        self.timer = QTimer()
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.anim_tick)
        self.anim_phase = 0.0  # Лічильник фази для плавності

        # Підключення сигналів
        self.spin_h.valueChanged.connect(self.update_params)
        self.spin_r.valueChanged.connect(self.update_params)

        for s in [self.spin_dx, self.spin_dy, self.spin_dz, self.spin_rot_x, self.spin_rot_y, self.spin_rot_z]:
            s.valueChanged.connect(self.update_transforms)

        for s in [self.spin_dist, self.spin_view_x, self.spin_view_y]:
            s.valueChanged.connect(self.update_projection)

    def add_spin(self, layout, label, val, min_v, max_v, row):
        lbl = QLabel(label)
        sp = QDoubleSpinBox()
        sp.setRange(min_v, max_v)
        sp.setValue(val)
        layout.addWidget(lbl, row, 0)
        layout.addWidget(sp, row, 1)
        return sp

    def update_params(self):
        self.canvas.fig_height = self.spin_h.value()
        self.canvas.fig_outer_r = self.spin_r.value()
        self.canvas.fig_inner_r = self.spin_r.value() / 2
        self.canvas.update_figure()

    def update_transforms(self):
        self.canvas.own_dx = self.spin_dx.value()
        self.canvas.own_dy = self.spin_dy.value()
        self.canvas.own_dz = self.spin_dz.value()
        self.canvas.own_rot_x = self.spin_rot_x.value()
        self.canvas.own_rot_y = self.spin_rot_y.value()
        self.canvas.own_rot_z = self.spin_rot_z.value()
        self.canvas.update()

    def update_projection(self):
        self.canvas.view_dist = self.spin_dist.value()
        self.canvas.view_rot_x = self.spin_view_x.value()
        self.canvas.view_rot_y = self.spin_view_y.value()
        self.canvas.update()

    def toggle_anim(self):
        if self.btn_anim.isChecked():
            self.timer.start()
        else:
            self.timer.stop()

    def anim_tick(self):
        # Використовуємо постійний крок фази для плавності
        self.anim_phase += 0.1

        # 1. Обертання
        cur_rot = self.spin_rot_y.value()
        self.spin_rot_y.blockSignals(True)  # Блокуємо, щоб не викликати зайвих оновлень
        self.spin_rot_y.setValue((cur_rot + 1) % 360)
        self.spin_rot_y.blockSignals(False)

        # 2. Дихання (Зміна радіусу від 60 до 140)
        base_r = 100
        amplitude = 40
        new_r = base_r + amplitude * math.sin(self.anim_phase)

        self.spin_r.blockSignals(True)  # Блокуємо
        self.spin_r.setValue(new_r)
        self.spin_r.blockSignals(False)

        # Оновлюємо все вручну ОДИН РАЗ за кадр
        self.update_params()
        self.update_transforms()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())