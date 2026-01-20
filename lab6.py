import sys
import os
import math
import numpy as np

# FIX FOR MACOS QT COCOA ERROR
try:
    import PySide6

    dirname = os.path.dirname(PySide6.__file__)
    plugin_path = os.path.join(dirname, 'plugins', 'platforms')
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
except ImportError:
    pass


from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QPushButton, QSizePolicy, QCheckBox
)


# 1. МАТЕМАТИКА ТРАНСФОРМАЦІЙ

class Transform3D:
    @staticmethod
    def rotate_x(angle_deg):
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])

    @staticmethod
    def rotate_y(angle_deg):
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])

    @staticmethod
    def rotate_z(angle_deg):
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

    @staticmethod
    def translate(dx, dy, dz):
        return np.array([[1, 0, 0, dx], [0, 1, 0, dy], [0, 0, 1, dz], [0, 0, 0, 1]])

    @staticmethod
    def scale(sx, sy, sz):
        return np.array([[sx, 0, 0, 0], [0, sy, 0, 0], [0, 0, sz, 0], [0, 0, 0, 1]])


# 2. ГЕОМЕТРІЯ ПОВЕРХНІ (GRID)

class SurfaceGeometry:
    @staticmethod
    def get_point(u, v, R, stretch):
        """
        Варіант 13: Наполовину еліпсоїд (z>0), наполовину сфера (z<0).
        """
        x = R * math.cos(u) * math.cos(v)
        y = R * math.cos(u) * math.sin(v)
        base_z = R * math.sin(u)

        if base_z > 0:
            z = base_z * stretch
        else:
            z = base_z
        return np.array([x, y, z, 1.0])

    @staticmethod
    def generate_grid(R, stretch, u_steps, v_steps):
        """Генерує сітку точок [rows][cols]"""
        grid = []
        # U від -pi/2 (південний полюс) до pi/2 (північний)
        us = np.linspace(-math.pi / 2, math.pi / 2, u_steps)
        # V від 0 до 2pi (по колу)
        vs = np.linspace(0, 2 * math.pi, v_steps)

        for u in us:
            row = []
            for v in vs:
                row.append(SurfaceGeometry.get_point(u, v, R, stretch))
            grid.append(row)
        return grid

    @staticmethod
    def map_contour(contour_2d, R, stretch, u_off, v_off, uv_rot_deg, uv_scale):
        """
        Накладає 2D контур на поверхню.
        """
        points_3d = []

        # Центр контуру (приблизно) для обертання
        cx = 0
        cy = 50

        rad_rot = math.radians(uv_rot_deg)
        cos_r = math.cos(rad_rot)
        sin_r = math.sin(rad_rot)

        # Коефіцієнт масштабування (пікселі -> радіани)
        # Яхта велика (~200px), а сфера це 3.14 (PI). Треба сильно зменшити.
        scale = 0.01 * (uv_scale / 100.0)

        for pt in contour_2d:
            # 1. Локальні координати відносно центру яхти
            lx = pt[0] - cx
            ly = pt[1] - cy

            # 2. Обертання в 2D (на площині яхти)
            rx = lx * cos_r - ly * sin_r
            ry = lx * sin_r + ly * cos_r

            # 3. Переведення в UV (сферичні координати)
            # V (довгота) += rx
            # U (широта) += ry
            v_angle = rx * scale + v_off
            u_angle = ry * scale + u_off

            # Клемпінг U, щоб не вилізти за полюси
            u_angle = max(-math.pi / 2 + 0.05, min(math.pi / 2 - 0.05, u_angle))

            points_3d.append(SurfaceGeometry.get_point(u_angle, v_angle, R, stretch))

        return points_3d


# 3. КЛАС ПОЛОТНА

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Змінюємо фон на світло-сірий, як на "гарних" скріншотах, щоб було краще видно сітку
        self.setStyleSheet("background-color: #f0f0f0;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # КОНТУР ЯХТИ
        self.boat_contour = [
            (0, 200), (25, 160), (50, 100), (65, 50), (10, 50),
            (150, 20), (100, -30), (40, -45), (-40, -45), (-100, -30), (-150, 20),
            (-10, 50), (-70, 50), (-35, 140), (0, 200)
        ]

        # --- Defaults ---
        self.surf_R = 100
        self.surf_stretch = 1.5

        self.model_dx = 0
        self.model_dy = 0
        self.model_rot_x = 20
        self.model_rot_y = -30
        self.model_rot_z = 0
        self.model_scale = 100

        self.uv_u = 0.2
        self.uv_v = 0.0
        self.uv_rot = 0
        self.uv_scale_pct = 100

        self.view_dist = 600

    def project_point(self, vec4, width, height, mvp_matrix):
        """Проекція однієї точки: 3D -> 2D Screen"""
        # MVP Transformation
        p = mvp_matrix @ vec4
        x, y, z = p[0], p[1], p[2]

        # Perspective Divide
        # d / (d - z)
        # Важливо: якщо z близько до d, буде ділення на нуль або вибух.
        if (self.view_dist - z) < 1:
            factor = 0  # Point is behind camera or on lens
        else:
            factor = self.view_dist / (self.view_dist - z)

        screen_x = width / 2 + x * factor
        screen_y = height / 2 - y * factor
        return QPointF(screen_x, screen_y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Обчислення матриць
        # Матриця моделі (світ)
        sc = self.model_scale / 100.0
        M_model = Transform3D.translate(self.model_dx, self.model_dy, 0) @ \
                  Transform3D.rotate_z(self.model_rot_z) @ \
                  Transform3D.rotate_y(self.model_rot_y) @ \
                  Transform3D.rotate_x(self.model_rot_x) @ \
                  Transform3D.scale(sc, sc, sc)

        # Для триточкової перспективи ми просто трансформуємо об'єкт.
        # Камера дивиться в центр (0,0).

        w = self.width()
        h = self.height()

        # 2. Генеруємо 3D точки сітки
        u_res = 18  # Кількість ліній широти
        v_res = 24  # Кількість ліній довготи
        grid_3d = SurfaceGeometry.generate_grid(self.surf_R, self.surf_stretch, u_res, v_res)

        # 3. Проектуємо сітку на екран (Projected Grid)
        proj_grid = []
        for row in grid_3d:
            proj_row = []
            for p3d in row:
                screen_pt = self.project_point(p3d, w, h, M_model)
                proj_row.append(screen_pt)
            proj_grid.append(proj_row)

        # 4. Малюємо СІТКУ (Wireframe)
        pen_wire = QPen(QColor(160, 160, 160), 1)  # Світло-сірий для задніх ліній
        painter.setPen(pen_wire)

        # Малюємо горизонталі та вертикалі
        rows = len(proj_grid)
        cols = len(proj_grid[0])

        for i in range(rows):
            for j in range(cols):
                curr = proj_grid[i][j]

                # Лінія "вниз" (по U)
                if i < rows - 1:
                    next_u = proj_grid[i + 1][j]
                    painter.drawLine(curr, next_u)

                # Лінія "вправо" (по V)
                if j < cols - 1:
                    next_v = proj_grid[i][j + 1]
                    painter.drawLine(curr, next_v)
                else:
                    # Замикання кола (останній з першим у рядку) -> для сфери це важливо
                    # Але в масиві вони не з'єднані. З'єднаємо [i][-1] з [i][0]?
                    # Для точної сфери v=0 і v=2pi співпадають, тому лінії співпадуть.
                    pass

        # 5. Малюємо ЯХТУ (Контур)
        curve_3d = SurfaceGeometry.map_contour(
            self.boat_contour,
            self.surf_R, self.surf_stretch,
            self.uv_u, self.uv_v, self.uv_rot, self.uv_scale_pct
        )

        curve_2d = []
        for p3d in curve_3d:
            curve_2d.append(self.project_point(p3d, w, h, M_model))

        pen_curve = QPen(QColor("red"), 2)
        painter.setPen(pen_curve)

        path = QPainterPath()
        if len(curve_2d) > 0:
            path.moveTo(curve_2d[0])
            for i in range(1, len(curve_2d)):
                path.lineTo(curve_2d[i])
            path.closeSubpath()  # Яхта замкнена
        painter.drawPath(path)


# 4. ГОЛОВНЕ ВІКНО

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №6: Триточкова перспектива")
        self.resize(1200, 750)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # --- ПАНЕЛЬ ---
        self.canvas = CanvasWidget()
        layout.addWidget(self.canvas, stretch=3)

        controls = QWidget()
        controls.setFixedWidth(320)
        controls.setStyleSheet("background-color: #e0e0e0;")  # Сіра панель
        ctrl_layout = QVBoxLayout(controls)
        layout.addWidget(controls, stretch=1)

        # 1. Параметри Поверхні
        grp_surf = QGroupBox("1. Параметри Поверхні")
        l_surf = QVBoxLayout()
        self.spin_R = self.add_slider(l_surf, "Радіус (R):", 100, 10, 200)
        self.spin_stretch = self.add_slider(l_surf, "Витяг (Stretch %):", 150, 10, 300)

        self.btn_anim = QPushButton("Старт/Стоп Анімація")
        self.btn_anim.setCheckable(True)
        self.btn_anim.setStyleSheet("background-color: #00AA00; color: white; font-weight: bold;")
        self.btn_anim.clicked.connect(self.toggle_anim)
        l_surf.addWidget(self.btn_anim)
        grp_surf.setLayout(l_surf)
        ctrl_layout.addWidget(grp_surf)

        # 2. Трансформація Світ (World)
        grp_world = QGroupBox("2. Трансформація Поверхні (Світ)")
        l_world = QVBoxLayout()
        self.spin_rot_x = self.add_slider(l_world, "Обертання X:", 20, -180, 180)
        self.spin_rot_y = self.add_slider(l_world, "Обертання Y:", -30, -180, 180)
        self.spin_rot_z = self.add_slider(l_world, "Обертання Z:", 0, -180, 180)
        self.spin_scale = self.add_slider(l_world, "Масштаб (%):", 100, 10, 300)
        self.spin_dx = self.add_slider(l_world, "Зсув X:", 0, -200, 200)
        self.spin_dy = self.add_slider(l_world, "Зсув Y:", 0, -200, 200)
        self.spin_dist = self.add_slider(l_world, "Проекція (d):", 600, 200, 2000)
        grp_world.setLayout(l_world)
        ctrl_layout.addWidget(grp_world)

        # 3. Трансформація Контуру (UV)
        grp_uv = QGroupBox("3. Трансформація Контуру (на поверхні)")
        l_uv = QVBoxLayout()
        # Слайдери для UV дають плавний рух
        self.spin_u = self.add_slider(l_uv, "Зсув U (широта):", 20, -150, 150)  # * 0.01
        self.spin_v = self.add_slider(l_uv, "Зсув V (довгота):", 0, -314, 314)  # * 0.01
        self.spin_uv_rot = self.add_slider(l_uv, "Обертання Контуру:", 0, -180, 180)
        self.spin_uv_scale = self.add_slider(l_uv, "Масштаб Контуру (%):", 100, 10, 200)
        grp_uv.setLayout(l_uv)
        ctrl_layout.addWidget(grp_uv)

        ctrl_layout.addStretch()

        # Timer
        self.timer = QTimer()
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.anim_tick)
        self.anim_phase = 0

    def add_slider(self, layout, label_text, val, min_v, max_v):
        lbl = QLabel(f"{label_text} {val}")

        # Горизонтальний лейаут для слайдера
        h = QHBoxLayout()
        sl = QSliderWithLabel(Qt.Horizontal, lbl, label_text)
        sl.setRange(min_v, max_v)
        sl.setValue(val)
        sl.valueChanged.connect(self.update_params)

        layout.addWidget(lbl)
        layout.addWidget(sl)
        return sl

    def update_params(self):
        c = self.canvas
        c.surf_R = self.spin_R.value()
        c.surf_stretch = self.spin_stretch.value() / 100.0

        c.model_rot_x = self.spin_rot_x.value()
        c.model_rot_y = self.spin_rot_y.value()
        c.model_rot_z = self.spin_rot_z.value()
        c.model_scale = self.spin_scale.value()
        c.model_dx = self.spin_dx.value()
        c.model_dy = self.spin_dy.value()
        c.view_dist = self.spin_dist.value()

        c.uv_u = self.spin_u.value() * 0.01
        c.uv_v = self.spin_v.value() * 0.01
        c.uv_rot = self.spin_uv_rot.value()
        c.uv_scale_pct = self.spin_uv_scale.value()

        c.update()

    def toggle_anim(self):
        if self.btn_anim.isChecked():
            self.timer.start()
        else:
            self.timer.stop()

    def anim_tick(self):
        self.anim_phase += 0.1

        # 1. "Дихання" форми
        stretch_val = 150 + 50 * math.sin(self.anim_phase)
        self.spin_stretch.setValue(int(stretch_val))

        # 2. Обертання сцени
        curr_rot = self.spin_rot_y.value()
        self.spin_rot_y.setValue((curr_rot + 1) % 360 if curr_rot < 360 else -360)


# Допоміжний клас для оновлення тексту слайдера
from PySide6.QtWidgets import QSlider


class QSliderWithLabel(QSlider):
    def __init__(self, orient, label, prefix):
        super().__init__(orient)
        self.label = label
        self.prefix = prefix
        self.valueChanged.connect(self.update_text)

    def update_text(self, val):
        self.label.setText(f"{self.prefix} {val}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())