"""Actions 실패 알림을 '진짜 실패'로만 거른다 (ci-alerts.yml이 호출).

GitHub 기본 실패 메일은 러너 장애처럼 우리 코드가 한 줄도 안 돈 실행에도
뜬다(2026-10-05 "job was not acquired by Runner" 건). 그래서 기본 메일은 끄고,
여기서 두 경우만 이슈(작성·담당자 지정 → 메일 알림)로 올린다.

  run <run_id>  잡 하나라도 conclusion=failure면 알림. 러너를 못 받은 잡은
                cancelled로 끝나므로 걸러진다.
  stale         예약 워크플로우가 연속 2회 이상 성공하지 못하면 알림(장시간
                장애 감지). 정상으로 돌아오면 이슈를 닫는다.

환경 변수: GITHUB_TOKEN, GITHUB_REPOSITORY. --dry-run이면 이슈를 쓰지 않는다.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "eretsbae/hearth-and-habit")
ASSIGNEE = REPO.split("/")[0]
LABEL = "ci-alert"
DRY_RUN = "--dry-run" in sys.argv

# 워크플로우 파일 → 마지막 성공 후 이 시간이 지나면 '멈춤'으로 본다.
# 각 값은 "한 번 거른 경우의 최대 간격"보다 크고 "두 번 연속 거른 경우의
# 최소 간격"보다 작게 잡았다(예약 실행이 GitHub 쪽에서 수 시간 늦는 것 감안).
# 예약을 멈추면(중단 기준 등) 여기서도 빼야 매일 알림이 뜨지 않는다.
WATCH = {
    "generate-and-publish.yml": 6 * 24,  # 월/수/금: 1회 누락 최대 5일, 2회 누락 최소 7일
    "pinterest-publish.yml": 60,         # 매일: 1회 누락 48시간, 2회 누락 72시간
    "weekly-report.yml": 17 * 24,        # 매주: 1회 누락 14일, 2회 누락 21일
}


def api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def open_alert(title: str) -> dict | None:
    issues = api("GET", f"/repos/{REPO}/issues?state=open&labels={LABEL}&per_page=100")
    return next((i for i in issues if i["title"] == title), None)


def raise_alert(title: str, body: str) -> None:
    """같은 제목의 열린 이슈가 있으면 댓글, 없으면 새 이슈."""
    print(f"ALERT: {title}\n{body}")
    if DRY_RUN:
        return
    existing = open_alert(title)
    if existing:
        api("POST", f"/repos/{REPO}/issues/{existing['number']}/comments", {"body": body})
        return
    try:
        api("POST", f"/repos/{REPO}/labels", {"name": LABEL, "color": "d73a4a"})
    except urllib.error.HTTPError as e:
        if e.code != 422:  # 422 = 이미 있음
            raise
    api("POST", f"/repos/{REPO}/issues",
        {"title": title, "body": body, "labels": [LABEL], "assignees": [ASSIGNEE]})


def clear_alert(title: str, body: str) -> None:
    existing = open_alert(title)
    if not existing:
        return
    print(f"RESOLVED: {title}")
    if DRY_RUN:
        return
    api("POST", f"/repos/{REPO}/issues/{existing['number']}/comments", {"body": body})
    api("PATCH", f"/repos/{REPO}/issues/{existing['number']}", {"state": "closed"})


def check_run(run_id: str) -> None:
    run = api("GET", f"/repos/{REPO}/actions/runs/{run_id}")
    jobs = api("GET", f"/repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100")["jobs"]
    failed = [j for j in jobs if j["conclusion"] == "failure"]
    if not failed:
        summary = ", ".join(f"{j['name']}={j['conclusion']}" for j in jobs) or "잡 없음"
        print(f"알림 안 함 — 실행 {run_id} ({run['name']}): {summary}")
        return
    lines = []
    for j in failed:
        steps = [s["name"] for s in j.get("steps", []) if s["conclusion"] == "failure"]
        lines.append(f"- 잡 `{j['name']}` 실패 단계: {', '.join(steps) or '(단계 정보 없음)'}")
    raise_alert(
        f"[CI 실패] {run['name']}",
        f"{run['html_url']}\n\n"
        f"- 트리거: {run['event']} / 커밋 {run['head_sha'][:7]} / {run['created_at']}\n"
        + "\n".join(lines),
    )


def check_stale() -> None:
    now = datetime.now(timezone.utc)
    for wf, max_hours in WATCH.items():
        meta = api("GET", f"/repos/{REPO}/actions/workflows/{wf}")
        title = f"[CI 정지] {meta['name']}"
        if meta["state"] != "active":
            print(f"{wf}: {meta['state']} — 건너뜀")
            continue
        runs = api("GET", f"/repos/{REPO}/actions/workflows/{wf}/runs?status=success&per_page=1")
        last = runs["workflow_runs"][0] if runs["workflow_runs"] else None
        if last is None:
            print(f"{wf}: 성공 이력 없음 — 건너뜀")
            continue
        ended = datetime.fromisoformat(last["updated_at"].replace("Z", "+00:00"))
        age = (now - ended).total_seconds() / 3600
        print(f"{wf}: 마지막 성공 {age:.0f}시간 전 (기준 {max_hours}시간)")
        if age > max_hours:
            raise_alert(
                title,
                f"마지막 성공 실행이 {age:.0f}시간 전({last['updated_at']})입니다 — "
                f"예약 실행을 연속으로 놓쳤습니다(기준 {max_hours}시간).\n\n"
                f"마지막 성공: {last['html_url']}\n"
                f"실행 목록: https://github.com/{REPO}/actions/workflows/{wf}\n"
                "GitHub 장애(githubstatus.com)인지, 실행이 cancelled로 끝났는지 확인하세요.",
            )
        else:
            clear_alert(title, f"정상화 — 마지막 성공 {last['html_url']}")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if args[:1] == ["run"] and len(args) == 2:
        check_run(args[1])
    elif args == ["stale"]:
        check_stale()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
