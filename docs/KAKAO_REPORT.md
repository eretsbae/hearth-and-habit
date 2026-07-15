# 주간 트래픽 리포트 → 카카오톡 설정 (최초 1회, 약 10분)

매주 월요일 아침(09:23 KST) GitHub Actions가 Blogger 조회수를 수집해서:

1. `data/traffic_history.json`에 주간 스냅샷 누적 (전주 대비 증감 계산용)
2. `docs/reports/weekly-YYYY-MM-DD.md`에 상세 리포트 커밋
3. **카카오톡 "나에게 보내기"로 4줄 요약 전송** (상세 리포트 링크 버튼 포함)

1·2번은 아무 설정 없이 즉시 동작합니다(구글 시크릿만 있으면 됨). 3번 카카오톡 전송만
아래 1회 설정이 필요합니다. 설정 전까지는 전송만 조용히 건너뜁니다.

## 1. Kakao Developers 앱 만들기 + 비즈 앱 전환

1. https://developers.kakao.com 접속 → 카카오 계정 로그인 → **내 애플리케이션 → 애플리케이션 추가하기**
   - 앱 이름/회사명: 아무거나 (예: `hearth-habit-report`)

2. **비즈 앱 전환 (필수, 즉시 완료)** — 현행 카카오 정책상 카카오톡 메시지 API("나에게
   보내기" 포함)는 비즈 앱에서만 쓸 수 있습니다. 무료이고, 사업자등록번호 없이도 콘솔에서
   바로 전환됩니다 (과거의 데브톡 개별 신청 방식은 폐지됨):
   - 앱 선택 → **앱 설정 → 일반** → 아래로 스크롤 → **비즈니스 정보** 섹션의
     **[개인 개발자 비즈 앱 전환]** 버튼 클릭 (사업자번호가 있다면 같은 섹션에서
     사업자 정보로 전환해도 됩니다)
   - 버튼이 비활성화되어 있으면 선행 조건(보통 같은 페이지 상단의 **앱 아이콘 등록**,
     카카오계정 본인인증)을 먼저 채운 뒤 다시 시도하세요.
   - 전환 전까지는 아래 단계의 talk_message 동의항목이 잠겨 있습니다.

3. **리다이렉트 URI 등록** — 2025-12 콘솔 개편으로 예전 "플랫폼 → Web 등록" 메뉴는
   없어졌고, 플랫폼 정보가 앱 키 하위로 이동했습니다:
   - **앱 → 플랫폼 키 → "Default Rest API Key" 카드 클릭** → **리다이렉트 URI**에
     `http://localhost:8765` 등록 (같은 화면에 사이트 도메인 항목이 있으면 동일 값 등록)
   - 그 화면의 **클라이언트 시크릿** 상태도 확인해두세요 — "사용함"이면 시크릿 값을 복사
     (아래 인증 단계에서 물어봅니다), "사용 안 함"이면 무시
4. **카카오 로그인** 메뉴 → 활성화 **ON**
5. **카카오 로그인 → 동의항목** → **카카오톡 메시지 전송(talk_message)** → 사용 설정
6. **앱 → 플랫폼 키**에서 **REST API 키** 값 복사

## 2. 로컬에서 1회 인증

리포지토리를 클론한 본인 컴퓨터에서:

```bash
cd hearth-and-habit
python generator/kakao_auth.py
```

- REST API 키 입력 → 클라이언트 시크릿 입력(콘솔에서 "사용함"인 경우만, 아니면 Enter)
  → 브라우저에서 카카오 로그인 + 메시지 전송 동의
- 토큰 파일 암호화용 passphrase를 직접 정해 입력 (기억해두거나 비밀번호 관리자에 저장)
- 완료되면 `.secrets/kakao_token.enc`(암호화된 토큰 파일)가 생성됩니다

## 3. 시크릿 등록 + 토큰 파일 커밋

1. GitHub 리포 → **Settings → Secrets and variables → Actions**:
   - `KAKAO_REST_API_KEY` = REST API 키
   - `KAKAO_TOKEN_PASSPHRASE` = 방금 정한 passphrase
2. 토큰 파일 커밋:
   ```bash
   git add .secrets/kakao_token.enc
   git commit -m "chore: add encrypted kakao token"
   git push
   ```

## 4. 동작 확인

**Actions 탭 → "Weekly Traffic Report" → Run workflow**로 수동 실행 →
카카오톡 "나와의 채팅"에 요약 메시지가 도착하면 성공입니다.

---

### 왜 토큰을 암호화해서 리포에 커밋하나요?

카카오 refresh token은 약 60일 유효하고, 만료 30일 전부터는 갱신 호출 시 **새 토큰으로
교체(rotation)**됩니다. GitHub Actions는 기본 권한으로 시크릿을 갱신할 수 없어서, 교체된
토큰을 저장할 곳이 필요합니다 — 그래서 passphrase(시크릿에만 존재)로 AES-256 암호화한
파일을 리포에 두고, 워크플로우가 교체 발생 시 재암호화해 자동 커밋합니다. passphrase 없이는
파일을 복호화할 수 없으므로 public 리포에 있어도 안전합니다.

### 문제 해결

| 증상 | 해결 |
|---|---|
| `Kakao token refresh failed` | refresh token 60일 만료. `python generator/kakao_auth.py` 재실행 후 `.secrets/kakao_token.enc` 다시 커밋 |
| `KakaoTalk send failed (403)` | 동의항목에서 talk_message가 켜져 있는지, 인증 시 동의했는지 확인 후 재인증 |
| talk_message 동의항목이 잠겨 있음 / 메시지 API 사용 불가 안내 | 비즈 앱 전환이 안 된 상태입니다 — 위 1단계의 [개인 개발자 비즈 앱 전환] 버튼 참고 |
| 메시지가 안 옴 (에러도 없음) | 카카오톡 → 설정 → 알림에서 "나와의 채팅" 알림 확인 |
| `KakaoTalk not configured — skipping send` 로그 | 시크릿 2개와 `.secrets/kakao_token.enc` 커밋 여부 확인 (위 3단계) |
