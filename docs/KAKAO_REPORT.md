# 주간 트래픽 리포트 → 카카오톡 설정 (최초 1회, 약 10분)

매주 월요일 아침(09:23 KST) GitHub Actions가 Blogger 조회수를 수집해서:

1. `data/traffic_history.json`에 주간 스냅샷 누적 (전주 대비 증감 계산용)
2. `docs/reports/weekly-YYYY-MM-DD.md`에 상세 리포트 커밋
3. **카카오톡 "나에게 보내기"로 4줄 요약 전송** (상세 리포트 링크 버튼 포함)

1·2번은 아무 설정 없이 즉시 동작합니다(구글 시크릿만 있으면 됨). 3번 카카오톡 전송만
아래 1회 설정이 필요합니다. 설정 전까지는 전송만 조용히 건너뜁니다.

## 1. Kakao Developers 앱 만들기

1. https://developers.kakao.com 접속 → 카카오 계정 로그인 → **내 애플리케이션 → 애플리케이션 추가하기**
   - 앱 이름/회사명: 아무거나 (예: `hearth-habit-report`)
2. 만든 앱 선택 → **앱 설정 → 플랫폼 → Web 플랫폼 등록**
   - 사이트 도메인: `http://localhost:8765`
3. **제품 설정 → 카카오 로그인** → 활성화 **ON**
   - **Redirect URI** 등록: `http://localhost:8765`
4. **제품 설정 → 카카오 로그인 → 동의항목** → **카카오톡 메시지 전송(talk_message)** → 사용 설정
   ("나에게 보내기"만 쓰므로 검수/비즈 앱 전환 없이 바로 사용 가능합니다)
5. **앱 설정 → 앱 키**에서 **REST API 키** 복사

## 2. 로컬에서 1회 인증

리포지토리를 클론한 본인 컴퓨터에서:

```bash
cd hearth-and-habit
python generator/kakao_auth.py
```

- REST API 키 입력 → 브라우저에서 카카오 로그인 + 메시지 전송 동의
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
| 메시지가 안 옴 (에러도 없음) | 카카오톡 → 설정 → 알림에서 "나와의 채팅" 알림 확인 |
| `KakaoTalk not configured — skipping send` 로그 | 시크릿 2개와 `.secrets/kakao_token.enc` 커밋 여부 확인 (위 3단계) |
