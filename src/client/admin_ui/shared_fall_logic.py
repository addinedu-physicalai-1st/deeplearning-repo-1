"""
낙상 감지 공통 로직 - 사용자 모드(MainWindow)와 관리자 모드(MonitoringPage)에서 동일하게 사용.
관리자 모드에서 설정된 모델/config와 동일한 추론 로직 적용.
"""

import os
import warnings
import numpy as np

_GUI_DIR = os.path.dirname(os.path.abspath(__file__))

KP_NAMES = [
    'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
    'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
    'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
    'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
]
CONF_THRESHOLD = 0.3


def select_target_person_from_results(results, method='largest', frame_shape=None):
    """
    YOLO 결과에서 모니터링 대상자 1명 선택 (관리자 탭과 동일).
    method='largest': 가장 큰 Bounding Box
    """
    if not results or len(results) == 0:
        return None
    kp = results[0].keypoints
    boxes = results[0].boxes
    if kp is None or boxes is None:
        return None
    kp_data = kp.data.cpu().numpy()
    boxes_data = boxes.xyxy.cpu().numpy()
    if len(kp_data) == 0 or len(boxes_data) == 0:
        return None
    if len(kp_data) == 1:
        return 0
    if method == 'largest':
        areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes_data]
        return int(np.argmax(areas))
    return 0


def extract_features_v3b(keypoints, state):
    """
    관리자 탭 MonitoringPage와 동일한 181개 Feature 추출 (v3b).
    state: dict with prev_keypoints, prev2_keypoints, feature_history (mutable, 업데이트됨)
    Returns: (features_dict, ) - state는 인자로 전달된 dict가 in-place 업데이트됨
    """
    try:
        prev_keypoints = state.get('prev_keypoints')
        prev2_keypoints = state.get('prev2_keypoints')
        feature_history = state.get('feature_history', [])
        if feature_history is None:
            feature_history = []
        features = {}

        valid = keypoints[:, 2] > CONF_THRESHOLD
        if np.any(valid):
            xs = keypoints[valid, 0]
            ys = keypoints[valid, 1]
            bbox_x_min = float(np.min(xs))
            bbox_y_min = float(np.min(ys))
            bbox_w = float(np.max(xs) - bbox_x_min)
            bbox_h = float(np.max(ys) - bbox_y_min)
            if bbox_w < 1: bbox_w = 1.0
            if bbox_h < 1: bbox_h = 1.0
        else:
            bbox_x_min, bbox_y_min = 0.0, 0.0
            bbox_w, bbox_h = 1.0, 1.0

        kp_norm = np.zeros((17, 3))
        for i in range(17):
            if keypoints[i][2] > CONF_THRESHOLD:
                kp_norm[i][0] = np.clip((keypoints[i][0] - bbox_x_min) / bbox_w, 0, 1)
                kp_norm[i][1] = np.clip((keypoints[i][1] - bbox_y_min) / bbox_h, 0, 1)
            else:
                kp_norm[i][0] = 0.0
                kp_norm[i][1] = 0.0
            kp_norm[i][2] = float(keypoints[i][2])

        def norm_prev(kp):
            if kp is None:
                return None
            normed = np.zeros((17, 3))
            for i in range(17):
                if kp[i][2] > CONF_THRESHOLD:
                    normed[i][0] = np.clip((kp[i][0] - bbox_x_min) / bbox_w, 0, 1)
                    normed[i][1] = np.clip((kp[i][1] - bbox_y_min) / bbox_h, 0, 1)
                normed[i][2] = float(kp[i][2])
            return normed

        prev_norm = norm_prev(prev_keypoints)
        prev2_norm = norm_prev(prev2_keypoints)

        for i, name in enumerate(KP_NAMES):
            features[f'{name}_x'] = float(kp_norm[i][0])
            features[f'{name}_y'] = float(kp_norm[i][1])
            features[f'{name}_conf'] = float(kp_norm[i][2])

        features['acc_x'] = 0.0
        features['acc_y'] = 0.0
        features['acc_z'] = 0.0
        features['acc_mag'] = 0.0

        def calc_angle(a, b, c):
            ba = np.array([a[0]-b[0], a[1]-b[1]])
            bc = np.array([c[0]-b[0], c[1]-b[1]])
            cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
            return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))

        features['left_elbow_angle'] = calc_angle(keypoints[5], keypoints[7], keypoints[9])
        features['right_elbow_angle'] = calc_angle(keypoints[6], keypoints[8], keypoints[10])
        features['left_knee_angle'] = calc_angle(keypoints[11], keypoints[13], keypoints[15])
        features['right_knee_angle'] = calc_angle(keypoints[12], keypoints[14], keypoints[16])
        shoulder_mid = (keypoints[5][:2] + keypoints[6][:2]) / 2
        hip_mid = (keypoints[11][:2] + keypoints[12][:2]) / 2
        vertical = np.array([hip_mid[0], hip_mid[1] - 100])
        features['spine_angle'] = calc_angle(shoulder_mid, hip_mid, vertical)

        hip_mid_n = (kp_norm[11][:2] + kp_norm[12][:2]) / 2
        shoulder_mid_n = (kp_norm[5][:2] + kp_norm[6][:2]) / 2
        features['hip_height'] = float(hip_mid_n[1])
        features['shoulder_height'] = float(shoulder_mid_n[1])
        features['head_height'] = float(kp_norm[0][1])
        features['bbox_width'] = float(bbox_w / (bbox_w + bbox_h))
        features['bbox_height'] = float(bbox_h / (bbox_w + bbox_h))
        features['bbox_aspect_ratio'] = float(bbox_w / bbox_h)
        features['shoulder_tilt'] = float(abs(kp_norm[5][1] - kp_norm[6][1]))
        features['avg_confidence'] = float(np.mean(keypoints[:, 2]))

        for i, name in enumerate(KP_NAMES):
            if prev_norm is not None and kp_norm[i][2] > CONF_THRESHOLD and prev_norm[i][2] > CONF_THRESHOLD:
                vx = float(kp_norm[i][0] - prev_norm[i][0])
                vy = float(kp_norm[i][1] - prev_norm[i][1])
            else:
                vx, vy = 0.0, 0.0
            speed = float(np.sqrt(vx**2 + vy**2))
            features[f'{name}_vx'] = vx
            features[f'{name}_vy'] = vy
            features[f'{name}_speed'] = speed
            if (prev2_norm is not None and prev_norm is not None and
                kp_norm[i][2] > CONF_THRESHOLD and prev_norm[i][2] > CONF_THRESHOLD and prev2_norm[i][2] > CONF_THRESHOLD):
                prev_vx = float(prev_norm[i][0] - prev2_norm[i][0])
                prev_vy = float(prev_norm[i][1] - prev2_norm[i][1])
                ax, ay = vx - prev_vx, vy - prev_vy
            else:
                ax, ay = 0.0, 0.0
            features[f'{name}_ax'] = ax
            features[f'{name}_ay'] = ay
            features[f'{name}_accel'] = float(np.sqrt(ax**2 + ay**2))

        features['hip_velocity'] = (features.get('left_hip_speed', 0) + features.get('right_hip_speed', 0)) / 2
        features['hip_acceleration'] = (features.get('left_hip_accel', 0) + features.get('right_hip_accel', 0)) / 2

        feature_history.append({
            'hip_height': features['hip_height'],
            'shoulder_height': features['shoulder_height'],
            'head_height': features['head_height'],
            'acc_mag': features['acc_mag'],
        })
        if len(feature_history) > 5:
            del feature_history[:-5]
        hist = feature_history
        for key in ['hip_height', 'shoulder_height', 'head_height']:
            vals = [h[key] for h in hist]
            features[f'{key}_mean_5'] = float(np.mean(vals))
            features[f'{key}_std_5'] = float(np.std(vals))
        features['acc_mag_diff'] = 0.0
        vals = [h['acc_mag'] for h in hist]
        features['acc_mag_mean_5'] = float(np.mean(vals))
        features['acc_mag_std_5'] = float(np.std(vals))

        state['prev2_keypoints'] = prev_keypoints.copy() if prev_keypoints is not None else None
        state['prev_keypoints'] = keypoints.copy()
        state['feature_history'] = feature_history
        return features
    except Exception as e:
        print(f"[shared_fall_logic] Feature 추출 오류: {e}")
        return {}


def extract_simple_features(keypoints):
    """
    관리자 모드 MonitoringPage와 동일한 Feature 추출.
    hip_height, aspect_ratio (및 RF 모델용 181차원 시 보조 피처).
    """
    features = {}
    left_hip = keypoints[11]
    right_hip = keypoints[12]
    if left_hip[2] > 0.5 and right_hip[2] > 0.5:
        features["hip_height"] = (left_hip[1] + right_hip[1]) / 2
    else:
        features["hip_height"] = 0

    x_coords = keypoints[:, 0][keypoints[:, 2] > 0.5]
    y_coords = keypoints[:, 1][keypoints[:, 2] > 0.5]
    if len(x_coords) > 0:
        w = np.max(x_coords) - np.min(x_coords)
        h = np.max(y_coords) - np.min(y_coords)
        features["aspect_ratio"] = w / (h + 1e-6)
    else:
        features["aspect_ratio"] = 1.0

    return features


def predict_fall_rf(features, rf_model=None, feature_columns=None):
    """
    Random Forest 낙상 예측 - 관리자 모드 MonitoringPage와 동일.
    rf_model, feature_columns가 있으면 실제 RF 모델 사용, 없으면 규칙 기반 fallback.
    DataFrame 사용 및 Binary(2class)->3class 변환 포함.

    Returns:
        (prediction, proba): prediction 0=Normal, 1=Falling, 2=Fallen
    """
    try:
        if rf_model is not None and feature_columns and len(feature_columns) > 0:
            import pandas as pd
            row = {col: features.get(col, 0) for col in feature_columns}
            df = pd.DataFrame([row])
            proba = rf_model.predict_proba(df)[0]
            if len(proba) == 2:
                prediction = 0 if proba[0] > proba[1] else 2
                return prediction, [float(proba[0]), 0.0, float(proba[1])]
            prediction = int(np.argmax(proba))
            return prediction, [float(p) for p in proba]

        hip_height = features.get("hip_height", 0)
        aspect_ratio = features.get("bbox_aspect_ratio", features.get("aspect_ratio", 1.0))
        if hip_height < 0.5:
            if aspect_ratio > 1.5:
                return 2, [0.1, 0.2, 0.7]
            return 1, [0.2, 0.6, 0.2]
        return 0, [0.8, 0.15, 0.05]

    except Exception:
        return 0, [1.0, 0.0, 0.0]


def load_rf_model_if_available():
    """관리자 모드와 동일한 RF 모델/feature_columns 로드."""
    import joblib

    model_path = os.path.join(_GUI_DIR, "models", "3class", "random_forest_model.pkl")
    feature_path = os.path.join(_GUI_DIR, "models", "3class", "feature_columns.txt")
    rf_model = None
    feature_columns = None

    if os.path.exists(model_path) and os.path.exists(feature_path):
        try:
            rf_model = joblib.load(model_path)
            with open(feature_path, "r") as f:
                lines = f.readlines()
                feature_columns = []
                for line in lines[2:]:
                    if ". " in line:
                        feature_name = line.strip().split(". ", 1)[1]
                        feature_columns.append(feature_name)
        except Exception as e:
            print(f"[shared_fall_logic] RF 모델 로드 실패: {e}")

    return rf_model, feature_columns
