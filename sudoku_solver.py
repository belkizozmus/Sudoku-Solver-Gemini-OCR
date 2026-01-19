import sys
import os
import json
import cv2
import numpy as np
import PIL.Image
import copy
import google.generativeai as genai
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QTableWidget
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt

API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.file_path = None
        self.processed_img_path = "processed_temp.png"
        self.grid = [[0]*9 for _ in range(9)]
        self.solutions = [] 

    def init_ui(self):
        self.setWindowTitle("Sudoku Solver")
        self.setGeometry(100, 100, 1000, 600)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)
        top_layout = QHBoxLayout()
        self.image_label = QLabel("Please Enter a Picture")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 3px dashed black; background-color: #f0f0f0;")
        self.image_label.setMinimumSize(500, 500)
        self.image_label.setMaximumSize(600, 600)
        self.table_widget = QTableWidget(9, 9)
        self.table_widget.setStyleSheet(
        "QTableWidget { gridline-color: black; }"
        )

        self.table_widget.horizontalHeader().setVisible(False)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.setFont(QFont("Arial", 14, QFont.Bold))
        top_layout.addWidget(self.image_label)
        top_layout.addWidget(self.table_widget)
        self.status_label = QLabel("Sudoku Solver")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.status_label.setStyleSheet("color: darkblue ; margin: 10x;")
        buttons_layout = QHBoxLayout()
        self.btn_load = QPushButton("upload your picture")
        self.btn_reset = QPushButton("reset")
        self.btn_solve1 = QPushButton("solve 1")
        self.btn_solve2 = QPushButton("solve 2")
        self.btn_solve3 = QPushButton("solve 3")
        btn_style = "padding: 8px; font-weight: bold; background-color: darkblue; color: white;"
        for btn in [self.btn_load, self.btn_reset, self.btn_solve1, self.btn_solve2, self.btn_solve3]:
            btn.setStyleSheet(btn_style)
        buttons_layout.addWidget(self.btn_load)

        buttons_layout.addWidget(self.btn_reset)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_solve1)
        buttons_layout.addWidget(self.btn_solve2)
        buttons_layout.addWidget(self.btn_solve3)

        self.main_layout.addLayout(top_layout)
        self.main_layout.addWidget(self.status_label)
        self.main_layout.addLayout(buttons_layout)
        self.btn_load.clicked.connect(self.picture_selection)
        self.btn_reset.clicked.connect(self.reset)
        self.btn_solve1.clicked.connect(lambda: self.display_solution(0))
        self.btn_solve2.clicked.connect(lambda: self.display_solution(1))
        self.btn_solve3.clicked.connect(lambda: self.display_solution(2))

    def picture_selection(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "picture selecting")
        if file_name:
            self.file_path = file_name
            pixmap = QPixmap(file_name)
            w, h = self.image_label.width(), self.image_label.height()
            self.image_label.setPixmap(pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            self.solutions = []
            self.grid = [[0]*9 for _ in range(9)]

    def display_grid(self, grid_data):
        self.table_widget.blockSignals(True)
        for i in range(9):
            for j in range(9):
                value = grid_data[i][j]
                item = QTableWidgetItem(str(value)) if value != 0 else QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignCenter)
                self.table_widget.setItem(i, j, item)
        self.table_widget.blockSignals(False)
        QApplication.processEvents()

    def reset(self):
        self.grid = [[0]*9 for _ in range(9)]
        self.solutions = []
        self.display_grid(self.grid)
        self.status_label.setText("Table was reset")
        self.status_label.setStyleSheet("color: red; font-size: 14px;")
        self.file_path = None
        self.image_label.clear()
        self.image_label.setText("Please Enter a Picture")

    def cv2_imread_utf8(self, path):
        try:
            with open(path, "rb") as f:
                return cv2.imdecode(np.asarray(bytearray(f.read()), dtype=np.uint8), cv2.IMREAD_COLOR)
        except:
            return None

    def order_points(self, pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
        return rect

    def four_point_transform(self, image, pts):
        rect = self.order_points(pts)
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    def preprocess_image(self, input_path, output_path):
        if not os.path.exists(input_path): return None
        img = self.cv2_imread_utf8(input_path)
        if img is None: return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blur, 255, 1, 1, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        puzzle_contour = None
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                puzzle_contour = approx
                break
        final_img = gray
        if puzzle_contour is not None:
            final_img = self.four_point_transform(gray, puzzle_contour.reshape(4, 2))
        final_img = cv2.resize(final_img, (800, 800), interpolation=cv2.INTER_CUBIC)
        denoised = cv2.fastNlMeansDenoising(final_img, None, 10, 7, 21)
        sharpened = cv2.filter2D(denoised, -1, np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]))
        binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        processed = cv2.erode(binary, np.ones((2, 2), np.uint8), iterations=1)
        is_success, im_buf_arr = cv2.imencode(".png", processed)
        if is_success: im_buf_arr.tofile(output_path)
        return output_path

    def gemini_ocr(self):
        self.status_label.setText("API reading")
        self.status_label.setStyleSheet("color: red; font-size: 14px;")
        QApplication.processEvents()
        processed_file = self.preprocess_image(self.file_path, self.processed_img_path)
        if not processed_file:
            self.status_label.setText("Picture could not be read")
            return None
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
            system_instruction=
        "You are a highly accurate OCR engine specifically for Sudoku puzzles.\n"
        "Analyze the input image which contains a 9x9 Sudoku grid.\n"
        "Output ONLY a valid JSON object.\n"
        "Rules:\n"
        "1. The JSON must have a key 'sudoku' containing a 9x9 list of lists.\n"
        "2. Represent empty cells as 0.\n"
        "3. Represent filled cells with their integer value (1-9).\n"
        "4. Be extremely careful with digits that look like noise. If a cell is empty, it is 0.\n"
        "5. Do not include markdown formatting like ```json ... ``` in the response.\n"
        )
        try:
            img = PIL.Image.open(processed_file)
            response = model.generate_content(["Extract Sudoku grid", img])
            grid_json = json.loads(response.text).get("sudoku")
            if grid_json and len(grid_json) == 9: return grid_json
            else:
                self.status_label.setText("Error : table cannot be read")
                return None
        except Exception as e:
            print(e)
            self.status_label.setText("Error API")
            return None

    def is_valid(self, grid, row, column, k):
        not_in_row = k not in grid[row]
        not_in_column = k not in [grid[i][column] for i in range(9)]
        box_r, box_c = (row // 3) * 3, (column // 3) * 3
        not_in_box = k not in [grid[i][j] 
                               for i in range(box_r, box_r + 3) 
                               for j in range(box_c, box_c + 3)]
        return not_in_row and not_in_column and not_in_box

    def solve_all(self, grid, row=0, column=0):
        if len(self.solutions) >= 3:
            return
        if row == 9:
            self.solutions.append(copy.deepcopy(grid))
            return
        next_row, next_column = (row, column + 1) if column < 8 else (row + 1, 0)
        if grid[row][column] != 0:
            self.solve_all(grid, next_row, next_column)
        else:
            for k in range(1, 10):
                if self.is_valid(grid, row, column, k):
                    grid[row][column] = k
                    self.solve_all(grid, next_row, next_column)
                    grid[row][column] = 0

    def calculate_solutions(self):
        self.solutions = []
        self.status_label.setText("solving")
        self.status_label.setStyleSheet("color: red; font-size: 14px;")
        QApplication.processEvents()
        temp_grid = [row[:] for row in self.grid]
        self.solve_all(temp_grid)
        number = len(self.solutions)
        if number > 0:
            self.status_label.setText(f"{number} solutions found")
            self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
        else:
            self.status_label.setText("Solution is not found")
            self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")

    def display_solution(self, order_of_solution):
        is_empty_grid = all(cell == 0 for row in self.grid for cell in row)
        if is_empty_grid and self.file_path:
            ocr_grid = self.gemini_ocr()
            if ocr_grid:
                self.grid = ocr_grid
                self.display_grid(self.grid)
                self.calculate_solutions()
            else:
                return
        if not self.solutions and not is_empty_grid:
             self.calculate_solutions()
        if order_of_solution < len(self.solutions):
            target_grid = self.solutions[order_of_solution]
            self.status_label.setText(f"Displaying Solution {order_of_solution + 1}")
        else:
            target_grid = [[0]*9 for _ in range(9)]
            self.status_label.setText(f"Solution {order_of_solution + 1} not available")
        self.display_grid(target_grid)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())

