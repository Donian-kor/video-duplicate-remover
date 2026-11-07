# 동영상 중복 제거기

같은 영상의 여러 버전(다른 해상도/화질) 중 **가장 좋은 품질만 남기고 나머지를 휴지통으로 이동**하는 Windows 데스크톱 프로그램입니다.

## 기능
- 폴더(하위 폴더 포함) 스캔
- ffprobe로 해상도, 비트레이트, 길이, 용량 수집
- 프레임 샘플링 + 지각 해시(pHash)로 같은 영상 판별
- 그룹별로 해상도 → 비트레이트 → 용량 순으로 최고 품질 1개를 "유지", 나머지를 "삭제 예정"으로 표시
- 삭제 전 체크박스로 수동 조정 가능, 삭제는 휴지통 이동(복원 가능)
- 스캔/삭제 진행 상황 로그

## 실행
```
run.bat
```
또는
```
python main.py
```

## 필요 환경
- Python 3.10+
- ffmpeg/ffprobe (PATH에 있어야 함)
- 패키지: PySide6, opencv-python, numpy, send2trash, tqdm

## 옵션
- **샘플 프레임 수**: 많을수록 정확하지만 느림 (기본 8)
- **유사도 임계값**: 낮을수록 엄격 (기본 12). 압축 차이가 큰 중복은 값을 올려보세요.

## 파일 구성
- exe 배포판: `dist\VideoDedup\VideoDedup.exe` (도움말.html 포함)
- 스캔 중 CPU/디스크를 사용합니다. 대용량 폴더는 시간이 걸릴 수 있습니다.


## 외부 프로그램
- **FFmpeg (ffprobe 포함)**: 필수. 없으면 프로그램 실행 시 자동 다운로드/설치 가능.
- Python 소스 실행 시 추가 패키지: PySide6, opencv-python, numpy, send2trash (requirements.txt)

## 배포
- exe 배포판: `dist\VideoDedup\VideoDedup.exe` (도움말.html 포함)
- 소스코드는 비공개이며 exe로만 배포합니다.
