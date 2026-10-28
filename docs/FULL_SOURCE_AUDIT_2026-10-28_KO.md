# 전체 저장소 재감사 — 2026-10-28

## 범위 및 판정
현재 공개 프로젝트의 native(파일 파서·메시·키폼), rigging(좌표·피벗·바인딩·트랜잭션·Creator RPC·MCP), JS(메시·모션·시맨틱 검증), 테스트·CI·문서를 확인했다. 통과한 CI는 합성 모델과 모의 Creator 기반이며 실제 패치된 Creator 0.8 실기 동작/시각적 완성도를 검증한 것이 아니다.

## 이번에 재현·수정한 신규 결함
1. **다른 프로젝트에 잘못된 파라미터 복원:** 캡처 도중 프로젝트가 전환되면 finally의 무조건적인 set_parameter가 새 프로젝트를 바꿀 수 있었다. 복원 전에 프로젝트 식별자를 확인하고 달라졌으면 편집을 거부하며 수동 복구 필요를 알린다.
2. **일반 바인딩이 존재하지 않는 노드 지칭:** geometry_audit은 deform에만 GUID 참조 검사를 수행했다. 모든 바인딩의 대상 노드 GUID 검증을 추가.
3. **일반 바인딩 키폼 데이터 오류:** 스칼라 값·isSet 모양·키폼 축 크기·opacity 유효 범위를 검사하지 않았다. 이제 편집 전에 거부.
4. **MCP approved-plan 경로의 검사 우회:** 계획 적용 도구는 개별 키폼만 확인하고, 일반 트랜잭션의 복합 파라미터 조합 검사를 건너뛰었다. 통합 quality gate를 적용하고 확장자를 INP/INX로 제한.

## 프로젝트 전체 위험 지도
- native/inp08.py: 0.8 INP parser/writer, texture+extension preservation, strict JSON/key/topology; 공식 모델 다종 호환성 미입증.
- native/autorig.py, rigging/deform.py: 초기 keyform proposal / TPS만. AI가 직접 전체 캐릭터를 리깅하는 엔진 아님.
- rigging/spaces.py, contracts.py, handoff.py: 명시 좌표·부모 계층·fingerprint 보존. Creator 실제 월드 pivot과 physics 영향은 검사되지 않음.
- rigging/agent_editor.py, transactions.py, topology.py, quality.py: 파일 기반 수정, 도형·쌍별 근사 품질 검사. 실제 SDK 블렌딩 / 렌더 외양 검사는 아님.
- rigging/creator_bridge.py, live_model_bridge.py, live_qa.py: localhost 브리지 RPC 및 파일 왕복. Native Creator 내 메모리 버텍스·바인딩/렌더 루프 없음. 기존 프로젝트 Undo 이력은 리임포트 시 소실 가능.
- rigging/mcp_server.py, cli.py: 모델 조작 표면; tool availability는 실제 Creator 연결 성공의 증거가 아님.
- src/*.mjs: 후보안·간이 품질/모션 추정. 최종 Inochi 공식 편집/합성 구현이 아님.
- tests/ 및 .github/workflows/: 합성·프로토콜 검증, real Creator GUI/IPC native 빌드 검증 단계가 빠짐.

## 미해결 차단 사항
Creator 내부 정점/바인딩/피벗/마스크/물리 native edit, 실제 렌더 비교, 2D/3D 결합 자세 테스트, TTS viseme 통합, PSD/PNG 시맨틱 파츠 생성, 완전 자동 iterative art quality loop, Windows Creator 현장 테스트. 장기적으로 native bridge를 구현하고 공식 INP 0.8 예제들과 픽셀 비교 테스트가 필요하다.

수정된 CI 통과는 **코드의 특정 안전성 보강**을 의미하며 **완벽**이나 **전문 리깅 품질 인증**을 의미하지 않는다.

## 2차 전체 진입점 감사 — 레거시 CLI
- native/autorig.py의 apply 명령이 변조된 계획에서 allow_replace 플래그를 그대로 하위 편집기에 넘겨 기존 키폼을 덮어쓸 수 있었다. 실제 중앙 키폼을 덮어쓰는 반례를 재현했다. 이제 키폼 화이트리스트·중복 대상·조합 기하 검사를 적용한다.
- rigging/cli.py의 proposal 및 native/model_qa.py의 JSON 출력은 실행 전 exists 검사만 하고 write_text로 저장해 경쟁 조건에서 기존 데이터를 덮어쓸 수 있었다. 공통 atomic_write(no overwrite)로 수정.
- 테스트: tests/test_alternate_writers.py, tests/test_comprehensive_review.py, tests/test_plan_commit_gate.py
