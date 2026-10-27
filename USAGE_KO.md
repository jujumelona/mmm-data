# Inochi2D 제작 보조 모듈 사용법 (2026-10-27)

정식 사용법 원문: https://github.com/jujumelona/mmm-data/blob/main/USAGE_KO.md

현재 코드는 PSD나 .inp/.inx를 직접 읽거나 수정하지 않습니다. 로컬 JSON 좌표/파라미터 샘플을 검사하는 도구와 에어리(AIRI) 모션 매핑용 어댑터입니다. 완성형 AI 자동 리깅 모듈이 아닙니다.

1. 프로젝트 폴더에서 Node.js 20 이상을 사용하여 `npm test` 및 `npm run check` 실행.
2. `npm run providers`로 외부 프로젝트 등록 목록 조회.
3. `npm run checkout-preview`는 다운로드 계획만 표시합니다.
4. `node src/source-checkout.mjs --all --dest ./third_party`는 외부 7개 저장소의 소스를 다운로드만 합니다. 이식하거나 실행하지는 않습니다.
5. `node src/cli.mjs roles examples/layers.json`은 레이어명 분석.
6. `node src/cli.mjs face-propose examples/face.json`은 9개 얼굴 좌표 후보 계산.
7. `node src/cli.mjs mesh-check examples/mesh.json`은 JSON 메시 변형 문제 검사.
8. `node src/cli.mjs mesh-repair examples/mesh.json`은 중립 메시 내부 정점 개선 제안(입력 파일 변경 없음).
9. `node src/cli.mjs motion-check examples/motion.json`은 루프·파라미터 범위 검사.

실제 AIRI 본체에 렌더러를 설치하려면 AIRI 본체 코드를 별도 경로에 받아 놓고, AIRI-Modules 저장소의 최상위에서 실험 브랜치에 다음을 실행합니다.

```
python scripts/install_into_airi.py --airi-root C:\\work\\airi --patch-only
python scripts/install_into_airi.py --airi-root C:\\work\\airi --runtime-only
```

C:\\work\\airi는 실제 AIRI 소스 경로로 교체해야 합니다. 실제 Inochi2D 모델, 모델별 모션 ID, 이벤트 바인딩은 별도로 준비해야 합니다. 실행 결과에 대한 Creator/AIRI WebGL 통합 테스트는 수행되지 않았습니다.

## 실제 INP1 모델의 입출력 및 자동 키폼 초안 (v0.3)

Node.js 기반 `examples/*.json`은 실제 모델이 아니다. v0.3에 추가된 `native/` 명령은 **Inochi2D 0.8계열 `TRNSRTS\0` 형식인 실제 `.inp/.inx` 바이너리**를 읽는다. 0.9계열 INP2는 지원하지 않으며 임의로 변환하지 않는다.

```powershell
# 실제 모델 정보: 노드 GUID, 정점 수, 파라미터, 애니메이션
python native/inp08.py inspect "C:\models\character.inp"

# 원본 바이너리 100% 동일 복사 검증, 텍스처/확장 섹션 보존
python native/inp08.py roundtrip "C:\models\character.inp" --output "C:\models\character_roundtrip.inp"

# 실제 메시·키폼 데이터를 JSON으로 추출
python native/inp08.py extract "C:\models\character.inp" --output "C:\models\character_poses.json"

# 삼각형 뒤집힘/붕괴/과도한 신축 검사
python native/model_qa.py "C:\models\character.inp" --output "C:\models\character_qa.json"
node src/cli.mjs mesh-check "C:\models\character_poses.json"
```

**자동 얼굴 3×3 키폼 초안:** Creator에서 미리 머리 각도 2D 파라미터 및 메시 변형 바인딩을 만들고, `inspect`에 나온 정확한 GUID·모델 좌표를 `examples/native/landmarks-config.template.json`에 입력한 뒤 다음을 실행한다. PSD 한 장에서 모델을 새로 만드는 명령이 아니다.

```powershell
python native/autorig.py plan "C:\models\character.inp" --config "C:\models\face-config.json" --output "C:\models\face-plan.json"
python native/autorig.py apply "C:\models\character.inp" --plan "C:\models\face-plan.json" --output "C:\models\character_candidate.inp" --acknowledge-visual-review-required
python native/model_qa.py "C:\models\character_candidate.inp"
```

자동 생성 키폼은 **저품질 가능성이 있는 초기 번역·원근 오프셋 초안**이다. 가려진 피부/의상 복원, 얼굴 조형의 미적 완성, 리깅 구조 자동 생성, 물리/마스크/손동작, 고급 애니메이션·AIRI 렌더링 검증을 의미하지 않는다. 원본을 자동으로 덮어쓰지 않으며, Creator에서 열어 시각적으로 검수하기 전에는 실전에 적용하지 않는다.

테스트: `npm test` + `npm run test:native` (독립 예제 / 합성 데이터 검증). 실제 캐릭터 Inochi Creator·AIRI E2E 검증은 **아직 미완료**이다.
