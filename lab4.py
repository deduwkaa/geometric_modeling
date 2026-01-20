import sys
import math
from PySide6.QtCore import Qt, QPointF, QTimer, QLineF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QPushButton, QSizePolicy, QCheckBox, QMenu
)

# 1. КЛАС ТОЧКИ (Node)

class BezierNode:
    def __init__(self, pos, type='corner'):
        self.pos = pos  # Основна точка (червона)
        self.handle_in = pos  # Вхідний вусик (зелений)
        self.handle_out = pos  # Вихідний вусик (зелений)
        self.type = type  # 'smooth' (гладка) або 'corner' (злам)

    def set_handles(self, h_in, h_out):
        self.handle_in = h_in
        self.handle_out = h_out

# 2. КЛАС ПОЛОТНА (CANVAS)

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #2b2b2b;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Вмикаємо кастомне меню (ПКМ)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # -- ІНІЦІАЛІЗАЦІЯ КОНТУРУ --
        # Формат: (x, y, тип_точки)
        raw_points = [
            (0, 200, 'corner'),  # Топ
            (25, 160, 'smooth'),  # Праве вітрило
            (50, 100, 'smooth'),
            (65, 50, 'corner'),
            (10, 50, 'corner'),
            (150, 20, 'corner'),  # Корпус право
            (100, -30, 'smooth'),
            (40, -45, 'smooth'),
            (-40, -45, 'smooth'),  # Корпус ліво
            (-100, -30, 'smooth'),
            (-150, 20, 'corner'),
            (-10, 50, 'corner'),  # Ліве вітрило
            (-70, 50, 'corner'),
            (-35, 140, 'smooth')
        ]

        self.nodes = []
        for x, y, t in raw_points:
            self.nodes.append(BezierNode(QPointF(x, y), t))

        self.auto_calculate_handles()

        # Цільові точки для анімації (коло)
        self.target_nodes = []
        radius = 160
        for i in range(len(self.nodes)):
            angle = 2 * math.pi * i / len(self.nodes) + math.pi / 2
            pos = QPointF(radius * math.cos(angle), radius * math.sin(angle))
            node = BezierNode(pos, 'smooth')
            # Спрощені ручки для кола
            node.handle_in = pos
            node.handle_out = pos
            self.target_nodes.append(node)

        # Стан
        self.show_skeleton = True
        self.transform_matrix = QTransform()

        # Інтерактив
        self.selected_node_idx = -1
        self.selected_handle_type = None
        self.drag_radius = 10  # Радіус для перетягування ЛКМ
        self.last_mouse_pos = QPointF()
        self.last_node_pos_drag = QPointF()

        # Анімація та трансформації
        self.is_animating = False
        self.anim_progress = 0.0
        self.tr_dx = 0;
        self.tr_dy = 0;
        self.tr_rot = 0;
        self.tr_sx = 1;
        self.tr_sy = 1

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

    # --- ВИПРАВЛЕНИЙ МЕТОД КОНТЕКСТНОГО МЕНЮ ---
    def show_context_menu(self, pos):
        if self.is_animating: return

        # Шукаємо точку, перевіряючи відстань В ПІКСЕЛЯХ на екрані
        target_idx = -1
        min_dist = float('inf')
        screen_hit_radius = 20  # Радіус попадання 20 пікселів

        for i, node in enumerate(self.nodes):
            # Переводимо координату точки зі світу на екран
            screen_node_pos = self.transform_matrix.map(node.pos)

            # Відстань між кліком миші та точкою на екрані
            dist = (screen_node_pos - QPointF(pos)).manhattanLength()

            if dist < screen_hit_radius and dist < min_dist:
                min_dist = dist
                target_idx = i

        if target_idx != -1:
            menu = QMenu(self)
            node = self.nodes[target_idx]

            # Дії меню
            action_smooth = QAction("Зробити Гладкою (Smooth)", self)
            action_smooth.setCheckable(True)
            action_smooth.setChecked(node.type == 'smooth')
            action_smooth.triggered.connect(lambda: self.set_node_type(target_idx, 'smooth'))

            action_corner = QAction("Зробити Зламом (Corner)", self)
            action_corner.setCheckable(True)
            action_corner.setChecked(node.type == 'corner')
            action_corner.triggered.connect(lambda: self.set_node_type(target_idx, 'corner'))

            menu.addAction(action_smooth)
            menu.addAction(action_corner)

            # Показуємо меню
            menu.exec(self.mapToGlobal(pos))

    def set_node_type(self, idx, type_):
        self.nodes[idx].type = type_
        if type_ == 'smooth':
            # Якщо стала гладкою, вирівнюємо вусики
            self.update_handles_smoothness(idx, 'out')
        self.update()

    # --- ЛКМ: ПЕРЕТЯГУВАННЯ ---
    def mousePressEvent(self, event):
        pos = self.get_logical_pos(event.position())

        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_animating:
                # 1. Перевірка вусиків (вони дрібніші, пріоритет)
                if self.show_skeleton:
                    for i, node in enumerate(self.nodes):
                        if (node.handle_in - pos).manhattanLength() < self.drag_radius:
                            self.selected_node_idx = i
                            self.selected_handle_type = 'in'
                            return
                        if (node.handle_out - pos).manhattanLength() < self.drag_radius:
                            self.selected_node_idx = i
                            self.selected_handle_type = 'out'
                            return

                # 2. Перевірка точок (радіус трохи більший)
                for i, node in enumerate(self.nodes):
                    if (node.pos - pos).manhattanLength() < self.drag_radius * 1.5:
                        self.selected_node_idx = i
                        self.selected_handle_type = 'node'
                        self.last_node_pos_drag = node.pos
                        return

            # Якщо промахнулися - рухаємо сцену
            self.last_mouse_pos = event.position()
            self.selected_node_idx = -1

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
            self.tr_dx += delta.x()
            self.tr_dy += delta.y()
            self.last_mouse_pos = event.position()
            self.update_transform()

    def mouseReleaseEvent(self, event):
        self.selected_node_idx = -1
        self.selected_handle_type = None

    # --- ТРАНСФОРМАЦІЇ ---
    def update_transform(self):
        t = QTransform()
        cx = self.width() / 2
        cy = self.height() / 2
        t.translate(cx + self.tr_dx, cy + self.tr_dy)
        t.scale(self.tr_sx, -self.tr_sy)
        t.rotate(self.tr_rot)
        self.transform_matrix = t
        self.update()

    def get_logical_pos(self, screen_pos):
        t_inv, ok = self.transform_matrix.inverted()
        if ok:
            return t_inv.map(screen_pos)
        return screen_pos

    # --- АНІМАЦІЯ ---
    def update_animation_state(self, progress):
        self.anim_progress = progress
        for i in range(len(self.nodes)):
            n_curr = self.nodes[i]
            n_targ = self.target_nodes[i]
            n_curr.pos = self.lerp(n_curr.pos, n_targ.pos, progress)
            n_curr.handle_in = self.lerp(n_curr.handle_in, n_targ.handle_in, progress)
            n_curr.handle_out = self.lerp(n_curr.handle_out, n_targ.handle_out, progress)
        self.update()

    def lerp(self, p1, p2, t):
        return p1 + (p2 - p1) * 0.05

    # --- МАЛЮВАННЯ ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#2b2b2b"))

        painter.setTransform(self.transform_matrix)
        self.draw_grid(painter)

        # Контур
        path = QPainterPath()
        n = len(self.nodes)
        if n > 0:
            path.moveTo(self.nodes[0].pos)
            for i in range(n):
                curr = self.nodes[i]
                next_node = self.nodes[(i + 1) % n]
                path.cubicTo(curr.handle_out, next_node.handle_in, next_node.pos)

        pen = QPen(QColor("#0099FF"), 2);
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QColor(26, 58, 90, 150))
        painter.drawPath(path)

        # Скелет
        if self.show_skeleton:
            pen_skel = QPen(QColor("#808080"), 1, Qt.DashLine);
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

        # Точки
        for node in self.nodes:
            painter.setPen(Qt.NoPen)
            if node.type == 'smooth':
                painter.setBrush(QColor("#FF0000"))
                r = 6 / self.tr_sx
                painter.drawEllipse(node.pos, r, r)
            else:
                painter.setBrush(QColor("#FF3333"))  # Трохи світліший квадрат для зламу
                r = 5 / self.tr_sx
                painter.drawRect(node.pos.x() - r, node.pos.y() - r, r * 2, r * 2)

    def draw_grid(self, painter):
        pen = QPen(QColor("#505050"), 0);
        pen.setCosmetic(True)
        painter.setPen(pen)
        limit = 2000;
        step = 50
        for i in range(-limit, limit, step):
            painter.drawLine(i, -limit, i, limit)
            painter.drawLine(-limit, i, limit, i)
        pen.setColor(Qt.black);
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(-limit, 0, limit, 0)
        painter.drawLine(0, -limit, 0, limit)


# 3. ГОЛОВНЕ ВІКНО

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №4: Гладкі контури")
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Панель
        controls = QWidget();
        controls.setFixedWidth(300)
        ctrl_layout = QVBoxLayout(controls)

        grp_opts = QGroupBox("Керування")
        vbox = QVBoxLayout()
        self.chk_skel = QCheckBox("Показати каркас");
        self.chk_skel.setChecked(True)
        self.chk_skel.stateChanged.connect(self.toggle_skel)
        vbox.addWidget(self.chk_skel)
        vbox.addWidget(QLabel("<b>ПКМ по червоній точці:</b><br>Змінити тип (Smooth/Corner)"))
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
        layout.addWidget(controls)
        layout.addWidget(self.canvas)

        self.timer = QTimer();
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.anim_tick)

    def toggle_skel(self):
        self.canvas.show_skeleton = self.chk_skel.isChecked()
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