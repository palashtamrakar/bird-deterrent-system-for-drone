import sys
import math
import random
import numpy as np
import time
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget, QProgressBar, QTextEdit, QStatusBar, QCheckBox)
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QLinearGradient
from PySide6.QtCore import Qt, QTimer, QPointF
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class Bird:
    """Represents a bird with different movement behaviors."""
    def __init__(self, start_x, start_y, angle_deg, speed, radar_widget, is_flock_member=False):
        self.x = start_x
        self.y = start_y
        self.angle = math.radians(angle_deg)
        self.speed = speed
        self.active = True
        self.behavior_type = random.choices(['straight', 'curved', 'avoid'], weights=[0.7, 0.2, 0.1])[0]
        self.curve_direction = random.choice([-1, 1])
        self.radar_widget = radar_widget
        self.near_center_time = 0
        self.min_center_distance = 20
        self.threat_level = random.uniform(0.1, 1.0)
        self.last_x = start_x
        self.last_y = start_y
        self.last_update = time.time()
        self.is_flock_member = is_flock_member
        self.flock_id = None
        self.avoiding_sound = False

    def distance_to(self, other):
        """Calculate distance to another bird."""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def get_relative_speed(self, center_x, center_y):
        """Calculate relative speed to drone (m/s) based on position change."""
        current_time = time.time()
        dt = current_time - self.last_update
        if dt > 0:
            dx = self.x - self.last_x
            dy = self.y - self.last_y
            speed_x = dx / dt
            speed_y = dy / dt
            relative_speed = math.sqrt((speed_x)**2 + (speed_y)**2)
            self.last_x = self.x
            self.last_y = self.y
            self.last_update = current_time
            return relative_speed
        return 0.0

    def move(self, center_x, center_y):
        """Update bird position with repulsion and sound wave response."""
        if not self.active:
            return

        # Repulsion from other birds
        for other_bird in self.radar_widget.birds:
            if other_bird != self and self.distance_to(other_bird) < 15:
                dx = self.x - other_bird.x
                dy = self.y - other_bird.y
                angle_offset = math.atan2(dy, dx)
                self.angle = angle_offset + math.radians(random.uniform(-30, 30))

        # Center distance check
        center_distance = math.sqrt((self.x - center_x)**2 + (self.y - center_y)**2)
        if center_distance < self.min_center_distance:
            self.near_center_time += 1
            if self.near_center_time > 30:
                self.active = False
                return
            dx = self.x - center_x
            dy = self.y - center_y
            self.angle = math.atan2(dy, dx) + math.radians(random.uniform(-45, 45))
        else:
            self.near_center_time = 0

        # Sound wave response
        if self.radar_widget.sound_active and center_distance <= self.radar_widget.sound_range:
            if not self.avoiding_sound and random.random() > self.threat_level * 0.5:
                self.avoiding_sound = True
                self.angle += math.radians(random.uniform(90, 180) * random.choice([-1, 1]))
                self.radar_widget.parent.alert_log.append(f"Alert: Bird at ({self.x:.1f}, {self.y:.1f}) avoiding sound wave at {time.strftime('%H:%M:%S')}")

        # Behavior logic
        if self.behavior_type == 'straight':
            dx = center_x - self.x
            dy = center_y - self.y
            self.angle = math.atan2(dy, dx)
        elif self.behavior_type == 'curved':
            dx = center_x - self.x
            dy = center_y - self.y
            target_angle = math.atan2(dy, dx)
            angle_diff = (target_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
            self.angle += 0.05 * self.curve_direction * (1 if angle_diff > 0 else -1)
        elif self.behavior_type == 'avoid':
            dx = self.x - center_x
            dy = self.y - center_y
            self.angle = math.atan2(dy, dx)

        self.angle = self.angle % (2 * math.pi)
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed

class RadarWidget(FigureCanvas):
    """Military-grade radar with enhanced and polished visualization."""
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(15, 15), dpi=100, facecolor='#1a1a1a')
        super().__init__(self.fig)
        self.setStyleSheet("background-color: #1a1a1a; border: 2px solid #333333;")
        self.config = {
            'spawn_interval': 5000,
            'update_interval': 33,
            'bird_speed_range': (1, 3),
            'max_birds': 4,
            'max_range': 300
        }
        self.birds = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_positions)
        self.timer.start(self.config['update_interval'])

        self.spawn_timer = QTimer(self)
        self.spawn_timer.timeout.connect(self.spawn_birds)
        self.spawn_timer.start(self.config['spawn_interval'])

        self.sound_timer = QTimer(self)
        self.sound_timer.timeout.connect(self.emit_sound_wave)
        self.sound_timer.start(5000)
        self.sound_active = False
        self.sound_range = 150
        self.parent = parent

        self.ax = self.fig.add_subplot(111, projection='polar')
        self.ax.set_facecolor('#1a1a1a')
        self.ax.set_theta_zero_location('N')
        self.ax.set_ylim(0, self.config['max_range'])
        self.ax.set_xticks(np.linspace(0, 2*np.pi, 12, endpoint=False))
        self.ax.set_xticklabels(['N', '', 'NE', '', 'E', '', 'SE', '', 'S', '', 'SW', ''])
        self.ax.tick_params(axis='x', colors='#888888', labelsize=10)
        self.draw_radar()

    def spawn_birds(self):
        """Spawn 3-4 birds or occasionally a flock (max 5 birds)."""
        if len([b for b in self.birds if b.active]) >= self.config['max_birds']:
            return

        if random.random() < 0.2:
            flock_size = random.randint(2, 5)
            center_x, center_y = self.config['max_range']/2, self.config['max_range']/2
            angle_deg = random.randint(0, 359)
            radius = self.config['max_range'] * 0.8
            start_x = center_x + radius * math.cos(math.radians(angle_deg))
            start_y = center_y + radius * math.sin(math.radians(angle_deg))
            flock_id = random.randint(1, 1000)
            for _ in range(flock_size):
                offset_x = random.uniform(-10, 10)
                offset_y = random.uniform(-10, 10)
                speed = random.uniform(*self.config['bird_speed_range'])
                bird = Bird(start_x + offset_x, start_y + offset_y, angle_deg, speed, self, is_flock_member=True)
                bird.flock_id = flock_id
                self.birds.append(bird)
        else:
            num_birds = random.randint(1, min(2, self.config['max_birds'] - len([b for b in self.birds if b.active])))
            center_x, center_y = self.config['max_range']/2, self.config['max_range']/2
            for _ in range(num_birds):
                angle_deg = random.randint(0, 359)
                speed = random.uniform(*self.config['bird_speed_range'])
                radius = self.config['max_range'] * 0.8
                start_x = center_x + radius * math.cos(math.radians(angle_deg))
                start_y = center_y + radius * math.sin(math.radians(angle_deg))
                bird = Bird(start_x, start_y, angle_deg + random.uniform(-30, 30), speed, self)
                self.birds.append(bird)

    def update_positions(self):
        """Update bird positions and redraw radar."""
        center_x, center_y = self.config['max_range']/2, self.config['max_range']/2
        radius = self.config['max_range']
        self.birds = [bird for bird in self.birds if bird.active and
                      abs(bird.x - center_x) < radius * 1.5 and
                      abs(bird.y - center_y) < radius * 1.5]
        active_count = len([b for b in self.birds if b.active])
        if active_count > self.config['max_birds']:
            excess_birds = sorted(self.birds, key=lambda b: b.threat_level)[:-self.config['max_birds']]
            for bird in excess_birds:
                bird.active = False
        for bird in self.birds:
            bird.move(center_x, center_y)
        self.draw_radar()
        self.update()

    def emit_sound_wave(self):
        """Emit a sound wave from the drone."""
        self.sound_active = True
        self.parent.avoid_action.setText("Status: Ultrasonic wave emitted at 18kHz")
        self.sound_timer.start(5000)
        QTimer.singleShot(1000, lambda: setattr(self, 'sound_active', False))

    def draw_radar(self):
        """Draw enhanced and polished military-grade radar with sound wave."""
        self.ax.clear()
        self.ax.set_facecolor('#1a1a1a')
        self.ax.set_ylim(0, self.config['max_range'])
        self.ax.set_xticks(np.linspace(0, 2*np.pi, 12, endpoint=False))
        self.ax.set_xticklabels(['N', '', 'NE', '', 'E', '', 'SE', '', 'S', '', 'SW', ''])
        self.ax.tick_params(axis='x', colors='#888888', labelsize=10)

        # Radial grid with labeled ranges
        for r in np.arange(50, self.config['max_range'] + 1, 50):
            self.ax.plot([0, 2*np.pi], [r, r], color='#333333', lw=0.5, ls='-', alpha=0.5)
            self.ax.text(0, r, f'{r}m', color='#888888', ha='left', va='center', fontsize=8)

        # Radar pulse effect
        pulse_radius = (time.time() % 2) * self.config['max_range'] / 2
        for i in range(3):
            alpha = 0.3 - i * 0.1
            if alpha > 0:
                self.ax.plot([0, 2*np.pi], [pulse_radius * (i + 1) / 3, pulse_radius * (i + 1) / 3], color='#00cc00', lw=1, alpha=alpha)

        # Rotating scan line with trail
        scan_angle = (time.time() % 10) * 2 * np.pi / 10
        for i in range(3):
            alpha = 0.8 - i * 0.2
            if alpha > 0:
                self.ax.plot([scan_angle - i * 0.1, scan_angle - i * 0.1], [0, self.config['max_range']], color='#00cc00', lw=2, alpha=alpha)

        # Sound wave representation
        if self.sound_active:
            self.ax.plot([0, 2*np.pi], [self.sound_range, self.sound_range], color='#00ff00', lw=1.5, ls='--', alpha=0.6)

        # Drone marker
        self.ax.plot(0, 0, marker='^', color='#00cc00', markersize=12, markeredgecolor='#888888', markeredgewidth=1, label='Drone')

        # Bird and flock markers with glow effect
        center_x, center_y = self.config['max_range']/2, self.config['max_range']/2
        flocks = {}
        for bird in self.birds:
            if not bird.active:
                continue
            angle = math.atan2(bird.y - center_y, bird.x - center_x)
            distance = min(math.sqrt((bird.x - center_x)**2 + (bird.y - center_y)**2), self.config['max_range'])
            relative_speed = bird.get_relative_speed(center_x, center_y)
            if bird.is_flock_member and bird.flock_id:
                if bird.flock_id not in flocks:
                    flocks[bird.flock_id] = {'x': bird.x, 'y': bird.y, 'count': 1, 'threat': bird.threat_level}
                else:
                    flocks[bird.flock_id]['x'] = (flocks[bird.flock_id]['x'] * flocks[bird.flock_id]['count'] + bird.x) / (flocks[bird.flock_id]['count'] + 1)
                    flocks[bird.flock_id]['y'] = (flocks[bird.flock_id]['y'] * flocks[bird.flock_id]['count'] + bird.y) / (flocks[bird.flock_id]['count'] + 1)
                    flocks[bird.flock_id]['count'] += 1
                    flocks[bird.flock_id]['threat'] = max(flocks[bird.flock_id]['threat'], bird.threat_level)
            else:
                self.ax.scatter(angle, distance, s=120 * bird.threat_level, c=f'#{int(100 + 155 * bird.threat_level):02x}cc00', alpha=0.9, edgecolor='#888888', linewidth=0.5)
                direction_deg = math.degrees(angle) % 360
                annotation = f"Dir: {direction_deg:.0f}°\nDist: {distance:.1f}m\nSpd: {relative_speed:.1f}m/s"
                self.ax.annotate(annotation, (angle, distance), xytext=(10, 10), textcoords='offset points',
                               bbox=dict(boxstyle="round,pad=0.5", fc="#ffff00", alpha=0.7),
                               fontsize=8, color='black')

        # Draw flocks
        for flock_id, flock in flocks.items():
            angle = math.atan2(flock['y'] - center_y, flock['x'] - center_x)
            distance = min(math.sqrt((flock['x'] - center_x)**2 + (flock['y'] - center_y)**2), self.config['max_range'])
            relative_speed = np.mean([b.get_relative_speed(center_x, center_y) for b in self.birds if b.flock_id == flock_id and b.active])
            self.ax.scatter(angle, distance, s=180 * flock['threat'], c=f'#{int(100 + 155 * flock["threat"]):02x}cc00', alpha=0.9, marker='s', edgecolor='#888888', linewidth=0.5, label=f'Flock {flock_id} ({flock["count"]})')
            direction_deg = math.degrees(angle) % 360
            annotation = f"Flock {flock_id} ({flock['count']} birds)\nDir: {direction_deg:.0f}°\nDist: {distance:.1f}m\nSpd: {relative_speed:.1f}m/s"
            self.ax.annotate(annotation, (angle, distance), xytext=(15, 15), textcoords='offset points',
                           bbox=dict(boxstyle="round,pad=0.5", fc="#ffff00", alpha=0.7),
                           fontsize=8, color='black')

        # Range scale legend
        self.ax.text(2.2 * np.pi / 2, self.config['max_range'] / 2, 'Range (m)\n0\n150\n300', color='#888888', ha='center', va='center', fontsize=8, rotation=90)

        self.ax.legend(loc='upper right', frameon=False, fontsize=8, labelcolor='#888888')
        self.draw()

class DroneControlPanel(QWidget):
    """Main drone control panel with sleek black tactical UI."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tactical Drone Control System")
        self.setStyleSheet("""
            QWidget {
                background-color: #0f0f0f;
                color: #b0b0b0;
                font-family: 'Arial', sans-serif;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 2px solid #333333;
                border-radius: 6px;
                background: #0f0f0f;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.8);
            }
            QTabBar::tab {
                background: #1a1a1a;
                padding: 10px 20px;
                border: 1px solid #333333;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                color: #888888;
            }
            QTabBar::tab:selected {
                background: #0f0f0f;
                color: #b0b0b0;
                border-bottom: 2px solid #555555;
            }
            QPushButton {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                color: #b0b0b0;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QProgressBar {
                border: 1px solid #333333;
                border-radius: 4px;
                text-align: center;
                height: 20px;
                background: #1a1a1a;
            }
            QProgressBar::chunk {
                background-color: #555555;
                border-radius: 2px;
            }
            QTextEdit {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 4px;
                color: #b0b0b0;
            }
            QLabel {
                padding: 4px;
            }
            QCheckBox {
                color: #b0b0b0;
                padding: 4px;
            }
            QStatusBar {
                background-color: #0f0f0f;
                color: #888888;
                border-top: 1px solid #333333;
            }
        """)
        self.setMinimumSize(1200, 900)

        # Tactical Header with Gradient
        header = QWidget()
        header_layout = QHBoxLayout()
        gradient = QLinearGradient(0, 0, 0, 30)
        gradient.setColorAt(0, QColor(15, 15, 15))
        gradient.setColorAt(1, QColor(5, 5, 5))
        header.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f0f0f, stop:1 #050505); padding: 8px; border-bottom: 2px solid #333333;")
        header_layout.addWidget(QLabel("TACTICAL DRONE OPS"))
        header_layout.addStretch()
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Battery: 75%"))
        status_layout.addWidget(QLabel("Signal: Strong"))
        status_layout.addWidget(QLabel("Time: 11:31 PM IST"))
        header_layout.addLayout(status_layout)
        header.setLayout(header_layout)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.createVitalsTab(), "Mission Vitals")
        self.tabs.addTab(self.createBirdDeterrentTab(), "Threat Management")

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("System Operational - Mission Time: 00:00:00")

        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self.tabs)
        layout.addWidget(self.status_bar)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

    def createVitalsTab(self):
        """Create the Vitals tab with dynamic updates."""
        tab = QWidget()
        grid = QGridLayout()
        grid.setSpacing(15)

        self.distance_progress = QProgressBar()
        self.distance_progress.setMaximum(10000)
        self.distance_progress.setValue(3400)
        self.distance_progress.setFormat("Distance: %p m")
        grid.addWidget(QLabel("Distance:"), 0, 0)
        grid.addWidget(self.distance_progress, 0, 1)

        self.battery = QProgressBar()
        self.battery.setMaximum(100)
        self.battery.setValue(75)
        self.battery.setFormat("Battery: %p%")
        grid.addWidget(QLabel("Battery:"), 1, 0)
        grid.addWidget(self.battery, 1, 1)

        self.radar_input = QTextEdit("No threats detected")
        grid.addWidget(QLabel("Threat Log:"), 2, 0, 1, 2)
        grid.addWidget(self.radar_input, 3, 0, 1, 2)

        self.payload = QLabel("Payload: 2.3kg")
        grid.addWidget(QLabel("Payload:"), 4, 0)
        grid.addWidget(self.payload, 4, 1)

        self.vitals_timer = QTimer(self)
        self.vitals_timer.timeout.connect(self.updateVitals)
        self.vitals_timer.start(1000)

        tab.setLayout(grid)
        return tab

    def createBirdDeterrentTab(self):
        """Create the Threat Management tab with radar and controls."""
        tab = QWidget()
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 3)  # Left half (radar) gets more stretch
        grid.setColumnStretch(6, 1)  # Right panel gets less stretch

        self.radar_display = RadarWidget(parent=self)
        grid.addWidget(self.radar_display, 0, 0, 12, 6)  # Full left half, 12 rows, 6 columns

        # Enhanced Right Panel
        grid.addWidget(QLabel("Status Dashboard:"), 0, 6, 1, 2)
        self.bird_info = QLabel("Threats: 0")
        grid.addWidget(QLabel("Threats:"), 1, 6)
        grid.addWidget(self.bird_info, 1, 7)

        self.avoid_action = QLabel("Status: Idle")
        grid.addWidget(QLabel("Deterrent:"), 2, 6)
        grid.addWidget(self.avoid_action, 2, 7)

        self.altitude = QLabel("Alt: 120m")
        grid.addWidget(QLabel("Altitude:"), 3, 6)
        grid.addWidget(self.altitude, 3, 7)

        self.wind_speed = QLabel("Wind: 5m/s")
        grid.addWidget(QLabel("Wind:"), 4, 6)
        grid.addWidget(self.wind_speed, 4, 7)

        self.temperature = QLabel("Temp: 22°C")
        grid.addWidget(QLabel("Temp:"), 5, 6)
        grid.addWidget(self.temperature, 5, 7)

        self.threat_summary = QLabel("Threat: Low")
        grid.addWidget(QLabel("Assessment:"), 6, 6)
        grid.addWidget(self.threat_summary, 6, 7)

        self.alert_log = QTextEdit("No alerts")
        grid.addWidget(QLabel("Alerts:"), 7, 6, 1, 2)
        grid.addWidget(self.alert_log, 8, 6, 3, 2)  # Increased height for alerts

        sensitivity_check = QCheckBox("High Sensitivity")
        sensitivity_check.stateChanged.connect(self.toggle_sensitivity)
        grid.addWidget(sensitivity_check, 11, 6, 1, 2)

        stop_button = QPushButton("HALT")
        stop_button.clicked.connect(self.stop_simulation)
        grid.addWidget(stop_button, 12, 6, 1, 1)

        manual_button = QPushButton("MANUAL")
        manual_button.clicked.connect(self.manual_control)
        grid.addWidget(manual_button, 12, 7, 1, 1)

        self.update_bird_info_timer = QTimer()
        self.update_bird_info_timer.timeout.connect(self.updateBirdInfo)
        self.update_bird_info_timer.start(1000)

        self.env_timer = QTimer()
        self.env_timer.timeout.connect(self.updateEnvironment)
        self.env_timer.start(2000)

        tab.setLayout(grid)
        return tab

    def updateVitals(self):
        """Update vitals display."""
        self.battery.setValue(max(0, self.battery.value() - 1))
        self.distance_progress.setValue(min(10000, self.distance_progress.value() + 50))
        current_time = time.time()
        mission_time = time.strftime("%H:%M:%S", time.gmtime(current_time - self.start_time if hasattr(self, 'start_time') else current_time))
        self.status_bar.showMessage(f"System Operational - Mission Time: {mission_time}")

    def updateBirdInfo(self):
        """Update threat count and radar input with detailed bird/flock data."""
        count = len([b for b in self.radar_display.birds if b.active])
        self.bird_info.setText(f"Threats: {count}")
        center_x, center_y = self.radar_display.config['max_range']/2, self.radar_display.config['max_range']/2
        bird_data = []
        flocks = {}
        for bird in self.radar_display.birds:
            if not bird.active:
                continue
            angle = math.atan2(bird.y - center_y, bird.x - center_x)
            distance = min(math.sqrt((bird.x - center_x)**2 + (bird.y - center_y)**2), self.radar_display.config['max_range'])
            relative_speed = bird.get_relative_speed(center_x, center_y)
            if bird.is_flock_member and bird.flock_id:
                if bird.flock_id not in flocks:
                    flocks[bird.flock_id] = {'count': 1, 'threat': bird.threat_level, 'x': bird.x, 'y': bird.y}
                else:
                    flocks[bird.flock_id]['count'] += 1
                    flocks[bird.flock_id]['threat'] = max(flocks[bird.flock_id]['threat'], bird.threat_level)
                    flocks[bird.flock_id]['x'] = (flocks[bird.flock_id]['x'] * (flocks[bird.flock_id]['count'] - 1) + bird.x) / flocks[bird.flock_id]['count']
                    flocks[bird.flock_id]['y'] = (flocks[bird.flock_id]['y'] * (flocks[bird.flock_id]['count'] - 1) + bird.y) / flocks[bird.flock_id]['count']
            else:
                direction_deg = math.degrees(angle) % 360
                bird_data.append(f"Threat at ({bird.x:.1f}, {bird.y:.1f}): Dir: {direction_deg:.0f}°, Dist: {distance:.1f}m, Speed: {relative_speed:.1f}m/s, Threat: {bird.threat_level:.1f}")

        for flock_id, flock in flocks.items():
            angle = math.atan2(flock['y'] - center_y, flock['x'] - center_x)
            distance = min(math.sqrt((flock['x'] - center_x)**2 + (flock['y'] - center_y)**2), self.radar_display.config['max_range'])
            relative_speed = np.mean([b.get_relative_speed(center_x, center_y) for b in self.radar_display.birds if b.flock_id == flock_id and b.active])
            direction_deg = math.degrees(angle) % 360
            bird_data.append(f"Flock {flock_id} ({flock['count']} birds): Dir: {direction_deg:.0f}°, Dist: {distance:.1f}m, Speed: {relative_speed:.1f}m/s, Threat: {flock['threat']:.1f}")

        self.radar_input.setText("\n".join(bird_data) if bird_data else "No threats detected")
        threat_level = max([b.threat_level for b in self.radar_display.birds if b.active] + [0])
        self.threat_summary.setText(f"Threat: {'High' if threat_level > 0.7 else 'Medium' if threat_level > 0.4 else 'Low'}")

    def updateEnvironment(self):
        """Update environmental data."""
        self.altitude.setText(f"Alt: {random.randint(100, 150)}m")
        self.wind_speed.setText(f"Wind: {random.uniform(0, 10):.1f}m/s")
        self.temperature.setText(f"Temp: {random.uniform(15, 30):.1f}°C")
        if random.random() < 0.1:
            self.alert_log.append(f"Alert: Threat detected at {time.strftime('%H:%M:%S')}")

    def toggle_sensitivity(self, state):
        """Toggle radar sensitivity."""
        self.radar_display.config['max_birds'] = 6 if state else 4
        self.status_bar.showMessage(f"Sensitivity: {'High' if state else 'Normal'} - Mission Time: {self.status_bar.currentMessage().split(' - ')[1]}")

    def stop_simulation(self):
        """Pause the simulation."""
        self.radar_display.timer.stop()
        self.radar_display.spawn_timer.stop()
        self.radar_display.sound_timer.stop()
        self.avoid_action.setText("Status: Halted")
        self.status_bar.showMessage("System Halted - Mission Time: 00:00:00")

    def manual_control(self):
        """Placeholder for manual control."""
        self.avoid_action.setText("Status: Manual")
        self.status_bar.showMessage("Manual Active - Mission Time: 00:00:00")

    def showEvent(self, event):
        """Initialize start time when window is shown."""
        super().showEvent(event)
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    panel = DroneControlPanel()
    panel.show()
    sys.exit(app.exec())
