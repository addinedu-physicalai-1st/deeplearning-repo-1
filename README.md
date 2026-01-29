# deeplearning-repo-1
# 🏠 Home Care-Vision AI (YOLO OSEM)

> **비전 딥러닝을 활용한 홈 세이프 솔루션** > YOLO 및 AI 모델 기반 이상 행동 패턴 감지 및 실시간 알람 시스템

---

## 📝 프로젝트 개요 (Project Overview)

본 프로젝트는 가정 내 안전 사고 예방을 위해 AI 기술을 활용하여 가족의 상태를 실시간으로 모니터링하고, 낙상이나 기절 등 이상 상황 발생 시 즉각적인 대응을 통해 **골든타임(Golden Time)** 을 확보하는 것을 핵심 목적으로 합니다.

### 🎯 핵심 목적
- **가족 안전 실시간 모니터링**: 실시간 영상 분석을 통한 24시간 안전 관리
- **응급 상황 즉각 대응**: 낙상, 기절 등 발생 시 보호자에게 신속한 알람 전파
- **취약 계층 케어**: 영·유아 위험 구역 이탈 방지 및 고령층 낙상 사고 감지

---

## 🛠 기술 스택 (Tech Stack)

| 구분 | 기술 | 설명 |
| :--- | :--- | :--- |
| **객체 탐지** | `YOLO v11` | 실시간 객체 탐지 및 위치 추적 |
| **포즈 분석** | `Pose Estimation` | 관절 포인트(Keypoints) 추출 및 수치화 |
| **동작 학습** | `Random Forest` / `LSTM` | 정적 자세 및 시계열 행동 흐름 학습 |
| **데이터베이스** | `MySQL 8.0` | 학습 데이터 및 로그 저장 |
| **환경** | `Python 3.12.3`, `OpenCV 4.13.0` | 영상 처리 및 시스템 통합 |

---

## ⚙️ 시스템 아키텍처 (System Architecture)

1. **데이터 수집**: 웹캠, 동영상 파일 또는 기존 데이터셋 활용
2. **데이터 추출**: YOLO Pose를 활용하여 관절 좌표(37개 벡터) 데이터화
3. **상태 분류**: 
   - `Standing`: 정상 활동
   - `Fall_Normal`: 일반적인 눕기 또는 낮은 위험
   - `Fall_Emergency`: 급격한 낙상 및 응급 상황
4. **알람 로직**: 이상 상태 감지 시 시간 기반(예: 3초 이상 무응답) 최종 판단 및 알림

---

## 🌟 기대 효과 (Expected Effects)

- **사회적 안전망 구축**: 독거 노인 고독사 예방 및 응급 구조 지원
- **스마트 홈 고도화**: 부재중 영·유아 및 반려동물의 건강·안전 확인
- **지능형 관제**: 자동화된 모니터링을 통한 관제 효율 극대화 및 인건비 절감

---

## 👥 팀 구성원 (Team Members)

| 역할 | 이름 | 담당 업무 |
| :--- | :--- | :--- |
| **PM** | **이건희** | 프로젝트 기획 및 총괄, 시스템 아키텍처 설계 |
| **Team Member** | **이준근** | AI 모델 학습 및 데이터 파이프라인 구축 |
| **Team Member** | **조익연** | YOLO Pose 데이터 추출 및 전처리 |
| **Team Member** | **공국진** | UI/UX 모니터링 대시보드 개발 |
| **Team Member** | **노영주** | 알람 시스템 및 DB 연동 최적화 |

---

## 🚀 시작하기 (Quick Start)

```bash
# 저장소 복제
git clone https://github.com/addinedu-physicalai-1st/deeplearning-repo-1.git

# 필수 라이브러리 설치
pip install -r requirements.txt

# 데이터 추출 및 학습 실행
python unified_extractor.py  # 데이터 수집
python train_and_eval.py     # 모델 학습
-. Team Members: 이준근, 조익연, 공국진, 노영주
