# Inochi2D-AI-Rigging

기존 `mmm-data` 공개 저장소를 재활용한 **독립 Inochi2D AI 자동 리깅 프로젝트**입니다. M.M.M 데이터 저장소 기능과는 분리되었습니다.

**현재 GitHub 공개본은 0.8 INP/INX 파일의 읽기·구조 검사 및 테스트를 수행하는 초기 부트스트랩입니다.**
자동 메시·자동 리깅·고급 키폼·MCP·Creator 실시간 편집을 완성했다고 주장하지 않습니다.
별도로 제작된 개발용 v0.4 코드 패키지는 단계적으로 이 저장소에 통합해야 합니다.

목표: 공식 자동 메시 생성 활용 → 파츠·랜드마크·회전 중심·부모 좌표계 검증 → 비강체 키폼 최적화 → Creator 실렌더 검증 → AI 반복 수정 → 편집 가능한 최종 모델.
정점·폴리곤·작업량에는 인위적인 상한을 두지 않으며 품질을 최우선으로 합니다.

```bash
python -m pip install -e .
inochi-rig inspect model.inx
python -m unittest discover -s tests -v
```

**원화, 사용자 비공개 캐릭터 자산, AIRI 비공개 코드는 포함하지 않습니다.**
GitHub 저장소 주소는 관리자 설정에서 이름을 변경하기 전까지 `mmm-data`로 유지됩니다.