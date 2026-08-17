# NaN Freeze Restart Agent

Windows 화면을 OCR로 감시하다가, 테이블 ROI에서 `NaN` 문자열이 임계값 이상이면 프로그램을 끄고 다시 켜는 프로토타입입니다.

Ollama / YOLO는 포함하지 않습니다. 클릭은 **캘리브레이션 좌표**, OCR은 **NaN 카운트 전용**입니다.

## 1차 동작

1. 화면을 주기적으로 캡처합니다.
2. 하단 중앙 **table ROI**에서 `NaN` 토큰 수를 셉니다.
3. 기본 임계값 **21개** 이상이 **연속 2회**이면 freeze로 판정합니다.
4. 지정 좌표로 STOP → 종료(X) → 하단 아이콘(더블클릭) → **10초 대기** → START.
5. 쿨다운(기본 15초) 후 다시 감시하고, 다시 멈추면 같은 시퀀스를 반복합니다.

## 설치

Python 3.10+ (개발 확인: 3.12), Windows 10 1803 이상.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### WinRT OCR (기본, 추가 모델 없음)

Windows 기본 OCR을 씁니다. 영어 텍스트(`NaN`, `STOP`)를 읽으려면 **English OCR 언어 팩**이 있어야 합니다.

- Settings → Time & language → Language → English (United States) → Options → OCR
- 또는 `winsdk` 설치 후 에이전트 대시보드의 `OCR: winrt` 표시를 확인

언어 팩이 없으면 `scan_all`이 빈 결과를 돌려 **카운트 0**으로 처리합니다. 오탐으로 재부팅하지 않습니다.

### 선택 폴백

`ocr.backend: auto` 이면 순서대로 `winrt` → `pytesseract` → `easyocr` 입니다.

```bat
pip install pytesseract
```

Tesseract 실행 파일도 시스템에 설치해야 합니다. EasyOCR은 PyTorch가 따라오므로 프로토타입에서는 권장하지 않습니다.

## 실행

```bat
.venv\Scripts\activate
python -m src
```

또는 `run_agent.bat`.

## 현장 캘리브레이션 (필수)

기본 `config.yaml` 좌표는 1920×1080 가정값입니다. 라인 PC에서 반드시 다시 찍으십시오.

1. 대상 프로그램을 평소 레이아웃으로 띄웁니다.
2. 대시보드 **Calibrate**.
3. **ROI (drag table region)** 에서 NaN이 쌓이는 테이블을 드래그합니다.
4. STOP / Close(X) / Launch icon / START 모드로 바꿔 각 위치를 클릭합니다.
   - 아이콘은 기본 **double click** (작업 표시줄/바탕화면 아이콘).
5. **Save** (Enter). Esc는 오버레이만 닫습니다.

단축키: `r` ROI, `s` STOP, `x` Close, `i` Icon, `t` START.

## 첫 테스트 순서

1. **Dry-run clicks** 체크.
2. **Dry-run recovery** — 로그에 STOP → wait 0.5 → Close → wait 1 → icon → wait 10 → START 만 찍히고 마우스는 움직이지 않아야 합니다.
3. Start monitor — NaN 개수가 임계값 근처인지 로그로 확인합니다.
4. 카운트가 맞으면 체크를 끄고 live 클릭을 켭니다.

`config.yaml`의 `monitor.confirm_scans`(기본 2)와 `cooldown_sec`(기본 15)으로 깜빡임·재발동을 조절합니다.

## 안전장치

- `pyautogui.FAILSAFE`: 마우스를 **화면 모서리**로 밀어 넣으면 클릭이 중단됩니다.
- 대시보드 **Stop** 은 감시 루프를 멈춥니다.
- 복구 시퀀스 중에는 추가 freeze 판정을 하지 않습니다.
- Dry-run 이 켜져 있으면 좌표만 로그하고 클릭하지 않습니다.

복구 클릭은 마우스/키보드를 실제로 움직입니다. 캘리브레이션이 틀리면 다른 창을 누를 수 있습니다.

디스플레이 배율은 **100%** 를 권장합니다. 캡처와 클릭이 모두 pyautogui 좌표를 쓰므로, OS DPI 스케일이 다르면 어긋날 수 있습니다.

## 설정

[`config.yaml`](config.yaml)

| 키 | 기본 | 의미 |
| --- | --- | --- |
| `monitor.interval_sec` | 2 | 캡처 주기 |
| `monitor.confirm_scans` | 2 | 연속 초과 횟수 |
| `monitor.cooldown_sec` | 15 | 복구 후 재발동 금지 |
| `ocr.backend` | auto | winrt / pytesseract / easyocr |
| `ocr.n0n_correction` | false | `N0N` 을 NaN으로 인정 |
| `rois.table` | 하단 중앙 | OCR 영역 `(x,y,w,h)` |
| `points.*` | STOP/X/아이콘/START | 클릭 좌표 |
| `recovery.startup_wait_sec` | 10 | 프로그램 기동 대기 (시퀀스 wait와 맞춤) |
| `rules[].when.all` / `any` | AND / OR | 조건 트리 |
| `rules[].when.*.min` | 21 | NaN 개수 임계값 |

조건 타입 `ocr_count`만 구현되어 있습니다. `error_text`, `screen_frozen_mse`는 자리만 있고 아직 발동하지 않습니다.

이벤트는 `logs/events.jsonl`에 남습니다.

## 테스트

```bat
python -m pytest
```

화면 클릭 없이 OCR 카운트, AND/OR 규칙, dry-run 시퀀스, confirm/cooldown을 검증합니다.

## 비범위 (1차)

Ollama, YOLO 버튼 검출, 다중 모니터 자동 매핑, 대상 창 강제 포커스, EXE 패키징.
