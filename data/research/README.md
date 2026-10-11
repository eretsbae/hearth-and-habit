# 리서치 근거 문서 (research dossiers)

`generator/research.py` 가 글을 쓰기 전에 웹 검색·페이지 읽기로 만든 근거 문서입니다.
파일 이름은 글 slug 와 같습니다(`<slug>.json`).

- `evidence[].source_url` 은 리서치 중 API 가 실제로 가져온 URL 만 남습니다(모델이 지어낸 URL 은 저장 전에 걸러짐).
- `sources` 는 글에서 인용해도 되는 URL 목록입니다. 글의 외부 링크는 이것과 `config/facts.yml` 출처만 허용됩니다.
- 글 속 수치가 의심되면 이 파일에서 근거와 출처를 찾아 대조합니다.
