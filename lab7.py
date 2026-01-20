import sys
import os
import math
from PySide6.QtCore import Qt, QPointF, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QTransform, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QSpinBox,
    QGroupBox, QPushButton, QSizePolicy
)

# --- FIX FOR MACOS QT COCOA ERROR ---
try:
    import PySide6

    dirname = os.path.dirname(PySide6.__file__)
    plugin_path = os.path.join(dirname, 'plugins', 'platforms')
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path
except ImportError:
    pass


# 1. ЛОГІКА L-СИСТЕМИ (L-System Engine)

class LSystemGenerator:
    def __init__(self, axiom, rules, angle):
        self.axiom = axiom
        self.rules = rules  # Dictionary {'F': 'F-F+F+F-F'}
        self.angle = angle
        self.current_string = axiom
        self.iterations = 0

    def generate(self, iterations):
        """Генерує рядок символів для заданої кількості ітерацій"""
        # Якщо просять те саме, що вже є, не перераховуємо
        if iterations == self.iterations:
            return self.current_string

        # Якщо з нуля
        current = self.axiom
        for _ in range(iterations):
            next_seq = []
            for char in current:
                # Замінюємо символ на правило, якщо воно є, інакше залишаємо символ
                next_seq.append(self.rules.get(char, char))
            current = "".join(next_seq)

        self.current_string = current
        self.iterations = iterations
        return current


# 2. КЛАС ПОЛОТНА (ФРАКТАЛ)

class FractalCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1e1e1e;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Параметри Варіанту 13
        # Axiom: F
        # Rule: F -> F-F+F+F-F
        # Angle: 90
        self.lsystem = LSystemGenerator(
            axiom="F",
            rules={"F": "F-F+F+F-F"},
            angle=90
        )

        self.fractal_path = QPainterPath()
        self.fractal_bounds = QRectF()

        # Параметри перегляду (Zoom/Pan)
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.last_mouse_pos = QPointF()

        # Генеруємо початковий стан (наприклад, 3 ітерації)
        self.update_fractal(3)

    def update_fractal(self, iterations):
        """Перебудовує шлях (Path) фракталу"""
        instruction = self.lsystem.generate(iterations)
        self.build_path(instruction)
        self.update()

    def build_path(self, instruction):
        """Перетворює рядок символів у QPainterPath"""
        path = QPainterPath()
        path.moveTo(0, 0)

        # "Черепашача графіка"
        # Зберігаємо стан: (x, y, кут)
        # Для цього фракталу стек не потрібен (немає '[' ']'), але для універсальності можна було б додати.

        x, y = 0.0, 0.0
        current_angle = 0.0  # Градуси
        step_length = 10.0  # Базова довжина кроку (не важлива, бо ми масштабуємо)

        # Оптимізація: вектори напрямку для 0, 90, 180, 270
        # Але оскільки кут може бути довільним, рахуємо через sin/cos

        for char in instruction:
            if char == 'F':
                rad = math.radians(current_angle)
                nx = x + step_length * math.cos(rad)
                ny = y + step_length * math.sin(rad)
                path.lineTo(nx, ny)
                x, y = nx, ny
            elif char == '+':
                current_angle += self.lsystem.angle
            elif char == '-':
                current_angle -= self.lsystem.angle

        self.fractal_path = path
        self.fractal_bounds = path.boundingRect()

        # Скидаємо трансформації перегляду, щоб фрактал був по центру
        self.fit_to_screen()

    def fit_to_screen(self):
        """Автоматично підбирає масштаб і зсув, щоб фрактал вліз у вікно"""
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        # Цей метод викличеться у paintEvent, коли будуть відомі розміри вікна
        self.auto_fit_pending = True

    # --- ПОДІЇ МИШІ (ZOOM / PAN) ---
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
        zoom_in = event.angleDelta().y() > 0
        factor = 1.1 if zoom_in else 0.9
        self.scale_factor *= factor
        self.update()

    # --- МАЛЮВАННЯ ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Фон
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        w = self.width()
        h = self.height()

        # Автоматичне центрування при першому малюванні або зміні ітерацій
        if getattr(self, 'auto_fit_pending', False):
            if not self.fractal_bounds.isEmpty():
                # Рахуємо масштаб, щоб вписати bounds у w/h з відступами
                padding = 40
                scale_w = (w - padding) / self.fractal_bounds.width()
                scale_h = (h - padding) / self.fractal_bounds.height()
                self.scale_factor = min(scale_w, scale_h)

                # Центруємо
                center_x = self.fractal_bounds.center().x()
                center_y = self.fractal_bounds.center().y()

                # Зсув, щоб центр фракталу співпав з центром екрану
                # (w/2, h/2) - (center_x * scale, center_y * scale)
                # Але ми застосовуємо translate, потім scale.
                # Тому: translate(w/2, h/2) -> scale -> translate(-center_x, -center_y)

                # Для простої реалізації в transform:
                self.offset_x = w / 2
                self.offset_y = h / 2
                self.center_correction_x = -center_x
                self.center_correction_y = -center_y

            self.auto_fit_pending = False

        # Застосування трансформацій
        transform = QTransform()

        # 1. Зсув користувача + центр екрану
        transform.translate(self.offset_x, self.offset_y)

        # 2. Масштаб
        transform.scale(self.scale_factor, self.scale_factor)

        # 3. Зсув, щоб центр фракталу був у (0,0) локальних координат
        # Якщо ми ще не рахували автофіт, беремо центр bounds
        cx = self.fractal_bounds.center().x()
        cy = self.fractal_bounds.center().y()
        transform.translate(-cx, -cy)

        painter.setTransform(transform)

        # Малюємо фрактал
        # Використовуємо "Cosmetic" ручку, щоб товщина лінії не змінювалася при зумі
        pen = QPen(QColor("#00ffcc"), 1.5)  # Neon Cyan
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawPath(self.fractal_path)

        # Скидаємо трансформацію для тексту
        painter.resetTransform()
        painter.setPen(QColor("white"))
        painter.drawText(10, 20, f"Variant 13: Quadratic Koch Curve (Type 1)")
        painter.drawText(10, 35, f"Rule: F -> F-F+F+F-F | Angle: 90")
        painter.drawText(10, 50, f"Zoom: {self.scale_factor:.2f}x")


# 3. ГОЛОВНЕ ВІКНО

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Лабораторна №7: Фрактали (L-System)")
        self.resize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # --- ПАНЕЛЬ КЕРУВАННЯ ---
        controls = QWidget()
        controls.setFixedWidth(250)
        controls.setStyleSheet("background-color: #2d2d2d; color: white;")
        ctrl_layout = QVBoxLayout(controls)

        # Група 1: Налаштування
        grp_sets = QGroupBox("Параметри")
        grp_sets.setStyleSheet(
            "QGroupBox { border: 1px solid gray; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        l_sets = QVBoxLayout()

        lbl_iter = QLabel("Ітерації (глибина):")
        self.spin_iter = QSpinBox()
        self.spin_iter.setRange(0, 6)  # Обмежуємо до 6, бо експоненціальний ріст точок
        self.spin_iter.setValue(3)
        self.spin_iter.setStyleSheet("background-color: #404040; color: white; padding: 5px;")
        self.spin_iter.valueChanged.connect(self.update_view)

        l_sets.addWidget(lbl_iter)
        l_sets.addWidget(self.spin_iter)

        btn_reset = QPushButton("Центрувати вигляд")
        btn_reset.setStyleSheet("background-color: #007acc; color: white; padding: 8px; border-radius: 4px;")
        btn_reset.clicked.connect(self.reset_view)
        l_sets.addWidget(btn_reset)

        grp_sets.setLayout(l_sets)
        ctrl_layout.addWidget(grp_sets)

        # Інфо
        lbl_info = QLabel(
            "<b>Управління:</b><br>"
            "- Колесо миші: Зум<br>"
            "- ЛКМ + Рух: Переміщення<br><br>"
            "<i>Чим більше ітерацій, тим<br>більше часу займає<br>генерація.</i>"
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #aaaaaa;")
        ctrl_layout.addWidget(lbl_info)

        ctrl_layout.addStretch()

        # --- ПОЛОТНО ---
        self.canvas = FractalCanvas()

        layout.addWidget(controls)
        layout.addWidget(self.canvas)

    def update_view(self):
        val = self.spin_iter.value()
        self.canvas.update_fractal(val)

    def reset_view(self):
        self.canvas.fit_to_screen()
        self.canvas.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())