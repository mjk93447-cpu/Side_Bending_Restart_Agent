# NaN Freeze Restart Agent

Windows 화면을 OCR로 감시하다가, 테이블 ROI에서 `NaN`이 임계값 이상이면 STOP → 종료 → 재실행 → START 로 복구합니다.

**오프라인 보안 PC** 에서는 Python / Tesseract / pip 설치 없이 GitHub Release의 **windows-x64 zip 통팩**만 복사하면 됩니다.

## 오프라인 통팩 (권장)

릴리즈: https://github.com/mjk93447-cpu/Side_Bending_Restart_Agent/releases

1. `SideBendingRestartAgent-0.2.0-windows-x64.zip` 을 USB 등으로 보안 PC에 복사합니다.
2. 압축을 풉니다. 인터넷, Python, Tesseract 설치는 필요 없습니다.
3. `RUN.bat` 또는 `SideBendingRestartAgent.exe` 를 실행합니다.
4. **Calibrate** 로 ROI와 클릭 좌표를 저장합니다.
5. **Dry-run clicks** 로 시퀀스를 확인한 뒤 live 로 전환합니다.

통팩 구성:

- `SideBendingRestartAgent.exe` — Python 런타임 + OpenCV + pyautogui + winsdk
- `tesseract/` — Tesseract 5.5.3 실행 파일과 `eng.traineddata` (시스템 설치 불필요)
- `config.yaml` — EXE 옆에 있는 쓰기 가능한 설정
- `logs/` — 실행 후 `agent.log`, `events.jsonl`

OCR 순서 (`ocr.backend: auto`): Windows 내장 OCR(언어 팩이 있을 때) → **번들 Tesseract**. EasyOCR/PyTorch는 통팩에 넣지 않습니다.

## 개발자 설치 (인터넷 있는 PC)

Python 3.10+ (확인: 3.12), Windows 10 1803 이상.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src
```

통팩을 다시 만들 때:

```bat
powershell -ExecutionPolicy Bypass -File scripts\build_offline_pack.ps1 -Version 0.2.0
```

산출물: `dist/SideBendingRestartAgent-0.2.0-windows-x64.zip`

## 동작

1. 화면을 주기적으로 캡처합니다.
2. **table ROI**에서 `NaN` 토큰 수를 셉니다.
3. 기본 임계값 **21개** 이상이 **연속 2회**이면 freeze로 판정합니다.
4. STOP → 종료(X) → 아이콘 더블클릭 → **10초 대기** → START.
5. 쿨다운(기본 15초) 후 다시 감시합니다.

## 현장 캘리브레이션 (필수)

기본 좌표는 1920×1080 가정값입니다. 라인 PC에서 다시 찍으십시오.

1. 대상 프로그램을 평소 레이아웃으로 띄웁니다.
2. 대시보드 **Calibrate**.
3. 테이블 ROI를 드래그합니다.
4. STOP / Close(X) / Launch icon / START 위치를 클릭합니다. 아이콘은 기본 더블클릭입니다.
5. **Save** (Enter).

단축키: `r` ROI, `s` STOP, `x` Close, `i` Icon, `t` START.

## 안전장치

- `pyautogui.FAILSAFE`: 마우스를 화면 모서리로 밀어 넣으면 클릭이 중단됩니다.
- 대시보드 **Stop** 은 감시 루프를 멈춥니다.
- Dry-run 이 켜져 있으면 좌표만 로그하고 클릭하지 않습니다.
- 디스플레이 배율 **100%** 권장 (캡처와 클릭이 같은 pyautogui 좌표).

## 설정

[`config.yaml`](config.yaml) — 통팩에서는 EXE와 같은 폴더에 있습니다.

| 키 | 기본 | 의미 |
| --- | --- | --- |
| `monitor.interval_sec` | 2 | 캡처 주기 |
| `monitor.confirm_scans` | 2 | 연속 초과 횟수 |
| `monitor.cooldown_sec` | 15 | 복구 후 재발동 금지 |
| `ocr.backend` | auto | winrt / pytesseract |
| `ocr.n0n_correction` | false | `N0N` 을 NaN으로 인정 |
| `rois.table` | 하단 중앙 | OCR 영역 |
| `points.*` | STOP/X/아이콘/START | 클릭 좌표 |
| `rules[].when.*.min` | 21 | NaN 개수 임계값 |

`TESSERACT_CMD` 환경 변수로 번들 경로를 덮어쓸 수 있습니다. 기본은 EXE 옆 `tesseract\tesseract.exe` 입니다.

## 테스트

```bat
python -m pytest
```

## 비범위

Ollama, YOLO, EasyOCR/PyTorch, 다중 모니터 자동 매핑, 대상 창 강제 포커스.
