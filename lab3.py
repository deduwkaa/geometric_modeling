import sys
import math
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QDoubleSpinBox,
    QGroupBox, QPushButton, QSizePolicy, QCheckBox, QMenu
)


# 1. МАТЕМАТИЧНЕ ЯДРО (Formula 1.2: Engineering Form)

class EngineeringMath:
    @staticmethod
    def get_point(u, rA, rB, rC, rD, wA, wB, wC, wD):
        """
        Реалізація формули (1.2) з методички (Раціональні криві Безьє 3-го порядку).
        Враховує координати 4 точок і 4 ваги.
        """
        mu = 1 - u
        mu2 = mu * mu
        mu3 = mu2 * mu
        u2 = u * u
        u3 = u2 * u

        b0 = mu3  # (1-u)^3
        b1 = 3 * u * mu2  # 3u(1-u)^2
        b2 = 3 * u2 * mu  # 3u^2(1-u)
        b3 = u3  # u^3

        # Чисельник
        nx = (rA.x() * wA * b0) + (rB.x() * wB * b1) + (rC.x() * wC * b2) + (rD.x() * wD * b3)
        ny = (rA.y() * wA * b0) + (rB.y() * wB * b1) + (rC.y() * wC * b2) + (rD.y() * wD * b3)

        # Знаменник
        denom = (wA * b0) + (wB * b1) + (wC * b2) + (wD * b3)

        if abs(denom) < 1e-6: return rA
        return QPointF(nx / denom, ny / denom)


# 2. КЛАС ТОЧКИ (Node) - (виправлений)

class Node:
    def __init__(self, pos, type='corner'):
        self.pos = pos  # Основна точка (A або D)
        self.handle_in = pos  # Вхідний вусик (C)
        self.handle_out = pos  # Вихідний вусик (B)
        self.type = type

        # Зберігаємо ваги окремо для кожної частини вузла
        self.w_pos = 1.0  # Вага червоної точки
        self.w_in = 1.0  # Вага зеленого вхідного вусика
        self.w_out = 1.0  # Вага зеленого вихідного вусика


# 3. КЛАС ПОЛОТНА (CANVAS)

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #2b2b2b;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # -- КОНТУР ЯХТИ --
        raw_points = [
            (0, 200, 'corner'), (25, 160, 'smooth'), (50, 100, 'smooth'),
            (65, 50, 'corner'), (10, 50, 'corner'), (150, 20, 'corner'),
            (100, -30, 'smooth'), (40, -45, 'smooth'), (-40, -45, 'smooth'),
            (-100, -30, 'smooth'), (-150, 20, 'corner'), (-10, 50, 'corner'),
            (-70, 50, 'corner'), (-35, 140, 'smooth')
        ]

        self.nodes = []
        for x, y, t in raw_points:
            self.nodes.append(Node(QPointF(x, y), t))

        self.auto_calculate_handles()

        # Цільові точки для анімації
        self.target_nodes = []
        radius = 160
        for i in range(len(self.nodes)):
            angle = 2 * math.pi * i / len(self.nodes) + math.pi / 2
            pos = QPointF(radius * math.cos(angle), radius * math.sin(angle))
            node = Node(pos, 'smooth')
            node.handle_in = pos
            node.handle_out = pos
            # Ваги за замовчуванням
            node.w_pos = 1.0;
            node.w_in = 1.0;
            node.w_out = 1.0
            self.target_nodes.append(node)

        self.show_skeleton = True
        self.transform_matrix = QTransform()

        # Інтерактив
        self.selected_node_idx = -1
        self.selected_handle_type = None  # 'node', 'in', 'out'
        self.drag_radius = 10
        self.last_mouse_pos = QPointF()
        self.last_node_pos_drag = QPointF()

        self.is_animating = False
        self.anim_progress = 0.0
        self.tr_dx = 0;
        self.tr_dy = 0;
        self.tr_rot = 0;
        self.tr_sx = 1;
        self.tr_sy = 1

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
        # Шукаємо тільки основні точки для меню типу
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
        if type_ == 'smooth': self.update_handles_smoothness(idx, 'out')
        self.update()

    def mousePressEvent(self, event):
        pos = self.get_logical_pos(event.position())
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_animating:
                # 1. Перевіряємо вусики
                if self.show_skeleton:
                    for i, node in enumerate(self.nodes):
                        if (node.handle_in - pos).manhattanLength() < self.drag_radius:
                            self.set_selection(i, 'in');
                            return
                        if (node.handle_out - pos).manhattanLength() < self.drag_radius:
                            self.set_selection(i, 'out');
                            return
                # 2. Перевіряємо вузли
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

        # Оновлення UI: відображаємо вагу саме тієї точки, яку вибрали (вузол або вусик)
        if self.main_window_ref and idx >= 0:
            self.main_window_ref.spin_weight.setEnabled(True)
            node = self.nodes[idx]
            if type_ == 'node':
                self.main_window_ref.lbl_weight_info.setText("Вага (Точка A/D):")
                self.main_window_ref.spin_weight.setValue(node.w_pos)
            elif type_ == 'in':
                self.main_window_ref.lbl_weight_info.setText("Вага (Вусик C):")
                self.main_window_ref.spin_weight.setValue(node.w_in)
            elif type_ == 'out':
                self.main_window_ref.lbl_weight_info.setText("Вага (Вусик B):")
                self.main_window_ref.spin_weight.setValue(node.w_out)
        elif self.main_window_ref:
            self.main_window_ref.lbl_weight_info.setText("Виберіть точку:")
            self.main_window_ref.spin_weight.setEnabled(False)

        self.update()

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
            # Інтерполяція ваг для всіх точок
            n_curr.w_pos = n_curr.w_pos + (n_targ.w_pos - n_curr.w_pos) * 0.05
            n_curr.w_in = n_curr.w_in + (n_targ.w_in - n_curr.w_in) * 0.05
            n_curr.w_out = n_curr.w_out + (n_targ.w_out - n_curr.w_out) * 0.05
        self.update()

    def lerp(self, p1, p2, t):
        return p1 + (p2 - p1) * 0.05

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#2b2b2b"))
        painter.setTransform(self.transform_matrix)
        self.draw_grid(painter)

        path = QPainterPath()
        n = len(self.nodes)
        steps = 40

        if n > 0:
            path.moveTo(self.nodes[0].pos)
            for i in range(n):
                # Сегмент i: від nodes[i] до nodes[i+1]
                curr = self.nodes[i]
                next_node = self.nodes[(i + 1) % n]

                # Точки A, B, C, D
                rA = curr.pos
                rB = curr.handle_out
                rC = next_node.handle_in
                rD = next_node.pos

                # Ваги A, B, C, D (Тепер беремо реальні ваги!)
                wA = curr.w_pos
                wB = curr.w_out  # Вага вихідного вусика
                wC = next_node.w_in  # Вага вхідного вусика наступного вузла
                wD = next_node.w_pos

                # Малювання сегмента
                for s in range(1, steps + 1):
                    u = s / steps
                    pt = EngineeringMath.get_point(u, rA, rB, rC, rD, wA, wB, wC, wD)
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
            painter.setBrush(QColor("#00FF00"))  # Зелені - B і C
            r = 4 / self.tr_sx
            for node in self.nodes:
                painter.drawEllipse(node.handle_in, r, r)
                painter.drawEllipse(node.handle_out, r, r)

        for i, node in enumerate(self.nodes):
            painter.setPen(Qt.NoPen)
            # Підсвітка вибору
            if i == self.selected_node_idx:
                if self.selected_handle_type == 'node':
                    painter.setBrush(QColor("#FFFF00"))
                else:
                    painter.setBrush(QColor("#FF0000")) if node.type == 'smooth' else painter.setBrush(
                        QColor("#FF3333"))
            else:
                if node.type == 'smooth':
                    painter.setBrush(QColor("#FF0000"))
                else:
                    painter.setBrush(QColor("#FF3333"))

            r = (6 if node.type == 'smooth' else 5) / self.tr_sx
            if node.type == 'smooth':
                painter.drawEllipse(node.pos, r, r)
            else:
                painter.drawRect(node.pos.x() - r, node.pos.y() - r, r * 2, r * 2)

            # Якщо вибрано вусик, підсвітимо його жовтим
            if i == self.selected_node_idx:
                if self.selected_handle_type == 'in':
                    painter.setBrush(QColor("#FFFF00"))
                    painter.drawEllipse(node.handle_in, 4 / self.tr_sx, 4 / self.tr_sx)
                elif self.selected_handle_type == 'out':
                    painter.setBrush(QColor("#FFFF00"))
                    painter.drawEllipse(node.handle_out, 4 / self.tr_sx, 4 / self.tr_sx)

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
        self.setWindowTitle("Лабораторна №3: Інженерний вигляд")
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

        # UI ваги
        self.lbl_weight_info = QLabel("Виберіть точку:")
        vbox.addWidget(self.lbl_weight_info)
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0.1, 50.0)
        self.spin_weight.setSingleStep(0.1)
        self.spin_weight.setValue(1.0)
        self.spin_weight.setEnabled(False)
        self.spin_weight.valueChanged.connect(self.update_weight)

        vbox.addWidget(self.spin_weight)
        vbox.addWidget(self.chk_skel)
        vbox.addWidget(QLabel("<b>ПКМ по точці:</b> Тип"))
        vbox.addWidget(QLabel("<b>ЛКМ:</b> Виділити/Перетягнути"))
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
        self.canvas.main_window_ref = self
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
        type_ = self.canvas.selected_handle_type
        if idx >= 0:
            val = self.spin_weight.value()
            if type_ == 'node':
                self.canvas.nodes[idx].w_pos = val
            elif type_ == 'in':
                self.canvas.nodes[idx].w_in = val
            elif type_ == 'out':
                self.canvas.nodes[idx].w_out = val
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