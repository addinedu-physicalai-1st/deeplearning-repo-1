"""
통합 낙상 감지 러너 - 사용자 탭/관리자 탭 공용.
한 프레임 입력 -> (스켈레톤+상태 오버레이된 프레임, 상태문자열, 낙상여부) 반환.
.env USE_MODEL (RandomForest | ST-GCN-Original | ST-GCN-Fine-tuned) 기반.
"""

import os
import time
import numpy as np
import cv2
from collections import deque

_GUI_DIR = os.path.dirname(os.path.abspath(__file__))

# YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# ST-GCN
try:
    from .stgcn_inference_finetuned import STGCNInference
    STGCN_AVAILABLE = True
except ImportError:
    STGCN_AVAILABLE = False

from .one_euro_filter import KeypointFilter
from .model_selection_dialog import get_model_config_from_env
from .shared_fall_logic import (
    extract_features_v3b,
    predict_fall_rf,
    load_rf_model_if_available,
    select_target_person_from_results,
)


def _draw_skeleton(frame, keypoints):
    """스켈레톤 그리기 (COCO 17)."""
    connections = [
        (0, 1), (0, 2), (1, 3), (2, 4), (5, 6),
        (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16),
    ]
    for person_kps in keypoints:
        for kp in person_kps:
            x, y, conf = int(kp[0]), int(kp[1]), kp[2]
            if conf > 0.5:
                cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)
        for i, j in connections:
            if i < len(person_kps) and j < len(person_kps) and person_kps[i][2] > 0.5 and person_kps[j][2] > 0.5:
                x1, y1 = int(person_kps[i][0]), int(person_kps[i][1])
                x2, y2 = int(person_kps[j][0]), int(person_kps[j][1])
                cv2.line(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
    return frame


class UnifiedFallRunner:
    """
    통합 낙상 감지: YOLO Pose + USE_MODEL(RandomForest / ST-GCN).
    process(frame) -> (annotated_frame, state_str, is_fallen).
    """

    def __init__(self, env_dir: str):
        """
        env_dir: .env가 있는 디렉터리 (예: client 디렉터리). 이 경로를 ADMIN_UI_ENV_DIR로 설정해 get_model_config_from_env 사용.
        """
        self._env_dir = os.path.abspath(env_dir)
        prev = os.environ.get("ADMIN_UI_ENV_DIR")
        os.environ["ADMIN_UI_ENV_DIR"] = self._env_dir
        try:
            model_config = get_model_config_from_env()
        finally:
            if prev is not None:
                os.environ["ADMIN_UI_ENV_DIR"] = prev
            elif "ADMIN_UI_ENV_DIR" in os.environ and os.environ["ADMIN_UI_ENV_DIR"] == self._env_dir:
                os.environ["ADMIN_UI_ENV_DIR"] = self._env_dir  # 유지

        self.model_type = model_config["type"]
        self.model_name = model_config.get("name", "Unknown")
        self.stgcn_model_path = model_config.get("model_path")
        self.yolo_model = None
        self.stgcn_model = None
        self.keypoints_buffer = []
        self.stgcn_buffer_size = 60
        self.keypoint_filter = KeypointFilter(filter_strength="medium")
        self.class_names = {0: "Normal", 1: "Falling", 2: "Fallen"}
        self.class_colors = {0: (0, 255, 0), 1: (0, 165, 255), 2: (0, 0, 255)}
        self._last_pred = (0, [1.0, 0.0, 0.0])  # prediction, proba
        self._frame_size_set = False
        self._history = []
        # RF용 181차원 피처 추출 상태 (관리자 탭과 동일)
        self._rf_feature_state = {'prev_keypoints': None, 'prev2_keypoints': None, 'feature_history': []}

        if YOLO_AVAILABLE:
            yolo_path = os.path.join(_GUI_DIR, "models", "yolo11s-pose.pt")
            if os.path.exists(yolo_path):
                self.yolo_model = YOLO(yolo_path)

        if self.model_type == "stgcn" and STGCN_AVAILABLE and self.stgcn_model_path and os.path.exists(self.stgcn_model_path):
            try:
                self.stgcn_model = STGCNInference(model_path=self.stgcn_model_path)
                self.keypoints_buffer = []
            except Exception as e:
                print(f"[UnifiedFallRunner] ST-GCN 로드 실패: {e}, RF 사용")
                self.model_type = "random_forest"
                self.stgcn_model = None

        # Random Forest: 관리자 모드와 동일한 rf_model/feature_columns 사용
        self.rf_model = None
        self.feature_columns = None
        if self.model_type == "random_forest":
            self.rf_model, self.feature_columns = load_rf_model_if_available()
            if self.rf_model:
                print(f"[UnifiedFallRunner] RF 모델 로드 ({len(self.feature_columns or [])} features)")

        # .env SHOWINFO, DEBUG_UI: 오버레이 표시 및 관리자 탭과 동일 UI 여부
        try:
            env_path = os.path.join(self._env_dir, ".env")
            if os.path.isfile(env_path):
                from dotenv import load_dotenv
                load_dotenv(env_path, override=False)
        except Exception:
            pass
        self._show_info = (os.environ.get("SHOWINFO", "true").strip().lower() == "true")
        self._debug_ui = (os.environ.get("DEBUG_UI", "false").strip().lower() == "true")
        self._frame_count = 0

    def process(self, frame: np.ndarray):
        """
        BGR 프레임 한 장 처리.
        Returns:
            (annotated_frame, state_str, is_fallen)
            - state_str: "Normal" | "Falling" | "Fallen"
            - is_fallen: True if state_str == "Fallen" (서버 알람용)
        """
        if frame is None or frame.size == 0:
            return frame, "Normal", False
        self._frame_count += 1
        frame = cv2.flip(frame, 1)
        state_str = "Normal"
        is_fallen = False
        h, w = frame.shape[:2]

        if self.yolo_model is None:
            if self._show_info:
                self._draw_status_overlay(frame, yolo_on=False)
            cv2.putText(frame, "YOLO not loaded", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            return frame, state_str, is_fallen

        try:
            results = self.yolo_model(frame, verbose=False)
            if not results or results[0].keypoints is None:
                if self._show_info:
                    self._draw_status_overlay(frame, yolo_on=True)
                self._draw_prediction_overlay(frame, self._last_pred[0], self._last_pred[1])
                return frame, self.class_names.get(self._last_pred[0], "Normal"), self._last_pred[0] == 2
            keypoints_all = results[0].keypoints.data.cpu().numpy()
            if len(keypoints_all) == 0:
                if self._show_info:
                    self._draw_status_overlay(frame, yolo_on=True)
                self._draw_prediction_overlay(frame, self._last_pred[0], self._last_pred[1])
                return frame, self.class_names.get(self._last_pred[0], "Normal"), self._last_pred[0] == 2
            target_idx = select_target_person_from_results(results, method='largest')
            kp = keypoints_all[target_idx] if target_idx is not None else keypoints_all[0]
            kp_filtered = self.keypoint_filter.apply(kp)
            frame = _draw_skeleton(frame, [kp_filtered])

            if self.model_type == "stgcn" and self.stgcn_model is not None:
                if not self._frame_size_set and hasattr(self.stgcn_model, "set_frame_size"):
                    self.stgcn_model.set_frame_size(w, h)
                    self._frame_size_set = True
                self.keypoints_buffer.append(np.asarray(kp_filtered, dtype=np.float32).copy())
                if len(self.keypoints_buffer) > self.stgcn_buffer_size:
                    self.keypoints_buffer.pop(0)
                if len(self.keypoints_buffer) >= self.stgcn_buffer_size:
                    try:
                        label, confidence, normal_prob, fall_prob = self.stgcn_model.predict(self.keypoints_buffer)
                        if label == "Fall":
                            state_str = "Fallen"
                            is_fallen = True
                            self._last_pred = (2, [0.0, 0.0, float(fall_prob)])
                        else:
                            state_str = "Normal"
                            self._last_pred = (0, [float(normal_prob), 0.0, float(fall_prob)])
                    except Exception as e:
                        if not hasattr(self, "_stgcn_err_count"):
                            self._stgcn_err_count = 0
                        self._stgcn_err_count += 1
                        if self._stgcn_err_count <= 3:
                            print(f"[UnifiedFallRunner] ST-GCN predict 오류: {e}")
            else:
                features = extract_features_v3b(kp_filtered, self._rf_feature_state)
                if features:
                    pred, proba = predict_fall_rf(
                        features,
                        rf_model=self.rf_model,
                        feature_columns=self.feature_columns,
                    )
                    self._last_pred = (pred, proba)
                    state_str = self.class_names[pred]
                    is_fallen = pred == 2
            # 최근 5분 평균 confidence 업데이트
            self._record_history(self._last_pred[0], self._last_pred[1])
            if self._show_info:
                self._draw_status_overlay(frame, yolo_on=True)
            self._draw_prediction_overlay(frame, self._last_pred[0], self._last_pred[1])
        except Exception as e:
            if not hasattr(self, "_log_count"):
                self._log_count = 0
            self._log_count += 1
            if self._log_count % 100 == 1:
                print(f"[UnifiedFallRunner] {e}")
        return frame, state_str, is_fallen

    def _record_history(self, prediction: int, proba):
        """최근 5분간 confidence 이력 저장 (정확도 대신 평균 confidence 사용)."""
        try:
            if proba is None or prediction is None:
                return
            if prediction < 0 or prediction >= len(proba):
                return
            conf = float(proba[prediction])
            now = time.time()
            self._history.append((now, conf))
            cutoff = now - 300.0  # 최근 5분
            # 오래된 항목 제거
            self._history = [(t, c) for (t, c) in self._history if t >= cutoff]
        except Exception:
            pass

    def _draw_status_overlay(self, frame, yolo_on: bool):
        """SHOWINFO=true 시: Frame, YOLO Pose ON/OFF. DEBUG_UI=true 시 관리자 탭과 동일한 FN Detection Acc 박스+진행바."""
        h, w = frame.shape[:2]
        cv2.putText(frame, f"Frame: {self._frame_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        yolo_text = "YOLO Pose ON" if yolo_on else "YOLO Pose OFF"
        cv2.putText(frame, yolo_text, (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        if self._debug_ui:
            self._draw_accuracy_overlay(frame)
        else:
            box_x = max(10, w - 260)
            cv2.rectangle(frame, (box_x, 10), (w - 10, 90), (80, 80, 80), -1)
            cv2.rectangle(frame, (box_x, 10), (w - 10, 90), (180, 180, 180), 2)
            cv2.putText(frame, "Recent 5 min", (box_x + 12, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2)
            avg_conf = sum(c for _, c in self._history) / len(self._history) if self._history else 0.0
            cv2.putText(frame, f"Detection Acc: {avg_conf*100:.1f}%", (box_x + 12, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    def _draw_accuracy_overlay(self, frame):
        """관리자 탭과 동일: Recent 5 min, FN Detection Acc, 진행바 (지표: 최근 5분 평균 신뢰도)."""
        try:
            h, w = frame.shape[:2]
            avg_conf = sum(c for _, c in self._history) / len(self._history) if self._history else 0.0
            accuracy = avg_conf * 100.0
            box_x = w - 250
            box_y = 10
            box_w = 240
            box_h = 100
            overlay = frame.copy()
            cv2.rectangle(overlay, (box_x, box_y), (box_x + box_w, box_y + box_h), (0, 0, 0), -1)
            blended = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            np.copyto(frame, blended)
            cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), (255, 255, 255), 2)
            cv2.putText(frame, "Recent 5 min", (box_x + 10, box_y + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.line(frame, (box_x + 10, box_y + 40), (box_x + box_w - 10, box_y + 40), (255, 255, 255), 1)
            cv2.putText(frame, f"FN Detection Acc: {accuracy:.1f}%", (box_x + 10, box_y + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)
            bar_x, bar_y = box_x + 10, box_y + 70
            bar_w, bar_h = box_w - 20, 15
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), -1)
            if accuracy >= 90:
                bar_color = (0, 255, 0)
            elif accuracy >= 70:
                bar_color = (0, 255, 255)
            else:
                bar_color = (0, 0, 255)
            filled_w = int(bar_w * (accuracy / 100.0))
            if filled_w > 0:
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled_w, bar_y + bar_h), bar_color, -1)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (255, 255, 255), 1)
        except Exception:
            pass

    def _draw_prediction_overlay(self, frame, prediction, proba):
        """상태 오버레이. DEBUG_UI=true 시 관리자 탭과 동일 스타일 (아이콘, 클래스별 확률바)."""
        if self._debug_ui:
            if (self.model_type == "stgcn" and self.stgcn_model is not None and
                len(getattr(self, "keypoints_buffer", [])) < getattr(self, "stgcn_buffer_size", 60)):
                self._draw_buffering_overlay(frame)
            else:
                self._draw_prediction_admin_style(frame, prediction, proba)
        else:
            h = frame.shape[0]
            name = self.class_names.get(prediction, "Unknown")
            color = self.class_colors.get(prediction, (255, 255, 255))
            conf = proba[prediction] * 100 if prediction < len(proba) else 0
            text = f"{name} {conf:.1f}%"
            box_top = h - 60
            cv2.rectangle(frame, (10, box_top), (320, h - 10), (0, 0, 0), -1)
            cv2.putText(frame, text, (20, box_top + 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    def _draw_buffering_overlay(self, frame):
        """ST-GCN 버퍼 채워지는 중 표시 (영상 왼쪽 맨 하단)"""
        try:
            h = frame.shape[0]
            box_top = h - 190
            buf_len = len(getattr(self, "keypoints_buffer", []))
            buf_size = getattr(self, "stgcn_buffer_size", 60)
            pct = int(100 * buf_len / buf_size)
            overlay = frame.copy()
            cv2.rectangle(overlay, (10, box_top), (280, h - 10), (0, 0, 0), -1)
            blended = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            np.copyto(frame, blended)
            cv2.putText(frame, "ST-GCN 버퍼링...", (20, box_top + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 200, 0), 2)
            cv2.putText(frame, f"{buf_len}/{buf_size} ({pct}%)", (20, box_top + 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        except Exception:
            pass

    def _draw_prediction_admin_style(self, frame, prediction, proba):
        """폴른 표시: 반투명 박스, 아이콘, 신뢰도, 클래스별 확률바 (영상 왼쪽 맨 하단)."""
        try:
            h, w = frame.shape[:2]
            box_h = 180
            box_top = h - box_h - 10
            box_bottom = h - 10
            class_name = self.class_names.get(prediction, "Unknown")
            color = self.class_colors.get(prediction, (255, 255, 255))
            confidence = proba[prediction] if prediction < len(proba) else 0
            icon_map = {0: "[OK]", 1: "[ALERT]", 2: "[DANGER]"}
            icon = icon_map.get(prediction, "")
            overlay = frame.copy()
            cv2.rectangle(overlay, (10, box_top), (280, box_bottom), (0, 0, 0), -1)
            blended = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            np.copyto(frame, blended)
            cv2.rectangle(frame, (10, box_top), (280, box_bottom), (255, 255, 255), 1)
            cv2.putText(frame, f"{icon} {class_name}", (20, box_top + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
            cv2.putText(frame, f"Confidence: {confidence*100:.1f}%", (20, box_top + 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset = box_top + 105
            for i, prob in enumerate(proba):
                cls_name = self.class_names.get(i, f"Class {i}")
                bar_width = int(prob * 230)
                cv2.rectangle(frame, (20, y_offset - 10), (20 + bar_width, y_offset + 5),
                              self.class_colors[i], -1)
                cv2.putText(frame, f"{cls_name}: {prob*100:.1f}%", (20, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 25
        except Exception:
            pass
