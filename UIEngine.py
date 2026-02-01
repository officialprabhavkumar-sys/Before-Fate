import queue
from PySide6.QtWidgets import QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QStackedWidget, QSizePolicy
from PySide6.QtCore import QTimer, QObject, Signal, Qt
import sys

from GeneralVerifier import verifier

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Before Fate")
        
class UIEngine(QObject):
    quit_requested = Signal()
    switch_page = Signal(str)
    update_box_signal = Signal(str, str)


    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.window = MainWindow()
        self.stack = QStackedWidget()
        self.window.setCentralWidget(self.stack)
        self.state = "mainmenu"
        self.window.setMinimumSize(1600, 900)
        self.quit_requested.connect(self.app.quit)
        self.switch_page.connect(self.set_page)
        self.switch_page.connect(self.set_page)
        self.update_box_signal.connect(self._update_box)
        self.app.setStyleSheet("""
                            QMainWindow {
                                background-color: #0f1117;
                                    }

                            QTextEdit {
                                background-color: #151821;
                                color: #e6e6eb;
                                border: 1px solid #2a2f45;
                                border-radius: 6px;
                                padding: 10px;
                                font-family: Hack;
                                font-size: 16px;
                                    }

                            QLineEdit {
                                background-color: #0f1320;
                                color: #ffffff;
                                border: 1px solid #3a3f5a;
                                border-radius: 6px;
                                padding: 8px;
                                font-family: Hack;
                                font-size: 16px;
                                    }

                            QLineEdit:focus {
                                border: 1px solid #6c7cff;
                                    }
                                """)
        
    def build_mainmenu_page(self) -> QWidget:
        mainmenu_widget = QWidget()
        mainmenu_layout = QVBoxLayout(mainmenu_widget)
        mainmenu_layout.setContentsMargins(0, 0, 0, 0)
        mainmenu_layout.setSpacing(8)
        mainmenu_layout.addWidget(self.mainmenu_output, stretch = 1)
        mainmenu_layout.addWidget(self.mainmenu_input)
        return mainmenu_widget
    
    def make_sidebar_box(self) -> QTextEdit:
        box = QTextEdit()
        box.setReadOnly(True)

        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    
        box.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        box.setStyleSheet("""
            QTextEdit {
                background-color: #151821;
                border: 2px solid #000;
                padding: 6px;
                font-family: Hack;
                font-size: 14px;
            }
        """)
        box.setCursorWidth(0)
        box.setFocusPolicy(Qt.NoFocus)
        return box
    
    def build_game_page(self) -> QWidget:
        game_widget = QWidget()
        game_layout = QVBoxLayout(game_widget)
        game_layout.setContentsMargins(0, 0, 0, 0)
        game_layout.setSpacing(8)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        sidebar_layout.setSpacing(6)
        
        self.time_box = self.make_sidebar_box()
        self.location_box = self.make_sidebar_box()
        self.player_box = self.make_sidebar_box()
        self.loadout_box = self.make_sidebar_box()
        self.effects_box = self.make_sidebar_box()
        
        sidebar_layout.addWidget(self.time_box, 1)
        sidebar_layout.addWidget(self.location_box, 1)
        sidebar_layout.addWidget(self.player_box, 3)
        sidebar_layout.addWidget(self.loadout_box, 3)
        sidebar_layout.addWidget(self.effects_box, 1)
        
        sidebar_layout.addStretch()
        
        top_layout.addWidget(self.game_output, stretch = 4)
        top_layout.addWidget(sidebar, stretch=1)

        game_layout.addLayout(top_layout, stretch = 1)
        game_layout.addWidget(self.game_input)

        return game_widget

    def set_page(self, page : str) -> None:
        
        if page == "game":
            self.state = "game"
            self.stack.setCurrentWidget(self.game_page)
        elif page == "mainmenu":
            self.state = "mainmenu"
            self.stack.setCurrentWidget(self.mainmenu_page)
        self.window.show()
        
    def process_output_queue(self) -> None:
        while not self.output_queue.empty():
            output = self.output_queue.get()
            verifier.verify_type(output, str, "output")
            MAPPING = {"mainmenu" : self.mainmenu_output, "game" : self.game_output}
            MAPPING[self.state].append(output)
            MAPPING[self.state].verticalScrollBar().setValue(MAPPING[self.state].verticalScrollBar().maximum())

    def initialize(self) -> None:

        self.mainmenu_output = QTextEdit()
        self.mainmenu_output.setReadOnly(True)
        self.game_output = QTextEdit()
        self.game_output.setReadOnly(True)

        self.mainmenu_input = QLineEdit()
        self.mainmenu_input.returnPressed.connect(self.add_input_to_queue)
        self.game_input = QLineEdit()
        self.game_input.returnPressed.connect(self.add_input_to_queue)

        self.mainmenu_page = self.build_mainmenu_page()
        self.game_page = self.build_game_page()

        self.stack.addWidget(self.mainmenu_page)
        self.stack.addWidget(self.game_page)

        self.set_page("mainmenu")
        
        self.output_timer = QTimer()
        self.output_timer.timeout.connect(self.process_output_queue)
        self.output_timer.start(50)
    
    def _update_box(self, box_name: str, text: str) -> None:
        MAPPING = {
            "time": self.time_box,
            "location": self.location_box,
            "player": self.player_box,
            "loadout": self.loadout_box,
            "effects": self.effects_box,
        }

        box = MAPPING[box_name]
        box.clear()
        for line in text.split("\n"):
            box.append(line)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def run(self):
    
        self.app.exec()
    
    def add_input_to_queue(self) -> None:
        
        MAPPING = {"mainmenu" : self.mainmenu_input, "game" : self.game_input}
        
        user_input = MAPPING[self.state].text()
        MAPPING[self.state].clear()
        
        if len(user_input) > 0:
            self.input_queue.put(user_input.strip())
    
    def stop(self) -> None:
        self.quit_requested.emit()