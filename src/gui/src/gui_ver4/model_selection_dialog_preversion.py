"""
모델 선택 다이얼로그
- Random Forest / ST-GCN 선택 UI
- 기존 input_selection_dialog 이후에 표시
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QRadioButton, QButtonGroup, QPushButton, QGroupBox,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class ModelSelectionDialog(QDialog):
    """낙상 감지 모델 선택 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("낙상 감지 모델 선택")
        self.setFixedSize(450, 350)
        self.setModal(True)
        
        # 기본 선택값
        self.selected_model = 'random_forest'
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # ===== 제목 =====
        title = QLabel("🤖 낙상 감지 모델 선택")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # ===== 모델 선택 그룹 =====
        group = QGroupBox("사용 가능한 모델")
        group.setFont(QFont("", 10, QFont.Weight.Bold))
        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        
        # Radio Button 그룹
        self.btn_group = QButtonGroup(self)
        
        # ----- Random Forest -----
        rf_container = QVBoxLayout()
        
        self.rf_radio = QRadioButton("Random Forest (권장)")
        self.rf_radio.setFont(QFont("", 11))
        self.rf_radio.setChecked(True)
        self.rf_radio.toggled.connect(self.on_model_changed)
        rf_container.addWidget(self.rf_radio)
        
        rf_desc = QLabel(
            "  • 정확도: <b>93.19%</b><br>"
            "  • 프레임 단위 즉시 추론<br>"
            "  • 낮은 지연시간, 안정적 성능"
        )
        rf_desc.setStyleSheet("color: #666; margin-left: 25px;")
        rf_desc.setTextFormat(Qt.TextFormat.RichText)
        rf_container.addWidget(rf_desc)
        
        group_layout.addLayout(rf_container)
        
        # 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #ddd;")
        separator.setFixedHeight(1)
        group_layout.addWidget(separator)
        
        # ----- ST-GCN -----
        stgcn_container = QVBoxLayout()
        
        self.stgcn_radio = QRadioButton("ST-GCN (시계열 분석)")
        self.stgcn_radio.setFont(QFont("", 11))
        self.stgcn_radio.toggled.connect(self.on_model_changed)
        stgcn_container.addWidget(self.stgcn_radio)
        
        stgcn_desc = QLabel(
            "  • 정확도: <b>84.21%</b><br>"
            "  • 60프레임(~2초) 시퀀스 분석<br>"
            "  • 동작 패턴 기반 감지"
        )
        stgcn_desc.setStyleSheet("color: #666; margin-left: 25px;")
        stgcn_desc.setTextFormat(Qt.TextFormat.RichText)
        stgcn_container.addWidget(stgcn_desc)
        
        group_layout.addLayout(stgcn_container)
        
        # 버튼 그룹에 추가
        self.btn_group.addButton(self.rf_radio, 0)
        self.btn_group.addButton(self.stgcn_radio, 1)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        # ===== 상태 표시 라벨 =====
        self.status_label = QLabel("✅ Random Forest 모델이 선택되었습니다.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "background-color: #e8f5e9; "
            "padding: 8px; "
            "border-radius: 4px; "
            "color: #2e7d32;"
        )
        layout.addWidget(self.status_label)
        
        # ===== 버튼 =====
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        # 확인 버튼
        self.ok_btn = QPushButton("확인")
        self.ok_btn.setFixedSize(100, 35)
        self.ok_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #1976d2;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 4px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "  background-color: #1565c0;"
            "}"
        )
        self.ok_btn.clicked.connect(self.accept)
        
        # 취소 버튼
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setFixedSize(100, 35)
        self.cancel_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #757575;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 4px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #616161;"
            "}"
        )
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def on_model_changed(self):
        """모델 선택 변경 시 상태 업데이트"""
        if self.rf_radio.isChecked():
            self.selected_model = 'random_forest'
            self.status_label.setText("✅ Random Forest 모델이 선택되었습니다.")
            self.status_label.setStyleSheet(
                "background-color: #e8f5e9; "
                "padding: 8px; "
                "border-radius: 4px; "
                "color: #2e7d32;"
            )
        else:
            self.selected_model = 'stgcn'
            self.status_label.setText("✅ ST-GCN 모델이 선택되었습니다. (버퍼링 필요)")
            self.status_label.setStyleSheet(
                "background-color: #e3f2fd; "
                "padding: 8px; "
                "border-radius: 4px; "
                "color: #1565c0;"
            )
    
    def get_selected_model(self) -> dict:
        """선택된 모델 정보 반환"""
        if self.rf_radio.isChecked():
            return {
                'type': 'random_forest',
                'name': 'Random Forest',
                'accuracy': 93.19,
                'description': '프레임 단위 즉시 추론'
            }
        else:
            return {
                'type': 'stgcn',
                'name': 'ST-GCN',
                'accuracy': 84.21,
                'description': '60프레임 시퀀스 분석',
                'buffer_size': 60
            }


def show_model_selection_dialog(parent=None) -> dict:
    """
    모델 선택 다이얼로그 표시
    
    Args:
        parent: 부모 위젯
        
    Returns:
        dict: {
            'type': 'random_forest' | 'stgcn',
            'name': str,
            'accuracy': float,
            'description': str,
            'buffer_size': int (ST-GCN only)
        }
    """
    dialog = ModelSelectionDialog(parent)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_selected_model()
    else:
        # 취소 시 기본값 (Random Forest)
        return {
            'type': 'random_forest',
            'name': 'Random Forest',
            'accuracy': 93.19,
            'description': '프레임 단위 즉시 추론'
        }


# ========== 테스트 ==========
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 다이얼로그 테스트
    result = show_model_selection_dialog()
    print("Selected model:", result)
    
    sys.exit(0)
