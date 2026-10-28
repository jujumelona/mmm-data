# 안전한 대량 리깅 편집과 Creator 실기 검사 (v0.5.0)

> **구현 범위:** Inochi2D 0.8 INP1 파일. 자동 메시 세분화는 **리깅 정밀도를 추가할 공간을 만드는 기능**이지 원화를 자동으로 예쁘게 만드는 기능이 아닙니다. 이 저장소는 완성형 자동 리거나 전문 작업자 대비 성능 우위를 입증하지 않았습니다.

## 왜 편집 정보 계약이 필요한가

- `node_guid`와 `parameter_guid`는 표시 이름보다 우선합니다. 기존 파츠 이름이 겹쳐도 잘못된 바인딩에 쓰지 않아야 합니다.
- `source_sha256`과 `expected_mesh_sha256`가 다르면 편집을 거부합니다. 수동 Creator에서 부모·메시·키폼을 고친 뒤 **오래된** AI 작업안을 적용하면 안 됩니다.
- `rig_manual_handoff`로 GUID, 부모 체인, 변형 축, UV, 메시, 가림·물리 관련 저장 필드를 먼저 전달합니다. 단, 저장된 `transform`은 *실제 라이브 Creator의 물리/파라미터 합성 후 위치*와 다릅니다.
- 크롭된 원화 이미지의 픽셀과 모델 좌표를 동일시하면 안 됩니다. 명시적 `image_origin_px`, `local_origin`, `axes`, `model_units_per_pixel` 계약이 필요합니다.
- `rotation_center`, `joint_center`, `landmark`, `seam`, `attachment`, `occlusion_anchor`는 의미가 다릅니다. 좌표만 같아도 대체할 수 없습니다.

## 원자적 배치 편집

1. `inochi-rig inspect model.inx`와 `rig_manual_handoff`에서 GUID와 현재 메시 정보를 얻습니다.
2. 원본 모델 SHA와 정확히 일치하는 다음 JSON을 작성합니다. 아래 SHA 및 메시 SHA는 **실제 조회 값으로 교체**해야 합니다.

```json
{
  "format": "inochi-ai-rigging.transaction.v1",
  "request_id": "session-1-face-mesh-refinement",
  "source_sha256": "REPLACE_WITH_ORIGINAL_SHA256",
  "edits": [
    {"op": "subdivide_mesh", "node_guid": "NODE_GUID", "expected_mesh_sha256": "REPLACE_WITH_MESH_SHA256"}
  ]
}
```

3. **변경 없이 드라이런:** `python -m rigging.cli transaction model.inx batch.json`.
4. **새 파일 생성:** `python -m rigging.cli transaction model.inx batch.json --out new-model.inx --commit`. `--commit` 시 조합 안전 검사는 끌 수 없습니다.
5. 새 `.inx`를 Creator 0.8에서 열어 실제 얼굴·관절·마스크·물리·모션·투명도 변형을 수동/비전 검사합니다. 출력물을 열었다고 품질 향상을 뜻하지 않습니다.

두 번째 지원 작업 `set_new_keyform`은 **기존 deform 바인딩의 비어 있는** 키폼에만 정점별 `[dx,dy]`를 기록합니다.

```json
{
  "op": "set_new_keyform",
  "parameter_guid": "PARAMETER_GUID",
  "node_guid": "NODE_GUID",
  "key_index": [2, 2],
  "vertex_offsets": [[0.0,0.0]]
}
```

위 `vertex_offsets` 예시는 형식만 보인 것이므로 실제로는 **모든 정점 수와 동일**한 원소가 있어야 합니다. 기존 키폼 덮어쓰기와 `allow_unsafe` 플래그는 지원하지 않습니다.

### 보장과 한계

- `subdivide_mesh`는 각 삼각형을 네 개로 나누며 **공유 모서리 중간점**을 하나만 생성합니다. 기존 정점·UV·삼각형의 방향·모든 2D keyform 오프셋을 동일한 선형 보간으로 확장합니다.
- 단일 키폼의 접힘·면적 급감·과도한 신장을 검사하며, **서로 다른 파라미터 두 개의 오프셋을 단순 합산한 보수적 근사 검사**도 실행합니다.
- Inochi2D의 실제 합성 방식에는 계층적 디포머·보간·마스크·물리가 포함되어 있습니다. **조합 근사 검사 통과가 실제 렌더링 합격을 증명하지 않습니다.** 반대로 근사 검사에서 실패해도 실제 렌더링이 반드시 실패하는 것은 아닙니다.
- 작업 하나라도 실패하면 `commit` 전 전체 배치를 폐기합니다. 새 파일은 임시 파일 후 **배타적 파일 생성**으로 공개하여 원본을 덮어쓰지 않습니다. 기존 `.inx/.inp`의 texture/extension 섹션을 그대로 보존합니다.
- 정점 연동 여부가 불분명한 추가 메시 필드 또는 미지원 바인딩 속성이 있으면 세분화를 거부합니다.
- 모델에 이미 잘못된 개별 키폼이 남아 있으면 배치 저장은 거부됩니다. Creator에서 원인을 먼저 수정해야 합니다.

## 실행 중인 Creator 실기 증거

`creator_capture_pose_sweep(parameter_uuid, poses, acknowledge_live_mutations=true)` MCP 도구는 **패치된 Creator 0.8**이 실행 중일 때만 동작합니다. 환경 변수 `INOCHI_CREATOR_MUTATIONS=1`도 필요합니다. 프로젝트·파라미터·범위를 검증하고 실제 `set_parameter` → `list_parameters` → `capture_viewport`를 호출합니다. 완료/실패 시 원래 파라미터 값을 되돌리는 것을 확인합니다. 결과는 **PNG 자체가 아닌 이미지 SHA-256·크기·캡처 시점 값**만 돌려줍니다. 캐릭터 이미지를 사용자에게 전송하지 않습니다.

- 원본 프로젝트가 열린 상태, 편집 매개변수 arming 해제, 애니메이션/물리/타인 수동 편집과 동시 작동 없음이 전제입니다.
- 캡처 픽셀을 기준 원화와 비교하는 컴퓨터비전 AI, Creator 내부 메시/바인딩 수정을 위한 D 브리지, 진짜 물리 동작 검증은 **아직 미구현/미검증**입니다.
- 이 테스트는 Creator SDK v0.8의 실제 실행 증거가 있어야 성공하며, 모의 결과를 실기 결과로 표시하면 안 됩니다.

## MCP 대응 도구

`rig_preview_transaction`, `rig_commit_transaction`, `rig_geometry_audit`, `rig_manual_handoff`, `rig_binding_vertex_slice`, `creator_probe_connection`, `creator_capture_pose_sweep`.

완성형 고품질 AI 리깅을 위해 남은 과제는 Creator 0.8 D 브리지에서 **실제 편집 모델의 메쉬·UV·바인딩·물리·마스크를 원자적으로 수정하는 API**, 이미지/기준점 캘리브레이션, 관절별 신체·얼굴 리깅 생성, 렌더링 시각 평가와 자동 보정 루프입니다. 이를 구현 완료로 표시하지 마십시오.
