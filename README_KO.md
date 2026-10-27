# Inochi2D-AI-Rigging — 한국어 사용 안내

이 저장소는 **단순 MCP 서버가 아니라 Inochi2D 0.8 제작 보조 엔진 + 안전한 AI 편집 인터페이스 + CLI + 선택적 MCP 서버**다. 현재 완성형 자동 리깅 프로그램은 **아니다**.

### 실제 가능한 것

- 기존 `.inx/.inp` 모델 구조 분석 및 원본 보존형 파일 쓰기
- 정점·삼각형·개별 변형 키폼 기하 검사
- 원화 픽셀 좌표/모델 좌표/회전 중심/관절 위치를 GUID와 SHA-256으로 묶어 전달
- 3개 이상의 비공선 랜드마크를 이용한 비강체(TPS) 변형 키폼 후보 생성
- 이미 존재하는 파라미터/메시/바인딩의 비어 있는 키폼만 수정 제안
- Creator를 별도 패치한 경우 노드·파라미터를 조회하는 MCP 연결

### 아직 구현하지 않은 것

PSD를 넣으면 수백 개 파츠가 완전 자동 리깅되는 기능, 수만 정점 최적화, 고급 물리 자동 구성, 실제 Creator 기반 AI 시각 평가 루프, 기준점 이동에 따른 전 계층·바인딩 자동 보정, 전문 리거 품질 우위 입증. **이 기능들을 구현한 척하지 않는다.**

### 실행

```powershell
cd Inochi2D-AI-Rigging
python -m pip install -e .
python -m unittest discover -s tests -p test_*.py -v
python -m unittest discover -s native -p test_*.py -v
npm test
python -m rigging.cli --help
python -m rigging.cli inspect "C:\\Models\\your-model.inx"
```

MCP는 추가 설치 후 `python -m rigging.mcp_server`로 실행한다.

```powershell
python -m pip install -e ".[mcp]"
python -m rigging.mcp_server
```

Creator 화면 직접 제어는 [inochi-creator-mcp](https://github.com/ozekimasaki/inochi-creator-mcp)를 별도로 설치하고 Inochi Creator `v0_8`의 수정 빌드를 실행해야 한다. 공식 배포 바이너리에는 이 제어 인터페이스가 없다. 외부 HTTP 브리지는 기본적으로 `127.0.0.1:17320`만 사용한다.

**안전 규칙:** 작업 원본을 덮어쓰지 않으며, 좌표 단위·기준점·부모 GUID가 빠지면 수정하지 않는다. 미리 제작한 키폼은 승인 없이 덮어쓰지 않는다. 정식 Creator 및 실제 렌더링 QA 없이는 고급 리깅 완료라고 표시하지 않는다.

### 공개 GitHub 저장소

현재 소스 44개 파일을 기존 공개 저장소 [jujumelona/mmm-data](https://github.com/jujumelona/mmm-data)에 업로드했습니다. 데이터 저장소로 사용하던 파일은 현재 main 브랜치에서 제거했고, M.M.M의 기본 연결도 끊었습니다.

현재 **저장소 주소는 아직 `mmm-data`**입니다. 필요하면 GitHub 저장소 **Settings → General → Repository name**에서 `Inochi2D-AI-Rigging`으로 변경할 수 있습니다. 저장소 URL 이름만 바뀌며, 프로그램 기능에는 영향을 주지 않습니다.

새 저장소를 만들 필요는 없습니다. 수정 사항은 이 저장소 main 브랜치에 커밋하면 됩니다. `scripts/publish_public.sh` 역시 새 저장소를 생성하지 않고 현재 저장소 위치만 안내합니다.
