# Inochi2D-AI-Rigging — 한국어 사용 안내

이 저장소는 **단순 MCP 서버가 아니라 Inochi2D 0.8 제작 보조 엔진 + 안전한 AI 편집 인터페이스 + CLI + 선택적 MCP 서버**다. 현재 완성형 자동 리깅 프로그램은 **아니다**.

**v0.5.0 추가:** 여러 작업을 한 번에 검사/새 파일로 저장하는 트랜잭션, 공유 모서리의 정확한 정점·UV·기존 keyform 세분화, 실제 Creator viewport 증거 수집(패치된 Creator 필요), 2개 파라미터 조합의 보수적 기하 안전 검사. 사용법과 한계: `docs/TRANSACTIONS_LIVE_QA_KO.md`.

### 실제 가능한 것

- 기존 `.inx/.inp` 모델 구조 분석 및 원본 보존형 파일 쓰기
- 정점·삼각형·개별 변형 키폼 기하 검사
- 원화 픽셀 좌표/모델 좌표/회전 중심/관절 위치를 GUID와 SHA-256으로 묶어 전달
- 3개 이상의 비공선 랜드마크를 이용한 비강체(TPS) 변형 키폼 후보 생성
- 이미 존재하는 파라미터/메시/바인딩의 비어 있는 키폼만 수정 제안
- Creator를 별도 패치한 경우 노드·파라미터를 조회하는 MCP 연결
- `rig_manual_handoff`: GUID·부모·메시·UV·파라미터/키폼·마스크·텍스처 원본 참조를 실제 저장 파일에서 조회
- `rig_binding_vertex_slice`: 수만 정점 모델에서도 필요한 키폼의 정점·UV·변위만 구간별 조회

- 원본을 덮어쓰지 않는 원자적 배치 편집: `rig_preview_transaction`/`rig_commit_transaction`, CLI `transaction`.
- 기존 키폼 전체를 보간 보존하는 정점 세분화: `subdivide_mesh`.
- Creator의 실시간 파라미터·viewport 캡처 증거 수집: `creator_capture_pose_sweep` (연결된 실행 환경에서만).

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

### 공개 저장소 생성

현재 연결된 GitHub 도구에는 **새 저장소 생성 기능이 없으므로**, 프로젝트를 준비하더라도 자동으로 공개 저장소를 생성했다고 말할 수 없다. 별도 ZIP의 프로젝트 루트에서, PC에 Git과 GitHub CLI를 설치하고 `gh auth login`으로 로그인한 뒤:

```bash
bash scripts/publish_public.sh --confirm-public
```

위 스크립트는 모델 파일·개인 프로젝트 문자열을 검사하고 `jujumelona/Inochi2D-AI-Rigging`이라는 **공개** 저장소를 생성·푸시한다. 이 작업은 사용자가 직접 명령을 실행할 때만 수행된다.

### 기준점과 리깅 컨텍스트 조회 (신규)

```bash
python -m rigging.cli manual-handoff model.inx NODE_GUID --anchors anchors.json
python -m rigging.cli binding-slice model.inx NODE_GUID PARAM_GUID 0 2 2 --start 0 --limit 256
```

동일한 `rig_manual_handoff`, `rig_binding_vertex_slice` MCP 도구가 있다. 노드의 실제 리깅 필드가 없으면 추측하지 않고 `null` 또는 별도 `missing_live_evidence`에 기록한다. 자세한 통합 설계와 미구현 목록: `docs/MCP_ENGINE_INTEGRATION_ROADMAP_KO.md`.

현재 공개 GitHub 저장소는 `https://github.com/jujumelona/mmm-data`이며, 기존 데이터 저장소 코드를 대체한 상태다. 저장소 이름 변경은 별도 관리 작업이다.


### AI 직접 편집 MCP (v0.6)

MCP 도구 `rig_agent_capabilities` → `rig_agent_model_map` → `rig_agent_read_target` → `rig_agent_preview_batch` → `rig_agent_save_batch` 를 통해 AI가 기존 키폼, 메시 정점, UV 및 일부 노드·파라미터 바인딩 값을 직접 읽고 수정할 수 있습니다. 모든 편집에는 원본 SHA-256, 각 편집 대상의 예상 해시, 명시적 좌표계와 엄격한 기하 검사가 필요합니다. 사용자가 매번 키폼을 조작할 필요 없이 **새 모델 파일만** 저장합니다.

**미구현:** 실행 중인 Inochi Creator의 정점·물리·마스크 직접 편집, 고급 자동 리깅 전 과정, 비전 기반 미적 판정 및 자동 반복 보정. MCP 도구를 추가한 것과 이 기능이 완성됐다는 것은 다릅니다.
