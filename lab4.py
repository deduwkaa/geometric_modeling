import sys
import math
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QPushButton, QSizePolicy, QCheckBox, QMenu
)


# 1. МАТЕМАТИЧНЕ ЯДРО (Rational Bezier)

class RationalBezierMath:
    @staticmethod
    def get_point(t, p0, p1, p2, p3, w0, w1, w2, w3):
        """
        Розрахунок точки на раціональній кривій Безьє 3-го порядку.
        Формула: P(t) = Sum(wi * Pi * Bi(t)) / Sum(wi * Bi(t))
        де Bi(t) - поліноми Бернштейна.
        """
        t2 = t * t
        t3 = t2 * t
        mt = 1 - t
        mt2 = mt * mt
        mt3 = mt2 * mt

        # Базисні функції Бернштейна
        b0 = mt3
        b1 = 3 * mt2 * t
        b2 = 3 * mt * t2
        b3 = t3

        # Чисельник (зважена сума координат)
        # x(t) = w0*x0*b0 + w1*x1*b1 + ...
        # y(t) = w0*y0*b0 + w1*y1*b1 + ...
        nx = w0 * p0.x() * b0 + w1 * p1.x() * b1 + w2 * p2.x() * b2 + w3 * p3.x() * b3
        ny = w0 * p0.y() * b0 + w1 * p1.y() * b1 + w2 * p2.y() * b2 + w3 * p3.y() * b3

        # Знаменник (сума ваг)
        # w(t) = w0*b0 + w1*b1 + w2*b2 + w3*b3
        d = w0 * b0 + w1 * b1 + w2 * b2 + w3 * b3

        if d == 0:
            return QPointF(0, 0)  # Захист від ділення на нуль

        return QPointF(nx / d, ny / d)


# 2. КЛАС ТОЧКИ (Node)

class BezierNode:
    def __init__(self, pos, type='corner'):
        self.pos = pos  # P0 / P3 (Вузол)
        self.handle_in = pos  # Вхідний контроль (для попереднього сегмента)
        self.handle_out = pos  # Вихідний контроль (P1 для поточного)
        self.type = type  # 'smooth' або 'corner'

        # ВАГА (Weight) для раціональної кривої
        # Для спрощення інтерфейсу, ця вага впливатиме на "тяжіння" вусиків (P1, P2)
        self.weight = 1.0


# 3. КЛАС ПОЛОТНА (CANVAS)

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #2b2b2b;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # -- ІНІЦІАЛІЗАЦІЯ КОНТУРУ --
        raw_points = [
            (0, 200, 'corner'),
            (25, 160, 'smooth'),
            (50, 100, 'smooth'),
            (65, 50, 'corner'),
            (10, 50, 'corner'),
            (150, 20, 'corner'),
            (100, -30, 'smooth'),
            (40, -45, 'smooth'),
            (-40, -45, 'smooth'),
            (-100, -30, 'smooth'),
            (-150, 20, 'corner'),
            (-10, 50, 'corner'),
            (-70, 50, 'corner'),
            (-35, 140, 'smooth')
        ]

        self.nodes = []
        for x, y, t in raw_points:
            self.nodes.append(BezierNode(QPointF(x, y), t))

        self.auto_calculate_handles()

        # Цільові точки для анімації
        self.target_nodes = []
        radius = 160
        for i in range(len(self.nodes)):
            angle = 2 * math.pi * i / len(self.nodes) + math.pi / 2
            pos = QPointF(radius * math.cos(angle), radius * math.sin(angle))
            node = BezierNode(pos, 'smooth')
            node.handle_in = pos
            node.handle_out = pos
            node.weight = 1.0
            self.target_nodes.append(node)

        # Стан
        self.show_skeleton = True
        self.transform_matrix = QTransform()

        # Інтерактив
        self.selected_node_idx = -1
        self.selected_handle_type = None
        self.drag_radius = 10
        self.last_mouse_pos = QPointF()
        self.last_node_pos_drag = QPointF()

        # Анімація
        self.is_animating = False
        self.anim_progress = 0.0
        self.tr_dx = 0;
        self.tr_dy = 0;
        self.tr_rot = 0;
        self.tr_sx = 1;
        self.tr_sy = 1

        # Посилання на головне вікно для оновлення UI (ваги)
        self.main_window_ref = None

    def auto_calculate_handles(self):
        n = len(self.nodes)
        for i in range(n):
            if self.nodes[i].type == 'corner':
                self.nodes[i].handle_in = self.nodes[i].pos
                self.nodes[i].handle_out = self.nodes[i].pos
                continue
            prev = self.nodes[(i - 1) % n].pos
            curr = self.nodes[i].pos
            next_p = self.nodes[(i + 1) % n].pos
            tangent = (next_p - prev) * 0.2
            self.nodes[i].handle_in = curr - tangent
            self.nodes[i].handle_out = curr + tangent

    def update_handles_smoothness(self, idx, changed_handle_type):
        node = self.nodes[idx]
        if node.type == 'corner': return
        pos = node.pos
        if changed_handle_type == 'in':
            vec = pos - node.handle_in
            node.handle_out = pos + vec
        elif changed_handle_type == 'out':
            vec = pos - node.handle_out
            node.handle_in = pos + vec

    def show_context_menu(self, pos):
        if self.is_animating: return
        target_idx = -1
        min_dist = float('inf')
        screen_hit_radius = 20

        for i, node in enumerate(self.nodes):
            screen_node_pos = self.transform_matrix.map(node.pos)
            dist = (screen_node_pos - QPointF(pos)).manhattanLength()
            if dist < screen_hit_radius and dist < min_dist:
                min_dist = dist
                target_idx = i

        if target_idx != -1:
            menu = QMenu(self)
            node = self.nodes[target_idx]
            action_smooth = QAction("Smooth", self);
            action_smooth.setCheckable(True);
            action_smooth.setChecked(node.type == 'smooth')
            action_smooth.triggered.connect(lambda: self.set_node_type(target_idx, 'smooth'))
            action_corner = QAction("Corner", self);
            action_corner.setCheckable(True);
            action_corner.setChecked(node.type == 'corner')
            action_corner.triggered.connect(lambda: self.set_node_type(target_idx, 'corner'))
            menu.addAction(action_smooth);
            menu.addAction(action_corner)
            menu.exec(self.mapToGlobal(pos))

    def set_node_type(self, idx, type_):
        self.nodes[idx].type = type_
        if type_ == 'smooth':
            self.update_handles_smoothness(idx, 'out')
        self.update()

    def mousePressEvent(self, event):
        pos = self.get_logical_pos(event.position())
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_animating:
                # Вусики
                if self.show_skeleton:
                    for i, node in enumerate(self.nodes):
                        if (node.handle_in - pos).manhattanLength() < self.drag_radius:
                            self.set_selection(i, 'in');
                            return
                        if (node.handle_out - pos).manhattanLength() < self.drag_radius:
                            self.set_selection(i, 'out');
                            return
                # Точки
                for i, node in enumerate(self.nodes):
                    if (node.pos - pos).manhattanLength() < self.drag_radius * 1.5:
                        self.set_selection(i, 'node');
                        self.last_node_pos_drag = node.pos
                        return

            self.last_mouse_pos = event.position()
            self.set_selection(-1, None)

    def set_selection(self, idx, type_):
        self.selected_node_idx = idx
        self.selected_handle_type = type_
        # Оновлюємо UI (спінбокс ваги)
        if self.main_window_ref:
            if idx >= 0:
                self.main_window_ref.spin_weight.setValue(self.nodes[idx].weight)
                self.main_window_ref.spin_weight.setEnabled(True)
            else:
                self.main_window_ref.spin_weight.setEnabled(False)

    def mouseMoveEvent(self, event):
        pos = self.get_logical_pos(event.position())
        if self.selected_node_idx >= 0:
            node = self.nodes[self.selected_node_idx]
            if self.selected_handle_type == 'node':
                delta = pos - self.last_node_pos_drag
                node.pos = pos
                node.handle_in += delta
                node.handle_out += delta
                self.last_node_pos_drag = pos
            elif self.selected_handle_type == 'in':
                node.handle_in = pos
                self.update_handles_smoothness(self.selected_node_idx, 'in')
            elif self.selected_handle_type == 'out':
                node.handle_out = pos
                self.update_handles_smoothness(self.selected_node_idx, 'out')
            self.update()
        elif event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position() - self.last_mouse_pos
            self.tr_dx += delta.x();
            self.tr_dy += delta.y()
            self.last_mouse_pos = event.position()
            self.update_transform()

    def mouseReleaseEvent(self, event):
        # self.selected_node_idx = -1 # Не скидаємо вибір, щоб можна було міняти вагу
        pass

    def update_transform(self):
        t = QTransform()
        cx = self.width() / 2;
        cy = self.height() / 2
        t.translate(cx + self.tr_dx, cy + self.tr_dy)
        t.scale(self.tr_sx, -self.tr_sy)
        t.rotate(self.tr_rot)
        self.transform_matrix = t
        self.update()

    def get_logical_pos(self, screen_pos):
        t_inv, ok = self.transform_matrix.inverted()
        return t_inv.map(screen_pos) if ok else screen_pos

    def update_animation_state(self, progress):
        self.anim_progress = progress
        for i in range(len(self.nodes)):
            n_curr = self.nodes[i]
            n_targ = self.target_nodes[i]
            n_curr.pos = self.lerp(n_curr.pos, n_targ.pos, progress)
            n_curr.handle_in = self.lerp(n_curr.handle_in, n_targ.handle_in, progress)
            n_curr.handle_out = self.lerp(n_curr.handle_out, n_targ.handle_out, progress)
            # Інтерполяція ваги
            n_curr.weight = n_curr.weight + (n_targ.weight - n_curr.weight) * 0.05
        self.update()

    def lerp(self, p1, p2, t):
        return p1 + (p2 - p1) * 0.05

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#2b2b2b"))
        painter.setTransform(self.transform_matrix)
        self.draw_grid(painter)

        # --- МАЛЮВАННЯ РАЦІОНАЛЬНОЇ КРИВОЇ ---
        path = QPainterPath()
        n = len(self.nodes)

        # Кількість кроків для апроксимації кожного сегмента
        steps_per_segment = 40

        if n > 0:
            path.moveTo(self.nodes[0].pos)
            for i in range(n):
                # Поточний вузол і наступний
                curr_node = self.nodes[i]
                next_node = self.nodes[(i + 1) % n]

                # 4 контрольні точки для сегмента
                p0 = curr_node.pos
                p1 = curr_node.handle_out
                p2 = next_node.handle_in
                p3 = next_node.pos

                # Ваги
                # Крайні точки (P0, P3) зазвичай мають вагу 1 для стиковки
                # Середні точки (P1, P2) беруть вагу відповідних вузлів
                w0 = 1.0
                w1 = curr_node.weight
                w2 = next_node.weight
                w3 = 1.0

                # Вручну розраховуємо точки (інженерний/раціональний вигляд)
                for s in range(1, steps_per_segment + 1):
                    t = s / steps_per_segment
                    pt = RationalBezierMath.get_point(t, p0, p1, p2, p3, w0, w1, w2, w3)
                    path.lineTo(pt)

        pen = QPen(QColor("#0099FF"), 2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QColor(26, 58, 90, 150))
        painter.drawPath(path)

        if self.show_skeleton:
            pen_skel = QPen(QColor("#808080"), 1, Qt.DashLine)
            pen_skel.setCosmetic(True)
            painter.setPen(pen_skel)
            for node in self.nodes:
                painter.drawLine(node.pos, node.handle_in)
                painter.drawLine(node.pos, node.handle_out)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#00FF00"))
            r = 4 / self.tr_sx
            for node in self.nodes:
                painter.drawEllipse(node.handle_in, r, r)
                painter.drawEllipse(node.handle_out, r, r)

        for i, node in enumerate(self.nodes):
            painter.setPen(Qt.NoPen)
            if i == self.selected_node_idx:
                painter.setBrush(QColor("#FFFF00"))  # Підсвітка обраного
            elif node.type == 'smooth':
                painter.setBrush(QColor("#FF0000"))
            else:
                painter.setBrush(QColor("#FF3333"))

            r = (6 if node.type == 'smooth' else 5) / self.tr_sx
            if node.type == 'smooth':
                painter.drawEllipse(node.pos, r, r)
            else:
                painter.drawRect(node.pos.x() - r, node.pos.y() - r, r * 2, r * 2)

    def draw_grid(self, painter):
        pen = QPen(QColor("#505050"), 0);
        pen.setCosmetic(True);
        painter.setPen(pen)
        for i in range(-2000, 2000, 50):
            painter.drawLine(i, -2000, i, 2000);
            painter.drawLine(-2000, i, 2000, i)
        pen.setColor(Qt.black);
        pen.setWidth(2);
        painter.setPen(pen)
        painter.drawLine(-2000, 0, 2000, 0);
        painter.drawLine(0, -2000, 0, 2000)


# 4. ГОЛОВНЕ ВІКНО

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №4: Раціональні криві Безьє")
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        controls = QWidget()
        controls.setFixedWidth(300)
        ctrl_layout = QVBoxLayout(controls)

        grp_opts = QGroupBox("Керування")
        vbox = QVBoxLayout()
        self.chk_skel = QCheckBox("Показати каркас")
        self.chk_skel.setChecked(True)
        self.chk_skel.stateChanged.connect(self.toggle_skel)

        # Додаємо керування вагою
        vbox.addWidget(QLabel("Вага обраної точки (Weight):"))
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0.1, 10.0)
        self.spin_weight.setSingleStep(0.1)
        self.spin_weight.setValue(1.0)
        self.spin_weight.setEnabled(False)  # Активується при виборі точки
        self.spin_weight.valueChanged.connect(self.update_weight)

        vbox.addWidget(self.spin_weight)
        vbox.addWidget(self.chk_skel)
        vbox.addWidget(QLabel("<b>ПКМ по точці:</b> Тип (Smooth/Corner)"))
        vbox.addWidget(QLabel("<b>ЛКМ:</b> Перетягування"))
        grp_opts.setLayout(vbox)
        ctrl_layout.addWidget(grp_opts)

        grp_anim = QGroupBox("Анімація")
        abox = QVBoxLayout()
        self.btn_anim = QPushButton("Старт Анімації")
        self.btn_anim.setCheckable(True)
        self.btn_anim.clicked.connect(self.toggle_anim)
        abox.addWidget(self.btn_anim)
        grp_anim.setLayout(abox)
        ctrl_layout.addWidget(grp_anim)

        ctrl_layout.addStretch()
        self.canvas = CanvasWidget()
        self.canvas.main_window_ref = self  # Передаємо посилання для зворотного зв'язку
        layout.addWidget(controls)
        layout.addWidget(self.canvas)

        self.timer = QTimer()
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.anim_tick)

    def toggle_skel(self):
        self.canvas.show_skeleton = self.chk_skel.isChecked()
        self.canvas.update()

    def update_weight(self):
        idx = self.canvas.selected_node_idx
        if idx >= 0:
            self.canvas.nodes[idx].weight = self.spin_weight.value()
            self.canvas.update()

    def toggle_anim(self):
        self.canvas.is_animating = self.btn_anim.isChecked()
        if self.canvas.is_animating:
            self.timer.start()
        else:
            self.timer.stop()

    def anim_tick(self):
        self.canvas.update_animation_state(0.05)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())